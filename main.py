#!/usr/bin/env python

from ast import Dict
import asyncio
import logging
import os
from typing import  Coroutine, List
from weakref import ReferenceType, ref

from hummingbot import init_logging
from hummingbot.client.config.config_crypt import  ETHKeyFileSecretManger
from hummingbot.client.config.config_helpers import (
    create_yml_files_legacy,
    load_client_config_map_from_file,
    read_system_configs_from_yml,
)
from hummingbot.client.config.security import Security
from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.client.settings import  AllConnectorSettings
from hummingbot.core.event.events import HummingbotUIEvent
from hummingbot.core.utils.async_utils import safe_gather

from hummingbot.core.pubsub import PubSub

class HummingbotNoTTY(PubSub):
    def __init__(self, mainApp):
        super().__init__()
        self.mainApp = mainApp

    async def run(self):
        scriptname=os.getenv("SCRIPT")
        self.startStrategy(scriptname)
        while True:
            await asyncio.sleep(10)
    def startStrategy(self, script_name:str):
        logging.getLogger(__name__).info("startStrategy: {0}".format(script_name))
        self.mainApp.start(script=script_name, log_level="INFO", is_quickstart=True)            
    
    def log(self, text: str, save_log: bool = True):
        logging.getLogger(__name__).info(text)

    def change_prompt(self, prompt: str, is_password: bool = False):
        logging.getLogger(__name__).info("change_prompt: {0}".format(prompt))

    async def prompt(self, prompt: str, is_password: bool = False) -> str:
        logging.getLogger(__name__).info("prompt: {0}".format(prompt))
        return ""

    def handle_tab_command(self, hummingbot: "HummingbotApplication", command_name: str, kwargs: vars):
        logging.getLogger(__name__).info("handle_tab_command: {0}".format(command_name))

    def clear_input(self):
        logging.getLogger(__name__).info("clear_input")


async def main():
    client_config_map = load_client_config_map_from_file()

    secrets_manager = ETHKeyFileSecretManger("1")
    if not Security.login(secrets_manager):
        logging.getLogger().error("Invalid password.")
        return
   
    await Security.wait_til_decryption_done()
    await create_yml_files_legacy()
    init_logging("hummingbot_logs.yml", client_config_map)
    await read_system_configs_from_yml()

    AllConnectorSettings.initialize_paper_trade_settings(client_config_map.paper_trade.paper_trade_exchanges)

    hb = HummingbotApplication.main_application(client_config_map=client_config_map)
    hb.app = HummingbotNoTTY(hb)

    tasks: List[Coroutine] = [hb.run()]
    await safe_gather(*tasks)

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
