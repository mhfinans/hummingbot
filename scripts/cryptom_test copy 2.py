import logging
from decimal import Decimal
from typing import List

from hummingbot.core.data_type.common import OrderType, PriceType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import BuyOrderCompletedEvent, BuyOrderCreatedEvent, FundingPaymentCompletedEvent, MarketOrderFailureEvent, OrderCancelledEvent, OrderExpiredEvent, OrderFilledEvent, PositionModeChangeEvent, RangePositionClosedEvent, RangePositionFeeCollectedEvent, RangePositionLiquidityAddedEvent, RangePositionLiquidityRemovedEvent, RangePositionUpdateEvent, RangePositionUpdateFailureEvent, SellOrderCompletedEvent, SellOrderCreatedEvent
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase



class SimpleCrossMM(ScriptStrategyBase):
    trading_pair = "ETH-USDT"
    right_market="binance"
    left_market="cryptom"
    markets = {left_market: {trading_pair},right_market: {trading_pair}}
    wait_tick=0
    def on_tick(self):
        binanceprice=self.connectors[self.right_market].get_mid_price(self.trading_pair)
        print("binance mid price",binanceprice)
        print("left active orders",self.left_active_orders())
        print("right active orders",self.right_active_orders())
        try:
            if self.wait_tick>0:
                if self.left_active_orders()==0 and self.right_active_orders()==0:
                    self.wait_tick=0
                    return
                self.wait_tick-=1
                return

            self.cancel_all_orders()
            left_asks=self.get_left_asks()
#            print(left_asks)
            for ask in left_asks:
                bid=self.get_right_best_bid(ask)
                print("+++++++++++++++++++++++++++++++++++++++++++++++++++")
                print("ask",ask)
                print("bid",bid)
                if ask and bid:
                    self.place_order(connector_name=self.left_market, order=self.create_proposal(ask))
                    self.place_order(connector_name=self.right_market, order=self.create_opposite_order(bid))
                    self.wait_tick=60
                    break

        except Exception as e:
            print(e)
    
    def left_active_orders(self):
        count=len(self.get_active_orders(connector_name=self.left_market))
        return count
    def right_active_orders(self):
        count=len(self.get_active_orders(connector_name=self.right_market))
        return count
        
        
    def create_opposite_order(self,order):
        print("create_opposite_order",order)
        return OrderCandidate(trading_pair=self.trading_pair, is_maker=True, order_type=OrderType.LIMIT,
                                        order_side=TradeType.BUY, amount=Decimal(order.amount), price=Decimal(order.price))
        
    def create_proposal(self,order):
        print("create proposal",order)
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
            spread=self.get_right_fee(bid)
            if (ask.price-(bid.price+spread))>diff:
                diff=ask.price-(bid.price+spread)
                min_bid=bid
            
        if min_bid is None:
            return None
        spread=self.get_right_fee(min_bid)
        print("best_bid_price",min_bid)
        
        return min_bid
    
    def place_order(self, connector_name: str, order: OrderCandidate):
        if order.order_side == TradeType.SELL:
            clientid=self.sell(connector_name=connector_name, trading_pair=order.trading_pair, amount=order.amount,
                      order_type=order.order_type, price=order.price)
            print("sell clientid",clientid)
        elif order.order_side == TradeType.BUY:
            clientid=self.buy(connector_name=connector_name, trading_pair=order.trading_pair, amount=order.amount,
                     order_type=order.order_type, price=order.price)
            print("buy clientid",clientid)
    def cancel_all_orders(self):
        for order in self.get_active_orders(connector_name=self.left_market):
            print("cancel",order)
            self.cancel(self.left_market, order.trading_pair, order.client_order_id)
        for order in self.get_active_orders(connector_name=self.right_market):
            print("cancel",order)
            self.cancel(self.right_market, order.trading_pair, order.client_order_id)