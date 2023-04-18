import asyncio
import time
from typing import TYPE_CHECKING, Any, Dict, Optional

from hummingbot.connector.exchange.cryptom import cryptom_constants as CONSTANTS
from hummingbot.connector.exchange.cryptom.cryptom_auth import CryptomAuth
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest, WSPlainTextRequest, WSResponse
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.connector.exchange.okx.okx_exchange import OkxExchange


class CryptomAPIUserStreamDataSource(UserStreamTrackerDataSource):

    _logger: Optional[HummingbotLogger] = None

    def __init__(
            self,
            auth: CryptomAuth,
            connector: 'CryptomExchange',
            api_factory: WebAssistantsFactory):
        super().__init__()
        self._auth: CryptomAuth = auth
        self._connector = connector
        self._api_factory = api_factory

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Creates an instance of WSAssistant connected to the exchange
        """
        mocking_assistant = NetworkMockingAssistant()
        ws: WSAssistant = mocking_assistant.create_websocket_mock()
        return ws        
    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        await asyncio.sleep(1)

    async def _process_websocket_messages(self, websocket_assistant: WSAssistant, queue: asyncio.Queue):
        while True:
            await asyncio.sleep(1)

    async def _process_event_message(self, event_message: Dict[str, Any], queue: asyncio.Queue):
        while True:
            await asyncio.sleep(1)
    @property
    def last_recv_time(self) -> float:
        return time.time()-100
    
    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant
