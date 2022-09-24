import json, os, sys
from uuid import uuid4
from datetime import datetime
import threading, time
from .. import logger

class WaitingPrompt:
    def __init__(self, db, wps, pgs, prompt, user, params, **kwargs):
        self.db = db
        self._waiting_prompts = wps
        self._processing_generations = pgs
        self.prompt = prompt
        self.user = user
        self.params = params
        self.total_usage = 0
        self.extract_params(params)
        self.id = str(uuid4())
        # The generations that have been created already
        self.processing_gens = []
        self.last_process_time = datetime.now()
        self.workers = kwargs.get("workers", [])
        # Prompt requests are removed after 1 mins of inactivity per n, to a max of 5 minutes
        self.stale_time = 180 * self.n
        if self.stale_time > 600:
            self.stale_time = 600

    # These are typically worker-specific so they will be defined in the specific class for this horde type
    def extract_params(self, params):
        self.n = params.pop('n', 1)
        self.prepare_job_payload(params)

    def prepare_job_payload(self, initial_dict = {}):
        # This is what we send to the worker
        self.gen_payload = initial_dict

    def activate(self):
        '''We separate the activation from __init__ as often we want to check if there's a valid worker for it
        Before we add it to the queue
        '''
        self._waiting_prompts.add_item(self)
        thread = threading.Thread(target=self.check_for_stale, args=())
        thread.daemon = True
        thread.start()

    def needs_gen(self):
        if self.n > 0:
            return(True)
        return(False)

    def start_generation(self, worker):
        if self.n <= 0:
            return
        new_gen = ProcessingGeneration(self, self._processing_generations, worker)
        self.processing_gens.append(new_gen)
        self.n -= 1
        self.refresh()
        prompt_payload = {
            "payload": self.gen_payload,
            "id": new_gen.id,
        }
        return(prompt_payload)

    def is_completed(self):
        if self.needs_gen():
            return(False)
        for procgen in self.processing_gens:
            if not procgen.is_completed():
                return(False)
        return(True)

    def count_processing_gens(self):
        ret_dict = {
            "finished": 0,
            "processing": 0,
        }
        for procgen in self.processing_gens:
            if procgen.is_completed():
                ret_dict["finished"] += 1
            else:
                ret_dict["processing"] += 1
        return(ret_dict)

    def get_status(self, lite = False):
        ret_dict = self.count_processing_gens()
        ret_dict["waiting"] = self.n
        ret_dict["done"] = self.is_completed()
        # Lite mode does not include the generations, to spare me download size
        if not lite:
            ret_dict["generations"] = []
            for procgen in self.processing_gens:
                if procgen.is_completed():
                    ret_dict["generations"].append(procgen.get_details())
        return(ret_dict)

    def get_lite_status(self):
        '''Same as get_status(), but without the images to avoid unnecessary size'''
        ret_dict = self.get_status(True)
        return(ret_dict)

    def get_own_queue_stats(self):
        '''Get out position in the working prompts queue sorted by kudos
        If this gen is completed, we return (-1,-1) which represents this, to avoid doing operations.
        '''
        if self.needs_gen():
            return(self._waiting_prompts.get_wp_queue_stats(self))
        return(-1,0,0)

    def record_usage(self, thing, kudos):
        '''Record that we received a requested generation and how much kudos it costs us
        We use 'thing' here as we do not care what type of thing we're recording at this point
        This avoids me having to extend this just to change a var name
        '''
        self.user.record_usage(thing, kudos)
        self.refresh()

    def check_for_stale(self):
        while True:
            if self._waiting_prompts.is_deleted(self):
                break
            if self.is_stale():
                self.delete()
                break
            time.sleep(600)

    def delete(self):
        for gen in self.processing_gens:
            gen.delete()
        self._waiting_prompts.del_item(self)
        del self

    def refresh(self):
        self.last_process_time = datetime.now()

    def is_stale(self):
        if (datetime.now() - self.last_process_time).seconds > self.stale_time:
            return(True)
        return(False)


