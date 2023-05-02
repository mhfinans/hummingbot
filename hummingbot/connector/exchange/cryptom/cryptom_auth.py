import base64
import hashlib
import hmac
from collections import OrderedDict
from datetime import datetime
import logging
import os
from typing import Any, Dict, Optional
from urllib.parse import urlencode

from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest
from hummingbot.logger.logger import HummingbotLogger


class CryptomAuth(AuthBase):

    def __init__(self, api_key: str, secret_key: str, time_provider: TimeSynchronizer):
        self.api_key: str = api_key
        self.secret_key: str = secret_key
        self.time_provider: TimeSynchronizer = time_provider
        self._logger: Optional[HummingbotLogger] = None

    def logger(self) -> HummingbotLogger:
        if self._logger is None:
            self._logger = logging.getLogger(HummingbotLogger.logger_name_for_class(self.__class__))
        return self._logger

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Adds the server time and the signature to the request, required for authenticated interactions. It also adds
        the required parameter in the request header.

        :param request: the request to be configured for authenticated interaction

        :return: The RESTRequest with auth information included
        """

        userId=os.environ.get("CRYPTOM_USER_ID")
        if userId is None or userId == "":
            self.logger().exception("Cryptom user id is not set. Please set the CRYPTOM_USER_ID environment variable.")


        request.headers["X-User"] = userId
        request.headers["user-id"] =userId
        request.url=request.url.format(user_id=userId)

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        This method is intended to configure a websocket request to be authenticated. OKX does not use this
        functionality
        """
        return request  # pass-through
