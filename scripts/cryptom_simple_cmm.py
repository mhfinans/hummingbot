import json
import logging
import os
import time
from decimal import Decimal
from typing import List

import redis

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
    TASK_ID=os.getenv("TASK_ID","task_id")
    config={}
    status={}
    wait_tick=0
        

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
                #self.logger().info("config is empty")
                #self.status["error"]="config is empty"
                return False
            else:
                json_str=json_str.decode("utf-8")
            
            if json is not None:
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
        return False
  
            
    def updateParams(self):
        if self.update_config():
            self.cancel_all_orders()
            os.environ["CRYPTOM_USER_ID"]=self.config["userId"]
            return True
        else:
            return False
    def on_tick(self):
        logging.getLogger(__name__).info("CMM: Tick")        
        if self.updateParams():
            logging.getLogger(__name__).info("update params success")
            return
        

        binanceprice=self.connectors[self.right_market].get_mid_price(self.trading_pair)
        try:
            if self.wait_tick>0:
                if self.left_active_orders()==0 and self.right_active_orders()==0:
                    self.wait_tick=0
                    return
                self.wait_tick-=1
                return

            self.cancel_all_orders()
            left_asks=self.get_left_asks()
            logging.getLogger(__name__).info("CMM: checking left_asks",left_asks)
            for ask in left_asks:
                bid=self.get_right_best_bid(ask)
                logging.getLogger(__name__).info("CMM:  checking right best ask {} bid {}",ask,bid)
                if ask and bid:
                    logging.getLogger(__name__).info("CMM: creating orders",ask,bid)
                    self.place_order(connector_name=self.left_market, order=self.create_proposal(ask))
                    self.place_order(connector_name=self.right_market, order=self.create_opposite_order(bid))
                    self.wait_tick=60
                    break
        except Exception as e:
            print(e)

        self.status["time"]=time.time()
        self.status["left_active_orders"]=self.left_active_orders()
        self.status["right_active_orders"]=self.right_active_orders()
        self.status["binance_mid_price"]=float(binanceprice)
        self.status["config"]=self.config

        self.update_status()
    
    def left_active_orders(self):
        count=len(self.get_active_orders(connector_name=self.left_market))
        return count
    def right_active_orders(self):
        count=len(self.get_active_orders(connector_name=self.right_market))
        return count
        
        
    def create_opposite_order(self,order):
        logging.getLogger(__name__).info("create_opposite_order",order)
        return OrderCandidate(trading_pair=self.trading_pair, is_maker=True, order_type=OrderType.LIMIT,
                                        order_side=TradeType.BUY, amount=Decimal(order.amount), price=Decimal(order.price))
        
    def create_proposal(self,order):
        logging.getLogger(__name__).info("create proposal",order)
        return OrderCandidate(trading_pair=self.trading_pair, is_maker=True, order_type=OrderType.LIMIT,
                                        order_side=TradeType.SELL, amount=Decimal(order.amount), price=Decimal(order.price))

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
        return self.get_left_order_book().ask_entries()
    
    
    def get_right_best_bid(self,ask):
        bids=self.get_right_order_book().bid_entries()
        diff=0
        min_bid= None
        for bid in bids:
            if (ask.price-(bid.price))>diff:
                diff=ask.price-(bid.price)
                min_bid=bid
            
        if min_bid is None:
            return None
        
        return min_bid
    
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