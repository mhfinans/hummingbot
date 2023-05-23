import asyncio
import json
import logging
import os
import time
from decimal import Decimal
from typing import List

import redis
from hummingbot.core.utils.async_utils import safe_ensure_future

from hummingbot.client.settings import ConnectorSetting
from hummingbot.core.data_type.common import OrderType, PriceType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    FundingPaymentCompletedEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderExpiredEvent,
    OrderFilledEvent,
    PositionModeChangeEvent,
    RangePositionClosedEvent,
    RangePositionFeeCollectedEvent,
    RangePositionLiquidityAddedEvent,
    RangePositionLiquidityRemovedEvent,
    RangePositionUpdateEvent,
    RangePositionUpdateFailureEvent,
    SellOrderCompletedEvent,
    SellOrderCreatedEvent,
)
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class CryptomSimpleCrossMM(ScriptStrategyBase):
    redis_client = None
    trading_pair = os.getenv("TRADING_PAIR")
    right_market=os.getenv("RIGHT_MARKET")
    left_market=os.getenv("LEFT_MARKET")
    markets = {left_market: {trading_pair},right_market: {trading_pair}}
    TASK_ID=os.getenv("TASK_ID","")
    config={}
    status={}
    order_timeout_second=10 
    process_interval=1
        

    def initRedisClient(self):
        if self.redis_client is None:
            self.redis_client = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))

    def update_status(self):
        try:
            self.initRedisClient()
            self.redis_client.set(self.TASK_ID+"_status", json.dumps(self.status))
        except Exception as e:
            logging.getLogger(__name__).error("Error update_status task object to redis: {0}".format(e))
            return False
    
    def update_config(self):
        try:
            self.initRedisClient()
            json_str=self.redis_client.get(self.TASK_ID+"_config")
            if json_str is None:
                self.logger().info("config is empty")
                #self.status["error"]="config is empty"
                return False
            else:
                json_str=json_str.decode("utf-8")
                
            
            config=json.loads(json_str)
            if self.check_config_and_update(config):
                self.config=config
                logging.getLogger(__name__).info("config: {0}".format(self.config))
                return True
            else:
                return False
                
           
        except Exception as e:
            logging.getLogger(__name__).error("Error update_config task object to redis: {0}".format(e))
            return False        
        
    def check_config_and_update(self,new):
        if self.config is None:
            return True
        if self.config.get("version","") !=new.get("version",""):
            return True
        return False
  
            
    def updateParams(self):
        if self.update_config():
            self.cancel_all_orders()
            os.environ["CRYPTOM_USER_ID"]=self.config["userId"]
            return True
        else:
            return False
        

    async def update_orders(self):
        cryptom = self.connectors[self.left_market]
        orders = await cryptom.get_all_orders("ETH-USDT")
        return orders

    def on_tick(self):
        try:
            print("do--------------------------------------------------")
            allorders=self.connectors[self.left_market].order_book_tracker.data_source.AllMarketOrders
            print("allorders",allorders)
            self.status["config"] = self.config
            self.update_status()
        except Exception as e:
            print(e)
    def clean_left_orders(self,timeout_second):
        left_orders=self.left_bot_orders()
        for order in left_orders:
            if order.time_created+timeout_second>time.time():
                self.cancel_order(self.left_market,order.client_order_id)
    def clean_right_orders(self,timeout_second):
        right_orders=self.right_bot_orders()
        for order in right_orders:
            if order.time_created+timeout_second>time.time():
                self.cancel_order(self.right_market,order.client_order_id)
            

    def createOppositeForAsk(self,ask,bid):
        self.place_order(connector_name=self.left_market, order=self.create_limit_order(ask.amount,ask.price,TradeType.SELL))
        self.place_order(connector_name=self.right_market, order=self.create_limit_order(ask.amount,bid.price,TradeType.BUY))
    
    def createOppositeForBid(self,ask,bid):
        self.place_order(connector_name=self.left_market, order=self.create_limit_order(bid.amount,bid.price,TradeType.BUY))
        self.place_order(connector_name=self.right_market, order=self.create_limit_order(bid.amount,ask.price,TradeType.SELL))


    def isAsk(self,order):
        return order.order_side==TradeType.SELL

   
    def  filterNotProcessedByBotInLeft(self,orders):
        result=[]
        leftbotorders=  [o.update_id for o in self.left_bot_orders()]
        for order in orders:
            if order.orderId not in leftbotorders:
                result.append(order)
        return result
         
    def left_bot_orders(self):
        return self.get_active_orders(connector_name=self.left_market)

    def right_bot_orders(self):
        return self.get_active_orders(connector_name=self.right_market)
        
        
    def create_limit_order(self,amount,price,order_side):
        logging.getLogger(__name__).info("create_limit_order price:{} amount:{} order_side:{}".format(amount,price,order_side)),
        return OrderCandidate(trading_pair=self.trading_pair, is_maker=True, order_type=OrderType.LIMIT,
                                        order_side=order_side, amount=Decimal(amount), price=Decimal(price))
        
    
    def get_right_fee(self,order):
        base_currency = self.trading_pair.split("-")[0]
        quote_currency = self.trading_pair.split("-")[1]
        amount = order.amount
        price = order.price
        fee=self.connectors[self.right_market].get_fee(base_currency, quote_currency, OrderType.LIMIT_MAKER, TradeType.BUY, amount, price)
        return float(order.amount)*float(order.price)*float(fee.percent)
   
    def get_left_mid_price(self):
        return self.connectors[self.left_market].get_mid_price(self.trading_pair)

    def get_left_order_book(self):
        return self.connectors[self.left_market].get_order_book(self.trading_pair)
    
    def get_right_order_book(self):
        return self.connectors[self.right_market].get_order_book(self.trading_pair)

    def get_right_best_bid(self):
        return self.connectors[self.right_market].get_price_by_type(self.trading_pair, PriceType.BestBid)

    def get_left_asks(self):
        return self.connectors[self.left_market]
    
    
    def get_right_best_bid(self,ask):
        bids=self.get_right_order_book().bid_entries()
        diff=0
        min_bid= None
        for bid in bids:
            if (ask.price-(bid.price))>diff and ask.amount<=bid.amount:
                diff=ask.price-(bid.price)
                min_bid=bid
            
        return min_bid
    
    def get_right_best_ask(self,bid):
        asks=self.get_right_order_book().ask_entries()
        diff=0
        min_ask= None
        for ask in asks:
            if (bid.price-(ask.price))>diff and bid.amount<=ask.amount:
                diff=bid.price-(ask.price)
                min_ask=bid
            
        return min_ask

    def place_order(self, connector_name: str, order: OrderCandidate):
        if order.order_side == TradeType.SELL:
            clientid=self.sell(connector_name=connector_name, trading_pair=order.trading_pair, amount=order.amount,
                      order_type=order.order_type, price=order.price)
        elif order.order_side == TradeType.BUY:
            clientid=self.buy(connector_name=connector_name, trading_pair=order.trading_pair, amount=order.amount,
                     order_type=order.order_type, price=order.price)
    
    def cancel_all_orders(self):
        for order in self.get_active_orders(connector_name=self.left_market):
            self.cancel(self.left_market, order.trading_pair, order.client_order_id)
        for order in self.get_active_orders(connector_name=self.right_market):
            self.cancel(self.right_market, order.trading_pair, order.client_order_id)