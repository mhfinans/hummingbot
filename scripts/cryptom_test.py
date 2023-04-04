from datetime import datetime
import json
import logging
import os
from hummingbot.client.settings import ConnectorSetting
from typing import Any, Dict, List, Set

from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
import redis

class CryptomTestExample(ScriptStrategyBase):
    """
    CRYTOM TEST SCRIPT
    """
    markets = {
#        "binance": {"ETH-USDT"},
    }
    count = 0
    status={}
    config={}
    def __init__(self,connectors: Dict[str, ConnectorSetting]):
        super().__init__(connectors)
        self.getParamsFromEnv()
        self.initRedisClient()
    
    def getParamsFromEnv(self):
        self.REDIS_URL=os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.TASK_ID=os.getenv("TASK_ID","task_id")

    def initRedisClient(self):
        self.redis_client = redis.Redis.from_url(self.REDIS_URL)
        if self.redis_client is None:
            logging.getLogger(__name__).error("Redis client is None")
    
    def push_status(self):
        try:
            self.redis_client.set(self.TASK_ID+"_status", json.dumps(self.status))
        except Exception as e:
            logging.getLogger(__name__).error("Error pushing task object to redis: {0}".format(e))
            return False
    
    def pop_config(self):
        try:
            json_str=self.redis_client.get(self.TASK_ID+"_config").decode("utf-8")
            if json is not None:
                self.config=json.loads(json_str)
                logging.getLogger(__name__).info("config: {0}".format(self.config))
           
        except Exception as e:
            logging.getLogger(__name__).error("Error pop task object to redis: {0}".format(e))
            return False        

    def on_tick(self):
        self.pop_config()
        logging.getLogger(__name__).debug("config {}".format(self.config))
        self.logger().info("CRYTPOM SCRIPT TEST IS OK")
        print("test {}",str(self.count))
        self.count += 1
        self.status["count"]=self.count
        self.status["time"]=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.status["config"]=self.config
        logging.getLogger(__name__).debug("status {}".format(self.status))
        self.push_status()
