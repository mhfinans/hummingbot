import sys

from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.in_flight_order import OrderState

CLIENT_ID_PREFIX = "93027a12dac34fBC"
MAX_ID_LEN = 32
SECONDS_TO_WAIT_TO_RECEIVE_MESSAGE = 30 * 0.8

DEFAULT_DOMAIN = ""

# URLs

CRYPTOM_BASE_URL = ""

# Doesn't include base URL as the tail is required to generate the signature

CRYPTOM_SERVER_TIME_PATH = '/api/v1/public/time'
CRYPTOM_TICKER_PATH = 'https://testnet.binance.vision/api/v3/ticker/24hr'

CRYPTOM_INSTRUMENTS_PATH = 'http://assets:9007/assets'
CRYPTOM_ORDER_BOOK_PATH = 'http://orders:9001/orders'


CRYPTOM_PLACE_ORDER_PATH = "http://orders:9001/orders"
CRYPTOM_ORDER_DETAILS_PATH = 'http://orders:9001/orders'
CRYPTOM_ORDER_CANCEL_PATH = 'http://orders:9001/orders'
CRYPTOM_BALANCE_PATH = 'http://wallets:9004/wallets?$user_id=eq@{user_id}'
CRYPTOM_TRADE_FILLS_PATH = "http://trades:9002/trades"


CRYPTOM_STATUS_ORDER_PROCESSING = 1
CRYPTOM_STATUS_ORDER_DONE = 2
CRYPTOM_STATUS_ORDER_PARTIAL = 3
CRYPTOM_STATUS_ORDER_CANCEL = 4


CRYPTOM_WS_ACCOUNT_CHANNEL = "account"
CRYPTOM_WS_ORDERS_CHANNEL = "orders"
CRYPTOM_WS_PUBLIC_TRADES_CHANNEL = "trades"
CRYPTOM_WS_PUBLIC_BOOKS_CHANNEL = "books"

CRYPTOM_WS_CHANNELS = {
    CRYPTOM_WS_ACCOUNT_CHANNEL,
    CRYPTOM_WS_ORDERS_CHANNEL
}

WS_CONNECTION_LIMIT_ID = "WSConnection"
WS_REQUEST_LIMIT_ID = "WSRequest"
WS_SUBSCRIPTION_LIMIT_ID = "WSSubscription"
WS_LOGIN_LIMIT_ID = "WSLogin"
""""
1 = OPEN
2 = FILLED
3 = PARTIAL 
4 = CANCELLED
"""
ORDER_STATE = {
    "1": OrderState.OPEN,
    "2": OrderState.FILLED,
    "3": OrderState.PARTIALLY_FILLED,
    "4": OrderState.CANCELED,
}

NO_LIMIT = sys.maxsize

RATE_LIMITS = [
    RateLimit(WS_CONNECTION_LIMIT_ID, limit=1, time_interval=1),
    RateLimit(WS_REQUEST_LIMIT_ID, limit=100, time_interval=10),
    RateLimit(WS_SUBSCRIPTION_LIMIT_ID, limit=240, time_interval=60 * 60),
    RateLimit(WS_LOGIN_LIMIT_ID, limit=1, time_interval=15),
    RateLimit(limit_id=CRYPTOM_SERVER_TIME_PATH, limit=10, time_interval=2),
    RateLimit(limit_id=CRYPTOM_INSTRUMENTS_PATH, limit=20, time_interval=2),
    RateLimit(limit_id=CRYPTOM_TICKER_PATH, limit=20, time_interval=2),
    RateLimit(limit_id=CRYPTOM_ORDER_BOOK_PATH, limit=20, time_interval=2),
    RateLimit(limit_id=CRYPTOM_PLACE_ORDER_PATH, limit=60, time_interval=2),
    RateLimit(limit_id=CRYPTOM_ORDER_DETAILS_PATH, limit=60, time_interval=2),
    RateLimit(limit_id=CRYPTOM_ORDER_CANCEL_PATH, limit=60, time_interval=2),
    RateLimit(limit_id=CRYPTOM_BALANCE_PATH, limit=10, time_interval=2),
    RateLimit(limit_id=CRYPTOM_TRADE_FILLS_PATH, limit=60, time_interval=2), 
]
