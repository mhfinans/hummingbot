from decimal import Decimal
from typing import Any, Dict

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

CENTRALIZED = True
EXAMPLE_PAIR = "ZRX-ETH"

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.001"),
    taker_percent_fee_decimal=Decimal("0.0015"),
    buy_percent_fee_deducted_from_returns=True
)


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information
    :param exchange_info: the exchange information for a trading pair
    :return: True if the trading pair is enabled, False otherwise
    """
    return True  # TODO: Change this later exchange_info.get("status", None) == "TRADING" and "SPOT" in exchange_info.get("permissions", list())


class CryptomConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="cryptom", const=True, client_data=None)
    cryptom_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Cryptom API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    cryptom_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Cryptom API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "cryptom"


KEYS = CryptomConfigMap.construct()

OTHER_DOMAINS = ["cryptom_io"]
OTHER_DOMAINS_PARAMETER = {"cryptom_io": "us"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"cryptom_io": "BTC-USDT"}
OTHER_DOMAINS_DEFAULT_FEES = {"cryptom_io": DEFAULT_FEES}


class CryptomIOConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="cryptom_io", const=True, client_data=None)
    cryptom_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Cryptom IO API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    cryptom_api_secret: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your Cryptom IO API secret",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "cryptom_io"


OTHER_DOMAINS_KEYS = {"cryptom_io": CryptomIOConfigMap.construct()}