class ProcessingGeneration:
    def __init__(self, owner, pgs, worker):
        self._processing_generations = pgs
        self.id = str(uuid4())
        self.owner = owner
        self.worker = worker
        self.start_time = datetime.now()
        self._processing_generations.add_item(self)

    # This should be extended by every horde type
    def set_generation(self, generation):
        if self.is_completed():
            return(0)
        self.generation = generation
        return(0)

    def is_completed(self):
        if self.generation:
            return(True)
        return(False)

    def delete(self):
        self._processing_generations.del_item(self)
        del self

    # This should be extended by every horde type
    def get_seconds_needed(self):
        return(0)

    def get_expected_time_left(self):
        if self.is_completed():
            return(0)
        seconds_needed = self.get_seconds_needed()
        seconds_elapsed = (datetime.now() - self.start_time).seconds
        expected_time = seconds_needed - seconds_elapsed
        # In case we run into a slow request
        if expected_time < 0:
            expected_time = 0
        return(expected_time)

    # This should be extended by every horde type
    def get_details(self):
        '''Returns a dictionary with details about this processing generation'''
        ret_dict = {
            "gen": procgen.generation,
            "worker_id": procgen.worker.id,
            "worker_name": procgen.worker.name,
        }
        return(ret_dict)

class Worker:
    def __init__(self, db):
        self.db = db
        self.kudos_details = {
            "generated": 0,
            "uptime": 0,
        }
        self.last_reward_uptime = 0
        # Every how many seconds does this worker get a kudos reward
        self.uptime_reward_threshold = 600
        # Maintenance can be requested by the owner of the worker (to allow them to not pick up more requests)
        self.maintenance = False
        # Paused is set by the admins to prevent that worker from seeing any more requests
        # This can be used for stopping workers who misbhevave for example, without informing their owners
        self.paused = False

    def create(self, user, name):
        self.user = user
        self.name = name
        self.id = str(uuid4())
        self.contributions = 0
        self.fulfilments = 0
        self.kudos = 0
        self.performances = []
        self.uptime = 0
        self.db.register_new_worker(self)

    def check_in(self, max_pixels):
        if not self.is_stale():
            self.uptime += (datetime.now() - self.last_check_in).seconds
            # Every 10 minutes of uptime gets 100 kudos rewarded
            if self.uptime - self.last_reward_uptime > self.uptime_reward_threshold:
                kudos = 100
                self.modify_kudos(kudos,'uptime')
                self.user.record_uptime(kudos)
                logger.debug(f"worker '{self.name}' received {kudos} kudos for uptime of {self.uptime_reward_threshold} seconds.")
                self.last_reward_uptime = self.uptime
        else:
            # If the worker comes back from being stale, we just reset their last_reward_uptime
            # So that they have to stay up at least 10 mins to get uptime kudos
            self.last_reward_uptime = self.uptime
        self.last_check_in = datetime.now()
        self.max_pixels = max_pixels
        logger.debug(f"Worker {self.name} checked-in")

    def get_human_readable_uptime(self):
        if self.uptime < 60:
            return(f"{self.uptime} seconds")
        elif self.uptime < 60*60:
            return(f"{round(self.uptime/60,2)} minutes")
        elif self.uptime < 60*60*24:
            return(f"{round(self.uptime/60/60,2)} hours")
        else:
            return(f"{round(self.uptime/60/60/24,2)} days")

    def can_generate(self, waiting_prompt):
        # takes as an argument a WaitingPrompt class and checks if this worker is valid for generating it
        is_matching = True
        skipped_reason = None
        if self.is_stale():
            # We don't consider stale workers in the request, so we don't need to report a reason
            is_matching = False
        # if thes worker is paused, we return OK, but skip everything
        if len(waiting_prompt.workers) >= 1 and self.id not in waiting_prompt.workers:
            is_matching = False
            skipped_reason = 'worker_id'
        if self.max_pixels < waiting_prompt.width * waiting_prompt.height:
            is_matching = False
            skipped_reason = 'max_pixels'
        return([is_matching,skipped_reason])

    @logger.catch
    def record_contribution(self, pixelsteps, kudos, pixelsteps_per_sec):
        self.user.record_contributions(pixelsteps, kudos)
        self.modify_kudos(kudos,'generated')
        self.contributions = round(self.contributions + pixelsteps/1000000,2) # We store them as Megapixelsteps
        self.fulfilments += 1
        self.performances.append(pixelsteps_per_sec)
        if len(self.performances) > 20:
            del self.performances[0]

    def modify_kudos(self, kudos, action = 'generated'):
        self.kudos = round(self.kudos + kudos, 2)
        self.kudos_details[action] = round(self.kudos_details.get(action,0) + abs(kudos), 2) 

    def get_performance_average(self):
        if len(self.performances):
            ret_num = sum(self.performances) / len(self.performances)
        else:
            # Always sending at least 1 pixelstep per second, to avoid divisions by zero
            ret_num = 1
        return(ret_num)

    def get_performance(self):
        if len(self.performances):
            ret_str = f'{round(sum(self.performances) / len(self.performances),1)} pixelsteps per second'
        else:
            ret_str = f'No requests fulfilled yet'
        return(ret_str)

    def is_stale(self):
        try:
            if (datetime.now() - self.last_check_in).seconds > 300:
                return(True)
        # If the last_check_in isn't set, it's a new worker, so it's stale by default
        except AttributeError:
            return(True)
        return(False)

    # We display these in the workers list json
    def get_details(self, is_privileged = False):
        ret_dict = {
            "name": self.name,
            "id": self.id,
            "max_pixels": self.max_pixels,
            "megapixelsteps_generated": self.contributions,
            "requests_fulfilled": self.fulfilments,
            "kudos_rewards": self.kudos,
            "kudos_details": self.kudos_details,
            "performance": self.get_performance(),
            "uptime": self.uptime,
            "maintenance_mode": self.maintenance,
        }
        if is_privileged:
            ret_dict['paused'] = self.paused
        return(ret_dict)

    @logger.catch
    def serialize(self):
        ret_dict = {
            "oauth_id": self.user.oauth_id,
            "name": self.name,
            "max_pixels": self.max_pixels,
            "contributions": self.contributions,
            "fulfilments": self.fulfilments,
            "kudos": self.kudos,
            "kudos_details": self.kudos_details.copy(),
            "performances": self.performances.copy(),
            "last_check_in": self.last_check_in.strftime("%Y-%m-%d %H:%M:%S"),
            "id": self.id,
            "uptime": self.uptime,
            "paused": self.paused,
            "maintenance": self.maintenance,
        }
        return(ret_dict)

    @logger.catch
    def deserialize(self, saved_dict, convert_flag = None):
        self.user = self.db.find_user_by_oauth_id(saved_dict["oauth_id"])
        self.name = saved_dict["name"]
        self.max_pixels = saved_dict["max_pixels"]
        self.contributions = saved_dict["contributions"]
        if convert_flag == 'pixelsteps':
            self.contributions = round(self.contributions / 50,2)
        self.fulfilments = saved_dict["fulfilments"]
        self.kudos = saved_dict.get("kudos",0)
        self.kudos_details = saved_dict.get("kudos_details",self.kudos_details)
        self.performances = saved_dict.get("performances",[])
        self.last_check_in = datetime.strptime(saved_dict["last_check_in"],"%Y-%m-%d %H:%M:%S")
        self.id = saved_dict["id"]
        self.uptime = saved_dict.get("uptime",0)
        self.maintenance = saved_dict.get("maintenance",False)
        self.paused = saved_dict.get("paused",False)
        self.db.workers[self.name] = self


