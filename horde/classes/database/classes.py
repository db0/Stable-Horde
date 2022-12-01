import time
import uuid
import json
from datetime import datetime, timedelta

from horde.logger import logger
from horde.vars import thing_name,thing_divisor

class FakeWPRow:
    def __init__(self,json_row):
        self.id = uuid.UUID(json_row["id"])
        self.things = json_row["things"]
        self.n = json_row["n"]
        self.extra_priority = json_row["extra_priority"]
        self.created = datetime.strptime(json_row["created"],"%Y-%m-%d %H:%M:%S")

# class WPCacheRefresh:
 
#     def __init__(self, interval ):
#         self.milestone()
 
#     def milestone(self):
#         self.start = time.monotonic()

#     def log(self):
#         logger.debuf(time.monotonic() - self.start)
 