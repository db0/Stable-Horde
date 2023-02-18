import random

from horde.logger import logger
from horde.vars import text_thing_divisor
from horde.flask import db
from horde.utils import get_random_seed
from horde.classes.base.waiting_prompt import WaitingPrompt
from horde.r2 import generate_procgen_upload_url, download_source_image, download_source_mask
from horde.image import convert_pil_to_b64
from horde.bridge_reference import check_bridge_capability

class TextWaitingPrompt(WaitingPrompt):
    __mapper_args__ = {
        "polymorphic_identity": "text",
    }    
    max_length = db.Column(db.Integer, default=80, nullable=False, index=True)
    max_content_length = db.Column(db.Integer, default=1024, nullable=False, index=True)
    softprompt = db.Column(db.String(255), default=None, nullable=False)


    def extract_params(self, params, **kwargs):
        self.n = params.pop('n', 1)
        self.jobs = self.n 
        self.max_length = params.get("max_length", 80)
        self.max_content_length = params.get("max_content_length", 1024)
        # To avoid unnecessary calculations, we do it once here.
        self.things = self.max_length
        # The total amount of to pixelsteps requested.
        self.total_usage = round(self.max_length * self.n / text_thing_divisor,2)
        self.models = kwargs.get("models", ['ReadOnly'])
        self.softprompt = kwargs.get("softprompt")
        self.prepare_job_payload(params)

    def calculate_kudos(self):
        self.kudos = 10
        db.session.commit()

    @logger.catch(reraise=True)
    def prepare_job_payload(self, initial_dict = None):
        '''Prepares the default job payload. This might be further adjusted per job in get_job_payload()'''
        if not initial_dict: initial_dict = {}
        self.gen_payload = initial_dict.copy()
        self.gen_payload["prompt"] = self.prompt
        self.gen_payload["n"] = 1
        db.session.commit()

    def activate(self, source_image = None, source_mask = None):
        # We separate the activation from __init__ as often we want to check if there's a valid worker for it
        # Before we add it to the queue
        super().activate()
        logger.info(f"New text2text prompt with ID {self.id} by {self.user.get_unique_alias()}: token:{self.max_length} * n:{self.n} == {self.total_usage} Total Tokens")

    def record_text_usage(self, raw_things, kudos):
        # This represents the cost of using the resources of the horde
        horde_tax = 1
        kudos += horde_tax
        super().record_text_usage(raw_things, kudos)

    # We can calculate the kudos in advance as they model doesn't affect them
    def calculate_kudos(self):
        result = pow((self.params.get('width', 512) * self.params.get('height', 512)) - (64*64), 1.75) / pow((1024*1024) - (64*64), 1.75)
        # We need to calculate the steps, without affecting the actual steps requested
        # because some samplers are effectively doubling their steps
        steps = self.get_accurate_steps()
        self.kudos = round((0.1232 * steps) + result * (0.1232 * steps * 8.75),2)
        # For each post processor in requested, we increase the cost by 20%
        for post_processor in self.gen_payload.get('post_processing', []):
            self.kudos = round(self.kudos * 1.2,2)
        db.session.commit()

    def log_faulted_prompt(self):
        source_processing = 'txt2img'
        if self.source_image:
            source_processing = self.source_processing
        logger.warning(f"Faulting waiting {source_processing} prompt {self.id} with payload '{self.gen_payload}' due to too many faulted jobs")

    def get_status(self, **kwargs):
        ret_dict = super().get_status(**kwargs)
        ret_dict["shared"] = self.shared
        return ret_dict