class Index:
    def __init__(self):
        self._index = {}

    def add_item(self, item):
        self._index[item.id] = item

    def get_item(self, uuid):
        return(self._index.get(uuid))

    def del_item(self, item):
        del self._index[item.id]

    def get_all(self):
        return(self._index.values())

    def is_deleted(self,item):
        if item.id in self._index:
            return(False)
        return(True)

class PromptsIndex(Index):

    def count_waiting_requests(self, user):
        count = 0
        for wp in self._index.values():
            if wp.user == user and not wp.is_completed():
                count += wp.n
        return(count)

    def count_total_waiting_generations(self):
        count = 0
        for wp in self._index.values():
            count += wp.n + wp.count_processing_gens()["processing"]
        return(count)

    def count_totals(self):
        ret_dict = {
            "queued_requests": 0,
            # mps == Megapixelsteps
            "queued_megapixelsteps": 0,
        }
        for wp in self._index.values():
            ret_dict["queued_requests"] += wp.n
            if wp.n > 0:
                ret_dict["queued_megapixelsteps"] += wp.pixelsteps / 1000000
        # We round the end result to avoid to many decimals
        ret_dict["queued_megapixelsteps"] = round(ret_dict["queued_megapixelsteps"],2)
        return(ret_dict)

    def get_waiting_wp_by_kudos(self):
        sorted_wp_list = sorted(self._index.values(), key=lambda x: x.user.kudos, reverse=True)
        final_wp_list = []
        for wp in sorted_wp_list:
            if wp.needs_gen():
                final_wp_list.append(wp)
        return(final_wp_list)

    # Returns the queue position of the provided WP based on kudos
    # Also returns the amount of mps until the wp is generated
    # Also returns the amount of different gens queued
    def get_wp_queue_stats(self, wp):
        mps_ahead_in_queue = 0
        n_ahead_in_queue = 0
        priority_sorted_list = self.get_waiting_wp_by_kudos()
        for iter in range(len(priority_sorted_list)):
            mps_ahead_in_queue += priority_sorted_list[iter].get_queued_megapixelsteps()
            n_ahead_in_queue += priority_sorted_list[iter].n
            if priority_sorted_list[iter] == wp:
                mps_ahead_in_queue = round(mps_ahead_in_queue,2)
                return(iter, mps_ahead_in_queue, n_ahead_in_queue)
        # -1 means the WP is done and not in the queue
        return(-1,0,0)
                

