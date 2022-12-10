import json

from horde.logger import logger
from horde.horde_redis import horde_r
from horde.threads import PrimaryTimedFunction


class PatreonCache(PrimaryTimedFunction):
    patrons = {}

    def call_function(self):
        try:
            self.patrons = json.loads(horde_r.get("patreon_cache"))
            # logger.debug(self.patrons)
        except TypeError:
            logger.warning("Patreon cache could not be retrieved from redis. Leaving existing cache.")

    def is_patron(self, user_id):
        return user_id in self.patrons

    def get_patrons(self, min_entitlement = 0, exact_entitlement = None):
        matching_patrons = {}
        for pid in self.patrons:
            if exact_entitlement is not None:
                if self.patrons[pid]["entitlement_amount"] == exact_entitlement:
                    matching_patrons[pid] = self.patrons[pid]
            elif self.patrons[pid]["entitlement_amount"] >= min_entitlement:
                matching_patrons[pid] = self.patrons[pid]
        return(matching_patrons)

    def get_ids(self, **kwargs):
        return list(self.get_patrons(**kwargs).keys())

    def get_names(self, **kwargs):
        return [p["name"] for p in self.get_sorted_patrons(**kwargs)]

    def get_sorted_patrons(self, **kwargs):
        all_patrons = self.get_patrons(**kwargs)
        return sorted(all_patrons.values(), key=lambda x: x["entitlement_amount"], reverse=True)

    def get_monthly_kudos(self, user_id):
        if not self.is_patron(user_id):
            return 0
        eamount = int(self.patrons[user_id]["entitlement_amount"] )
        if eamount == 25:
            return(300000)
        elif eamount == 10:
            return(50000)
        elif eamount < 10:
            return(eamount * 1000)
        else:
            logger.warning(f"Found patron '{user_id}' with non-standard entitlement: {eamount}")
            return(0)


patrons = PatreonCache(3600, None)
# We call it now to ensure the cache if full when the monthly kudos assignment is done because the thread take a second longer to fire than the import
patrons.call_function()