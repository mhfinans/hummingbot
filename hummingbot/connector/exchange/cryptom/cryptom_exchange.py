import asyncio
import datetime
from ast import excepthandler
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.exchange.bitfinex import OrderStatus
from hummingbot.connector.exchange.cryptom import (
    cryptom_constants as CONSTANTS,
    cryptom_utils,
    cryptom_web_utils as web_utils,
)
from hummingbot.connector.exchange.cryptom.cryptom_api_order_book_data_source import CryptomAPIOrderBookDataSource
from hummingbot.connector.exchange.cryptom.cryptom_api_user_stream_data_source import CryptomAPIUserStreamDataSource
from hummingbot.connector.exchange.cryptom.cryptom_auth import CryptomAuth
from hummingbot.connector.exchange_base import s_decimal_NaN
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class CryptomExchange(ExchangePyBase):
    web_utils = web_utils

    def __init__(self,
                 client_config_map: "ClientConfigAdapter",
                 cryptom_api_key: str,
                 cryptom_api_secret: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True):
        self._cryptom_api_key = cryptom_api_key
        self._cryptom_api_secret = cryptom_api_secret
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        super().__init__(client_config_map)

    @property
    def authenticator(self):
        return CryptomAuth(
            api_key=self._cryptom_api_key,
            secret_key=self._cryptom_api_secret,
            time_provider=self._time_synchronizer)

    @property
    def name(self) -> str:
        return "cryptom"

    @property
    def rate_limits_rules(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self):
        return ""

    @property
    def client_order_id_max_length(self):
        return CONSTANTS.MAX_ID_LEN

    @property
    def client_order_id_prefix(self):
        return CONSTANTS.CLIENT_ID_PREFIX

    @property
    def trading_rules_request_path(self):
        return CONSTANTS.CRYPTOM_INSTRUMENTS_PATH

    @property
    def trading_pairs_request_path(self):
        return CONSTANTS.CRYPTOM_INSTRUMENTS_PATH

    @property
    def check_network_request_path(self):
        return CONSTANTS.CRYPTOM_SERVER_TIME_PATH

    @property
    def trading_pairs(self):
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return False

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    def supported_order_types(self):
        return [OrderType.MARKET,OrderType.LIMIT]

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        error_description = str(request_exception)
        is_time_synchronizer_related = '"code":"50113"' in error_description
        return is_time_synchronizer_related

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            auth=self._auth)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return CryptomAPIOrderBookDataSource(
            trading_pairs=self.trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory)

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return CryptomAPIUserStreamDataSource(
            auth=self._auth,
            connector=self,
            api_factory=self._web_assistants_factory)

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> TradeFeeBase:

        is_maker = is_maker or (order_type is OrderType.LIMIT)
        return build_trade_fee(
            base_currency=base_currency,
            quote_currency=quote_currency,
            order_type=order_type,
            order_side=order_side,
            amount=amount,
            price=price,
            is_maker=is_maker)
    
        

    async def _initialize_trading_pair_symbol_map(self):
        try:
            exchange_info = await self._api_get(
                path_url=self.trading_pairs_request_path,
                overwrite_url=self.trading_pairs_request_path,
                params={},
            )
            self._initialize_trading_pair_symbols_from_exchange_info(exchange_info=exchange_info)
        except Exception as e:
            self.logger().exception("There was an error requesting exchange info.", exc_info=e)
    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        for symbol_data in exchange_info["result"]:
            mapping[symbol_data["name"]] = symbol_data["name"]
            
        self._set_trading_pair_symbol_map(mapping)

    async def _place_order(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           trade_type: TradeType,
                           order_type: OrderType,
                           price: Decimal,
                           **kwargs) -> Tuple[str, float]:

        data = {
            "type": 1,#LIMIT
            "side": 1 if trade_type.name.lower() == "buy" else 0,
            "market": trading_pair,
            "quantity": float(amount),
            "price": float(price),
        }
        exchange_order_id={}
        try:
            exchange_order_id = await self._api_request(
                path_url=CONSTANTS.CRYPTOM_PLACE_ORDER_PATH,
                method=RESTMethod.POST,
                data=data,
                is_auth_required=True,
            )
        except Exception as ex:
            raise IOError(f"Error submitting order {order_id}: {ex.args[0]}")

        data = exchange_order_id["result"]
        return data["orderId"], self.current_timestamp

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        if tracked_order.exchange_order_id is None:
            raise ValueError(f"Cannot cancel order {order_id} - no exchange order ID.")
        """
        This implementation specific function is called by _cancel, and returns True if successful
        """
        try:
            cancel_result =  await self._api_request(
                path_url=CONSTANTS.CRYPTOM_ORDER_CANCEL_PATH,
                overwrite_url=CONSTANTS.CRYPTOM_ORDER_CANCEL_PATH+"/"+str(tracked_order.exchange_order_id),
                method=RESTMethod.DELETE,
                is_auth_required=True,
                data={},
                params={},
            )
        except Exception as ex:
            raise IOError(f"Error submitting order {order_id}: {ex.args[0]}")

        if cancel_result["result"]["orderId"]!=tracked_order.exchange_order_id:
            raise IOError(f"Error cancelling order {order_id}: {cancel_result}")

        return True

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        try:
            exchange_symbol = trading_pair.replace("-", "")
            params = {"symbol": exchange_symbol}
            response = await self._api_get(
                path_url=CONSTANTS.CRYPTOM_TICKER_PATH,
                params=params)
            price = float(response["lastPrice"])
        except Exception as ex:
            raise IOError(f"Error fetching last traded price for {trading_pair}: {excepthandler.args[0]}")
        return price

    async def _update_balances(self):
        try:
            msg = await self._api_request(
                path_url=CONSTANTS.CRYPTOM_BALANCE_PATH,
                method=RESTMethod.GET,
                is_auth_required=True)
        except Exception as ex:            
            raise IOError(f"Error fetching balances: {ex.args[0]}")

        balances = msg['result'][0]['assets']

        self._account_available_balances.clear()
        self._account_balances.clear()

        for balance in balances:
            self._update_balance_from_details(balance_details=balance)

    def _update_balance_from_details(self, balance_details: Dict[str, Any]):
        available = Decimal(balance_details["availableAmount"])
        total = available + Decimal(balance_details["freezeAmount"])
        self._account_balances[balance_details["assetName"]] = total
        self._account_available_balances[balance_details["assetName"]] = available

    async def _update_trading_rules(self):
        # This has to be reimplemented because the request requires an extra parameter
        exchange_info = await self._api_get(
            path_url=self.trading_rules_request_path,
            params={},
        )
        trading_rules_list = await self._format_trading_rules(exchange_info)
        self._trading_rules.clear()
        for trading_rule in trading_rules_list:
            self._trading_rules[trading_rule.trading_pair] = trading_rule
        self._initialize_trading_pair_symbols_from_exchange_info(exchange_info=exchange_info)

    async def _format_trading_rules(self, raw_trading_pair_info: List[Dict[str, Any]]) -> List[TradingRule]:
        trading_rules = []

        for info in raw_trading_pair_info.get("result", []):
            try:
                if cryptom_utils.is_exchange_information_valid(exchange_info=info):
                    trading_pair=info["name"]
                    quantityFilterMin=Decimal(info["quantityFilterMin"])
                    priceFilterStepSize=Decimal(info["priceFilterStepSize"])
                    quantityFilterStepSize=Decimal(info["quantityFilterStepSize"])
                    rule= TradingRule(
                            trading_pair=trading_pair,
                            min_order_size=Decimal(quantityFilterMin),
                            min_price_increment=Decimal(priceFilterStepSize),
                            min_base_amount_increment=Decimal(quantityFilterStepSize),
                        )
                    trading_rules.append(rule)
            except Exception as ex:
                self.logger().exception(f"Error parsing the trading pair rule {info}. Skipping.")
        return trading_rules

    async def _update_trading_fees(self):
        """
        Update fees information from the exchange
        """
        pass

    async def _request_order_update(self, order: InFlightOrder) -> Dict[str, Any]:
        orderId=await order.get_exchange_order_id()
        
        return await self._api_request(
            method=RESTMethod.GET,
            path_url=CONSTANTS.CRYPTOM_ORDER_DETAILS_PATH,
            params={
                    "$order_id":"eq@{}".format(orderId),
                    },
            is_auth_required=True)

    async def _request_order_fills(self, order: InFlightOrder) -> Dict[str, Any]:
        order_id=await order.get_exchange_order_id()
        return await self._api_request(
            method=RESTMethod.GET,
            path_url=CONSTANTS.CRYPTOM_TRADE_FILLS_PATH,
            params={
                "$order_id": "eq@{}".format(order_id),
                },
            is_auth_required=True)

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []

        if order.exchange_order_id is not None:
            try:
                all_fills_response = await self._request_order_fills(order=order)
                fills_data = all_fills_response["result"]
                percent_token=(await self.exchange_symbol_associated_to_pair(order.trading_pair))
                percent_token=percent_token.split("-")[0]
                for fill_data in fills_data:
                    fee = TradeFeeBase.new_spot_fee(
                        fee_schema=self.trade_fee_schema(),
                        trade_type=order.trade_type,
                        percent_token=percent_token,
                        flat_fees=[TokenAmount(amount=Decimal(fill_data["commission"]), token=percent_token)]
                    )
                     
                  
                    timestamp=datetime.datetime.fromisoformat(fill_data["updatedAt"].replace("Z",""))
                    trade_update = TradeUpdate(
                        trade_id=str(fill_data["id"]),
                        client_order_id=order.client_order_id,
                        exchange_order_id=str(fill_data["orderId"]),
                        trading_pair=order.trading_pair,
                        fee=fee,
                        fill_base_amount=Decimal(sum(Decimal(d['quantity']) for d in fill_data['done'] if d['side'] == 'buy')),
                        fill_quote_amount=Decimal(sum(Decimal(d['quantity']) * Decimal(d['price']) for d in fill_data['done'] if d['side'] == 'sell')),
                        fill_price=Decimal(fill_data["done"][0]["price"]),
                        fill_timestamp=timestamp.timestamp(),
                    )
                    trade_updates.append(trade_update)
            except IOError as ex:
                if not self._is_request_exception_related_to_time_synchronizer(request_exception=ex):
                    raise

        return trade_updates

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        try:
            updated_order_data = await self._request_order_update(order=tracked_order)

            order_data = updated_order_data["result"][0]
            new_state = CONSTANTS.ORDER_STATE[str(order_data["status"])]
            timestamp=datetime.datetime.fromisoformat(order_data["updatedAt"].replace("Z",""))
            order_update = OrderUpdate(
                client_order_id=tracked_order.client_order_id,
                exchange_order_id=str(order_data["orderId"]),
                trading_pair=tracked_order.trading_pair,
                update_timestamp=timestamp,
                new_state=new_state,
            )

        except IOError as ex:
            if self._is_request_exception_related_to_time_synchronizer(request_exception=ex):
                order_update = OrderUpdate(
                    client_order_id=tracked_order.client_order_id,
                    trading_pair=tracked_order.trading_pair,
                    update_timestamp=self.current_timestamp,
                    new_state=tracked_order.current_state,
                )
            else:
                raise

        return order_update

    async def _user_stream_event_listener(self):
        async for stream_message in self._iter_user_event_queue():
            try:
                args = stream_message.get("arg", {})
                channel = args.get("channel", None)

                if channel == CONSTANTS.CRYPTOM_WS_ORDERS_CHANNEL:
                    for data in stream_message.get("data", []):
                        order_status = CONSTANTS.ORDER_STATE[data["state"]]
                        client_order_id = data["clOrdId"]
                        fillable_order = self._order_tracker.all_fillable_orders.get(client_order_id)
                        updatable_order = self._order_tracker.all_updatable_orders.get(client_order_id)

                        if (fillable_order is not None
                                and order_status in [OrderState.PARTIALLY_FILLED, OrderState.FILLED]):
                            fee = TradeFeeBase.new_spot_fee(
                                fee_schema=self.trade_fee_schema(),
                                trade_type=fillable_order.trade_type,
                                percent_token=data["fillFeeCcy"],
                                flat_fees=[TokenAmount(amount=Decimal(data["fillFee"]), token=data["fillFeeCcy"])]
                            )
                            trade_update = TradeUpdate(
                                trade_id=str(data["tradeId"]),
                                client_order_id=fillable_order.client_order_id,
                                exchange_order_id=str(data["ordId"]),
                                trading_pair=fillable_order.trading_pair,
                                fee=fee,
                                fill_base_amount=Decimal(data["fillSz"]),
                                fill_quote_amount=Decimal(data["fillSz"]) * Decimal(data["fillPx"]),
                                fill_price=Decimal(data["fillPx"]),
                                fill_timestamp=int(data["uTime"]) * 1e-3,
                            )
                            self._order_tracker.process_trade_update(trade_update)

                        if updatable_order is not None:
                            order_update = OrderUpdate(
                                trading_pair=updatable_order.trading_pair,
                                update_timestamp=int(data["uTime"]) * 1e-3,
                                new_state=order_status,
                                client_order_id=updatable_order.client_order_id,
                                exchange_order_id=str(data["ordId"]),
                            )
                            self._order_tracker.process_order_update(order_update=order_update)

                elif channel == CONSTANTS.CRYPTOM_WS_ACCOUNT_CHANNEL:
                    for data in stream_message.get("data", []):
                        for details in data.get("details", []):
                            self._update_balance_from_details(balance_details=details)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in user stream listener loop.")
                await self._sleep(5.0)