class GenerationsIndex(Index):
    pass


class User:
    def __init__(self, db):
        self.db = db
        self.kudos = 0
        self.kudos_details = {
            "accumulated": 0,
            "gifted": 0,
            "admin": 0,
            "received": 0,
        }
        self.concurrency = 30
        self.usage_multiplier = 1.0

    def create_anon(self):
        self.username = 'Anonymous'
        self.oauth_id = 'anon'
        self.api_key = '0000000000'
        self.invite_id = ''
        self.creation_date = datetime.now()
        self.last_active = datetime.now()
        self.id = 0
        self.contributions = {
            "megapixelsteps": 0,
            "fulfillments": 0
        }
        self.usage = {
            "megapixelsteps": 0,
            "requests": 0
        }
        # We allow anonymous users more leeway for the max amount of concurrent requests
        # This is balanced by their lower priority
        self.concurrency = 200

    def create(self, username, oauth_id, api_key, invite_id):
        self.username = username
        self.oauth_id = oauth_id
        self.api_key = api_key
        self.invite_id = invite_id
        self.creation_date = datetime.now()
        self.last_active = datetime.now()
        self.id = self.db.register_new_user(self)
        self.contributions = {
            "megapixelsteps": 0,
            "fulfillments": 0
        }
        self.usage = {
            "megapixelsteps": 0,
            "requests": 0
        }

    # Checks that this user matches the specified API key
    def check_key(api_key):
        if self.api_key and self.api_key == api_key:
            return(True)
        return(False)

    def get_unique_alias(self):
        return(f"{self.username}#{self.id}")

    def record_usage(self, pixelsteps, kudos):
        self.usage["megapixelsteps"] = round(self.usage["megapixelsteps"] + (pixelsteps * self.usage_multiplier / 1000000),2)
        self.usage["requests"] += 1
        self.modify_kudos(-kudos,"accumulated")

    def record_contributions(self, pixelsteps, kudos):
        self.contributions["megapixelsteps"] = round(self.contributions["megapixelsteps"] + pixelsteps/1000000,2)
        self.contributions["fulfillments"] += 1
        self.modify_kudos(kudos,"accumulated")

    def record_uptime(self, kudos):
        self.modify_kudos(kudos,"accumulated")

    def modify_kudos(self, kudos, action = 'accumulated'):
        logger.debug(f"modifying existing {self.kudos} kudos of {self.get_unique_alias()} by {kudos} for {action}")
        self.kudos = round(self.kudos + kudos, 2)
        self.kudos_details[action] = round(self.kudos_details.get(action,0) + kudos, 2)

    def get_details(self):
        ret_dict = {
            "id": self.id,
            "kudos": self.kudos,
            "kudos_details": self.kudos_details,
            "usage": self.usage,
            "contributions": self.contributions,
            "concurrency": self.concurrency,
        }
        return(ret_dict)


    @logger.catch
    def serialize(self):
        ret_dict = {
            "username": self.username,
            "oauth_id": self.oauth_id,
            "api_key": self.api_key,
            "kudos": self.kudos,
            "kudos_details": self.kudos_details.copy(),
            "id": self.id,
            "invite_id": self.invite_id,
            "contributions": self.contributions.copy(),
            "usage": self.usage.copy(),
            "usage_multiplier": self.usage_multiplier,
            "concurrency": self.concurrency,
            "creation_date": self.creation_date.strftime("%Y-%m-%d %H:%M:%S"),
            "last_active": self.last_active.strftime("%Y-%m-%d %H:%M:%S"),
        }
        return(ret_dict)

    @logger.catch
    def deserialize(self, saved_dict, convert_flag = None):
        self.username = saved_dict["username"]
        self.oauth_id = saved_dict["oauth_id"]
        self.api_key = saved_dict["api_key"]
        self.kudos = saved_dict["kudos"]
        self.kudos_details = saved_dict.get("kudos_details", self.kudos_details)
        self.id = saved_dict["id"]
        self.invite_id = saved_dict["invite_id"]
        self.contributions = saved_dict["contributions"]
        self.usage = saved_dict["usage"]
        self.concurrency = saved_dict.get("concurrency", 30)
        self.usage_multiplier = saved_dict.get("usage_multiplier", 1.0)
        if self.api_key == '0000000000':
            self.concurrency = 200
        if convert_flag == 'pixelsteps':
            # I average to 25 steps, to convert pixels to pixelsteps, since I wasn't tracking it until now
            self.contributions['megapixelsteps'] = round(self.contributions['pixels'] / 50,2)
            del self.contributions['pixels']
            self.usage['megapixelsteps'] = round(self.usage['pixels'] / 50,2)
            del self.usage['pixels']
        self.creation_date = datetime.strptime(saved_dict["creation_date"],"%Y-%m-%d %H:%M:%S")
        self.last_active = datetime.strptime(saved_dict["last_active"],"%Y-%m-%d %H:%M:%S")


