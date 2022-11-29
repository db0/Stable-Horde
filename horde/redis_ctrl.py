import os
import socket
import redis

from horde.logger import logger

redis_hostname = os.getenv('REDIS_IP', "localhost")
redis_port = 6379
redis_address = f"redis://{redis_hostname}:{redis_port}"

horde_db = 0
limiter_db = 1
ipaddr_db = 2
cache_db = 3
ipaddr_supicion_db = 4
ipaddr_timeout_db = 5
logger.warning(f"Redis hostname is set to {redis_hostname}")
def is_redis_up() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((redis_hostname, redis_port)) == 0

def ger_limiter_url():
    return(f"{redis_address}/{limiter_db}")

def ger_cache_url():
    return(f"{redis_address}/{cache_db}")

def get_horde_db():
    rdb = redis.Redis(
        host=redis_hostname,
        port=redis_port,
        db = horde_db)
    return(rdb)

def get_ipaddr_db():
    logger.error(redis_hostname)
    rdb = redis.Redis(
        host=redis_hostname,
        port=redis_port,
        db = ipaddr_db)
    return(rdb)

def get_ipaddr_suspicion_db():
    rdb = redis.Redis(
        host=redis_hostname,
        port=redis_port,
        db = ipaddr_supicion_db)
    return(rdb)

def get_ipaddr_timeout_db():
    rdb = redis.Redis(
        host=redis_hostname,
        port=redis_port,
        db = ipaddr_timeout_db)
    return(rdb)
