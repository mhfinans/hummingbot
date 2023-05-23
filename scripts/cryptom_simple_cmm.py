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
    TASK_ID=os.getenv("TASK_ID","")
    config={}
    status={}
    order_timeout_second=10 
    process_interval=1
    
    forwardInFlights={}
    oppositeInFlights={}
    doneInFlights={}
        

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
        

    def on_tick(self):
        if int(time.time()) % self.process_interval>0:
            return

        #logging.getLogger(__name__).info("CMM: Tick")        
        if self.updateParams():
            logging.getLogger(__name__).info("update params success")
            return
        

        binancemidprice=self.connectors[self.right_market].get_mid_price(self.trading_pair)
        print("binance mid price: {}",binancemidprice)
        cryptommidprice=self.connectors[self.left_market].get_mid_price(self.trading_pair)
        try:
            newOrders=self.newOrdersFromLeft()
            bestRightOrder=None
            for newOrder in newOrders:
                if newOrder.order_type==OrderType.LIMIT:
                    bestRightOrder=self.get_right_best_order(newOrder)
                    if bestRightOrder is None:
                        continue
                    
                    self.createLimitForwardOrder(newOrder)
                
                elif newOrder.order_type==OrderType.MARKET:
                    self.createMarketForwardOrder(newOrder)


        except Exception as e:
            print(e)

        self.status["time"]=time.time()
        self.status["left_bot_orders_count"]=len(self.left_bot_orders())
        self.status["right_bot_orders_count"]=len(self.right_bot_orders())
        self.status["cryptom_mid_price"]=float(cryptommidprice)
        self.status["binance_mid_price"]=float(binancemidprice)
        self.status["config"]=self.config

        self.update_status()
    
    def isAsk(self,order):
        return order.trade_type==TradeType.SELL
        #else Bid
    
    
    def createLimitForwardOrder(self,source_order):
        order_client_id=self.place_order(connector_name=self.right_market, order=self.create_order(source_order.amount,source_order.price,OrderType.LIMIT,TradeType.SELL if self.isAsk(source_order) else TradeType.BUY))
        self.forwardInFlights[order_client_id]=source_order
    
    def createMarketForwardOrder(self,source_order):
        right_mid_price=self.connectors[self.right_market].get_mid_price(self.trading_pair)
        order_client_id=self.place_order(connector_name=self.right_market, order=self.create_order(source_order.amount,right_mid_price,OrderType.MARKET,TradeType.SELL if self.isAsk(source_order) else TradeType.BUY))
        self.forwardInFlights[order_client_id]=source_order
    
    def createOppositeOrder(self,source_order):
        order_client_id=self.place_order(connector_name=self.left_market, order=self.create_order(source_order.amount,source_order.price,source_order.order_type,TradeType.BUY if self.isAsk(source_order) else TradeType.SELL))
        self.oppositeInFlights[order_client_id]=source_order
    

   
    def  newOrdersFromLeft(self):
        result=[]
        all_left_orders=self.get_left_market_orders()
        for i_source_order in all_left_orders:
            doneOrderTime= self.doneInFlights.get(i_source_order.exchange_order_id,None)
            add=True
            if doneOrderTime is not None:
                if time.time()-doneOrderTime<60*10:
                    continue
                else:
                    del self.doneInFlights[i_source_order.exchange_order_id]
                
            for order_id,f_source_order in self.forwardInFlights.items():
                if i_source_order.exchange_order_id==f_source_order.exchange_order_id:
                    add=False
                    break
            for order_id,o_source_order in self.oppositeInFlights.items():
                if i_source_order.exchange_order_id==o_source_order.exchange_order_id:
                    add=False
                    break
            if add:
                result.append(i_source_order)
        logging.getLogger(__name__).info("new left orders: {}/{}".format(len(result),len(all_left_orders)))
        return result
         
    def left_bot_orders(self):
        return self.get_active_orders(connector_name=self.left_market)

    def right_bot_orders(self):
        return self.get_active_orders(connector_name=self.right_market)
        
        
    def create_order(self,amount,price,order_type,order_side):
        logging.getLogger(__name__).info("create_limit_order price:{} amount:{} order_side:{}".format(amount,price,order_side)),
        return OrderCandidate(trading_pair=self.trading_pair, is_maker=True, order_type=order_type,
                                        order_side=order_side, amount=Decimal(amount), price=Decimal(price))
        
   

    def get_right_order_book(self):
        return self.connectors[self.right_market].get_order_book(self.trading_pair)

    def get_left_market_orders(self):
        return self.connectors[self.left_market].order_book_tracker.data_source.AllMarketOrders

    
    
    
    def get_right_best_order(self,source_order):
        if self.isAsk(source_order):
            return self.get_right_best_bid(source_order.price,source_order.amount)
        else:
            return self.get_right_best_ask(source_order.price,source_order.amount)
    
    def get_right_best_bid(self,ref_price,ref_amount):
        bids=self.get_right_order_book().bid_entries()
        diff=0
        max_bid= None
        for bid in bids:
            if (bid.price-ref_price)>diff and ref_amount<=bid.amount:
                diff=ref_price-bid.price
                max_bid=bid
            
        return max_bid
        
    def get_right_best_ask(self,ref_price,ref_amount):
        asks=self.get_right_order_book().ask_entries()
        diff=0
        min_ask= None
        for ask in asks:
            if (ref_price-Decimal(ask.price))>diff and ref_amount<=Decimal(ask.amount):
                diff=ref_price-Decimal(ask.price)
                min_ask=ask
            
        return min_ask

    def place_order(self, connector_name: str, order: OrderCandidate):
        if order.order_side == TradeType.SELL:
            return self.sell(connector_name=connector_name, trading_pair=order.trading_pair, amount=order.amount,
                      order_type=order.order_type, price=order.price)
        elif order.order_side == TradeType.BUY:
            return self.buy(connector_name=connector_name, trading_pair=order.trading_pair, amount=order.amount,
                     order_type=order.order_type, price=order.price)
    
    def cancel_all_orders(self):
        for order in self.get_active_orders(connector_name=self.left_market):
            self.cancel(self.left_market, order.trading_pair, order.client_order_id)
        for order in self.get_active_orders(connector_name=self.right_market):
            self.cancel(self.right_market, order.trading_pair, order.client_order_id)
    
            
    def did_fill_order(self, order_filled_event: OrderFilledEvent):
        print("fill_order price:{} ",order_filled_event)
        
        source_order=self.forwardInFlights.get(order_filled_event.order_id,None)
        if source_order is not None:
            self.createOppositeOrder(source_order)
            del self.forwardInFlights[order_filled_event.order_id]
            return
        
        source_order=self.oppositeInFlights.get(order_filled_event.order_id,None)
        if source_order is not None:
            self.doneInFlights[source_order.exchange_order_id]=time.time()
            del self.oppositeInFlights[order_filled_event.order_id]
            return

        

    def did_create_sell_order(self, order_created_event: SellOrderCreatedEvent):
        logging.getLogger(__name__).info("create_sell_order price:{} amount:{} order_side:{}".format(order_created_event.order.price,order_created_event.order.amount,order_created_event.order.order_side))
    
    def did_fail_order(self, order_failed_event: MarketOrderFailureEvent):
        logging.getLogger(__name__).info("fail_order price:{} amount:{} order_side:{}".format(order_failed_event.order.price,order_failed_event.order.amount,order_failed_event.order.order_side))
    
    def did_cancel_order(self, cancelled_event: OrderCancelledEvent):
        logging.getLogger(__name__).info("cancel_order price:{} amount:{} order_side:{}".format(cancelled_event.order.price,cancelled_event.order.amount,cancelled_event.order.order_side))
    
    def did_expire_order(self, expired_event: OrderExpiredEvent):
        logging.getLogger(__name__).info("expire_order price:{} amount:{} order_side:{}".format(expired_event.order.price,expired_event.order.amount,expired_event.order.order_side))
    
    def did_complete_buy_order(self, order_completed_event: BuyOrderCompletedEvent):
        logging.getLogger(__name__).info("complete_buy_order price:{} amount:{} order_side:{}".format(order_completed_event.order.price,order_completed_event.order.amount,order_completed_event.order.order_side))
    
    def did_complete_sell_order(self, order_completed_event: SellOrderCompletedEvent):
        logging.getLogger(__name__).info("complete_sell_order price:{} amount:{} order_side:{}".format(order_completed_event.order.price,order_completed_event.order.amount,order_completed_event.order.order_side))
    
    def did_complete_funding_payment(self, funding_payment_completed_event: FundingPaymentCompletedEvent):
        logging.getLogger(__name__).info("complete_funding_payment price:{} amount:{} order_side:{}".format(funding_payment_completed_event.payment.amount,funding_payment_completed_event.payment.amount,funding_payment_completed_event.payment.order_side))
    
    def did_change_position_mode_succeed(self, position_mode_changed_event: PositionModeChangeEvent):
        logging.getLogger(__name__).info("change_position_mode_succeed price:{} amount:{} order_side:{}".format(position_mode_changed_event.new_position_mode,position_mode_changed_event.new_position_mode,position_mode_changed_event.new_position_mode))
    
    def did_change_position_mode_fail(self, position_mode_changed_event: PositionModeChangeEvent):
        logging.getLogger(__name__).info("change_position_mode_fail price:{} amount:{} order_side:{}".format(position_mode_changed_event.new_position_mode,position_mode_changed_event.new_position_mode,position_mode_changed_event.new_position_mode))
    
    def did_add_liquidity(self, add_liquidity_event: RangePositionLiquidityAddedEvent):
        logging.getLogger(__name__).info("add_liquidity price:{} amount:{} order_side:{}".format(add_liquidity_event.added_amount,add_liquidity_event.added_amount,add_liquidity_event.added_amount))
    
    def did_remove_liquidity(self, remove_liquidity_event: RangePositionLiquidityRemovedEvent):
        logging.getLogger(__name__).info("remove_liquidity price:{} amount:{} order_side:{}".format(remove_liquidity_event.removed_amount,remove_liquidity_event.removed_amount,remove_liquidity_event.removed_amount))
    
    def did_update_lp_order(self, update_lp_event: RangePositionUpdateEvent):
        logging.getLogger(__name__).info("update_lp_order price:{} amount:{} order_side:{}".format(update_lp_event.new_price,update_lp_event.new_price,update_lp_event.new_price))
    
    def did_fail_lp_update(self, fail_lp_update_event: RangePositionUpdateFailureEvent):
        logging.getLogger(__name__).info("fail_lp_update price:{} amount:{} order_side:{}".format(fail_lp_update_event.new_price,fail_lp_update_event.new_price,fail_lp_update_event.new_price))
    
    def did_collect_fee(self, collect_fee_event: RangePositionFeeCollectedEvent):
        logging.getLogger(__name__).info("collect_fee price:{} amount:{} order_side:{}".format(collect_fee_event.fee_amount,collect_fee_event.fee_amount,collect_fee_event.fee_amount))
    
    def did_close_position(self, closed_position_event: RangePositionClosedEvent):
        logging.getLogger(__name__).info("close_position price:{} amount:{} order_side:{}".format(closed_position_event.profit_loss,closed_position_event.profit_loss,closed_position_event.profit_loss))
     
    """
    def get_right_fee(self,order):
        base_currency = self.trading_pair.split("-")[0]
        quote_currency = self.trading_pair.split("-")[1]
        amount = order.amount
        price = order.price
        fee=self.connectors[self.right_market].get_fee(base_currency, quote_currency, OrderType.LIMIT_MAKER, TradeType.BUY, amount, price)
        return float(order.amount)*float(order.price)*float(fee.percent)
    """
    """
    def get_left_mid_price(self):
        return self.connectors[self.left_market].get_mid_price(self.trading_pair)
    """
    """
    def get_left_order_book(self):
        return self.connectors[self.left_market].get_order_book(self.trading_pair)
    """