class Stats:
    def __init__(self, db, convert_flag = None, interval = 60):
        self.db = db
        self.worker_performances = []
        self.fulfillments = []
        self.interval = interval
        self.last_pruning = datetime.now()

    def record_fulfilment(self, pixelsteps, starting_time):
        seconds_taken = (datetime.now() - starting_time).seconds
        if seconds_taken == 0:
            pixelsteps_per_sec = 1
        else:
            pixelsteps_per_sec = round(pixelsteps / seconds_taken,1)
        if len(self.worker_performances) >= 10:
            del self.worker_performances[0]
        self.worker_performances.append(pixelsteps_per_sec)
        fulfillment_dict = {
            "pixelsteps": pixelsteps,
            "start_time": starting_time,
            "deliver_time": datetime.now(),
        }
        self.fulfillments.append(fulfillment_dict)
        return(pixelsteps_per_sec)

    def get_megapixelsteps_per_min(self):
        total_pixelsteps = 0
        pruned_array = []
        for fulfillment in self.fulfillments:
            if (datetime.now() - fulfillment["deliver_time"]).seconds <= 60:
                pruned_array.append(fulfillment)
                total_pixelsteps += fulfillment["pixelsteps"]
        if (datetime.now() - self.last_pruning).seconds > self.interval:
            self.last_pruning = datetime.now()
            self.fulfillments = pruned_array
            logger.debug("Pruned fulfillments")
        megapixelsteps_per_min = round(total_pixelsteps / 1000000,2)
        return(megapixelsteps_per_min)

    def get_request_avg(self):
        if len(self.worker_performances) == 0:
            return(0)
        avg = sum(self.worker_performances) / len(self.worker_performances)
        return(round(avg,1))

    @logger.catch
    def serialize(self):
        serialized_fulfillments = []
        for fulfillment in self.fulfillments.copy():
            json_fulfillment = {
                "pixelsteps": fulfillment["pixelsteps"],
                "start_time": fulfillment["start_time"].strftime("%Y-%m-%d %H:%M:%S"),
                "deliver_time": fulfillment["deliver_time"].strftime("%Y-%m-%d %H:%M:%S"),
            }
            serialized_fulfillments.append(json_fulfillment)
        ret_dict = {
            "worker_performances": self.worker_performances,
            "fulfillments": serialized_fulfillments,
        }
        return(ret_dict)

    @logger.catch
    def deserialize(self, saved_dict, convert_flag = None):
        # Convert old key
        if "fulfilment_times" in saved_dict:
            self.worker_performances = saved_dict["fulfilment_times"]
        elif "server_performances" in saved_dict:
            self.worker_performances = saved_dict["fulfilment_times"]
        else:
            self.worker_performances = saved_dict["worker_performances"]
        deserialized_fulfillments = []
        for fulfillment in saved_dict.get("fulfillments", []):
            class_fulfillment = {
                "pixelsteps": fulfillment["pixelsteps"],
                "start_time": datetime.strptime(fulfillment["start_time"],"%Y-%m-%d %H:%M:%S"),
                "deliver_time":datetime.strptime(fulfillment["deliver_time"],"%Y-%m-%d %H:%M:%S"),
            }
            deserialized_fulfillments.append(class_fulfillment)
        self.fulfillments = deserialized_fulfillments
       
