import json
import os
import redis
from redis.exceptions import RedisError


class RedisService:
    def __init__(self):
        self.r = None
        try:
            # Redis is disabled - uncomment and set env vars to enable
            # self.pool = redis.ConnectionPool(
            #     host=os.getenv("REDIS_HOST"),
            #     port=6380,
            #     db=0,
            #     password=os.getenv("REDIS_PASSWORD"),
            #     ssl=True,
            # )
            # self.r = redis.Redis(connection_pool=self.pool)
            pass
        except RedisError as err:
            print(err)

    def write_to_redis(self, key, value):
        self.r.set(key, json.dumps(value))

    def read_from_redis(self, key):
        return json.loads(self.r.get(key))

    def check_key_in_redis(self, key):
        return self.r.exists(key)