class Database:
    def __init__(self, convert_flag = None, interval = 60):
        self.interval = interval
        self.ALLOW_ANONYMOUS = True
        # This is used for synchronous generations
        self.WORKERS_FILE = "db/workers.json"
        self.workers = {}
        # Other miscellaneous statistics
        self.STATS_FILE = "db/stats.json"
        self.stats = Stats(self)
        self.USERS_FILE = "db/users.json"
        self.users = {}
        # Increments any time a new user is added
        # Is appended to usernames, to ensure usernames never conflict
        self.last_user_id = 0
        logger.init(f"Database Load", status="Starting")
        if convert_flag:
            logger.init_warn(f"Convert Flag '{convert_flag}' received.", status="Converting")
        if os.path.isfile(self.USERS_FILE):
            with open(self.USERS_FILE) as db:
                serialized_users = json.load(db)
                for user_dict in serialized_users:
                    if not user_dict:
                        logger.error("Found null user on db load. Bypassing")
                        continue
                    new_user = User(self)
                    new_user.deserialize(user_dict,convert_flag)
                    self.users[new_user.oauth_id] = new_user
                    if new_user.id > self.last_user_id:
                        self.last_user_id = new_user.id
        self.anon = self.find_user_by_oauth_id('anon')
        if not self.anon:
            self.anon = User(self)
            self.anon.create_anon()
            self.users[self.anon.oauth_id] = self.anon
        if os.path.isfile(self.WORKERS_FILE):
            with open(self.WORKERS_FILE) as db:
                serialized_workers = json.load(db)
                for worker_dict in serialized_workers:
                    if not worker_dict:
                        logger.error("Found null worker on db load. Bypassing")
                        continue
                    new_worker = Worker(self)
                    new_worker.deserialize(worker_dict,convert_flag)
                    self.workers[new_worker.name] = new_worker
        if os.path.isfile(self.STATS_FILE):
            with open(self.STATS_FILE) as stats_db:
                self.stats.deserialize(json.load(stats_db),convert_flag)

        if convert_flag:
            self.write_files_to_disk()
            logger.init_ok(f"Convertion complete.", status="Exiting")
            sys.exit()
        thread = threading.Thread(target=self.write_files, args=())
        thread.daemon = True
        thread.start()
        logger.init_ok(f"Database Load", status="Completed")

    def write_files(self):
        logger.init_ok("Database Store Thread", status="Started")
        while True:
            self.write_files_to_disk()
            time.sleep(self.interval)

    def write_files_to_disk(self):
        if not os.path.exists('db'):
            os.mkdir('db')
        worker_serialized_list = []
        logger.debug("Saving DB")
        for worker in self.workers.copy().values():
            # We don't store data for anon workers
            if worker.user == self.anon: continue
            worker_serialized_list.append(worker.serialize())
        with open(self.WORKERS_FILE, 'w') as db:
            json.dump(worker_serialized_list,db)
        with open(self.STATS_FILE, 'w') as db:
            json.dump(self.stats.serialize(),db)
        user_serialized_list = []
        for user in self.users.copy().values():
            user_serialized_list.append(user.serialize())
        with open(self.USERS_FILE, 'w') as db:
            json.dump(user_serialized_list,db)

    def get_top_contributor(self):
        top_contribution = 0
        top_contributor = None
        user = None
        for user in self.users.values():
            if user.contributions['megapixelsteps'] > top_contribution and user != self.anon:
                top_contributor = user
                top_contribution = user.contributions['megapixelsteps']
        return(top_contributor)

    def get_top_worker(self):
        top_worker = None
        top_worker_contribution = 0
        for worker in self.workers:
            if self.workers[worker].contributions > top_worker_contribution:
                top_worker = self.workers[worker]
                top_worker_contribution = self.workers[worker].contributions
        return(top_worker)

    def count_active_workers(self):
        count = 0
        for worker in self.workers.values():
            if not worker.is_stale():
                count += 1
        return(count)

    def get_total_usage(self):
        totals = {
            "megapixelsteps": 0,
            "fulfilments": 0,
        }
        for worker in self.workers.values():
            totals["megapixelsteps"] += worker.contributions
            totals["fulfilments"] += worker.fulfilments
        return(totals)


    def register_new_user(self, user):
        self.last_user_id += 1
        self.users[user.oauth_id] = user
        logger.info(f'New user created: {user.username}#{self.last_user_id}')
        return(self.last_user_id)

    def register_new_worker(self, worker):
        self.workers[worker.name] = worker
        logger.info(f'New worker checked-in: {worker.name} by {worker.user.get_unique_alias()}')

    def find_user_by_oauth_id(self,oauth_id):
        if oauth_id == 'anon' and not self.ALLOW_ANONYMOUS:
            return(None)
        return(self.users.get(oauth_id))

    def find_user_by_username(self, username):
        for user in self.users.values():
            ulist = username.split('#')
            # This approach handles someone cheekily putting # in their username
            if user.username == "#".join(ulist[:-1]) and user.id == int(ulist[-1]):
                if user == self.anon and not self.ALLOW_ANONYMOUS:
                    return(None)
                return(user)
        return(None)

    def find_user_by_id(self, user_id):
        for user in self.users.values():
            # The arguments passed to the URL are always strings
            if str(user.id) == user_id:
                if user == self.anon and not self.ALLOW_ANONYMOUS:
                    return(None)
                return(user)
        return(None)

    def find_user_by_api_key(self,api_key):
        for user in self.users.values():
            if user.api_key == api_key:
                if user == self.anon and not self.ALLOW_ANONYMOUS:
                    return(None)
                return(user)
        return(None)

    def find_worker_by_name(self,worker_name):
        return(self.workers.get(worker_name))

    def find_worker_by_id(self,worker_id):
        for worker in self.workers.values():
            if worker.id == worker_id:
                return(worker)
        return(None)

    def transfer_kudos(self, source_user, dest_user, amount):
        if amount > source_user.kudos:
            return([0,'Not enough kudos.'])
        source_user.modify_kudos(-amount, 'gifted')
        dest_user.modify_kudos(amount, 'received')
        return([amount,'OK'])

    def transfer_kudos_to_username(self, source_user, dest_username, amount):
        dest_user = self.find_user_by_username(dest_username)
        if not dest_user:
            return([0,'Invalid target username.'])
        if dest_user == self.anon:
            return([0,'Tried to burn kudos via sending to Anonymous. Assuming PEBKAC and aborting.'])
        if dest_user == source_user:
            return([0,'Cannot send kudos to yourself, ya monkey!'])
        kudos = self.transfer_kudos(source_user,dest_user, amount)
        return(kudos)

    def transfer_kudos_from_apikey_to_username(self, source_api_key, dest_username, amount):
        source_user = self.find_user_by_api_key(source_api_key)
        if not source_user:
            return([0,'Invalid API Key.'])
        if source_user == self.anon:
            return([0,'You cannot transfer Kudos from Anonymous, smart-ass.'])
        kudos = self.transfer_kudos_to_username(source_user, dest_username, amount)
        return(kudos)
