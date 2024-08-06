"""
    Base User Interface
"""

from pyrogram.handlers import MessageHandler
from pyrogram.types import Message
from pyrogram import filters

from stub import MetaClient, MetaModule
import stub


class Module(MetaModule):
    """
    Base UI
    Add's common bot commands
    """

    i18n: MetaModule
    ustorage: MetaModule
    handlers: dict[str, MessageHandler]


    def __init__(self, client: MetaClient) -> None:
        self.identifier: str = 'BaseUI'
        self.client: MetaClient = client

    async def setup(self) -> None:
        pass

    async def install(self) -> None:
        pass

    async def post_install(self) -> None:
        self.i18n = self.client.modules['I18n']
        self.ustorage = self.client.modules['UStorage']

        common = filters.private
        self.handlers = {
            'start': MessageHandler(
                self.ustorage.Contextualize(self.start),
                common & filters.command('start')
            ),
            'help': MessageHandler(
                self.ustorage.Contextualize(self.help),
                common & filters.command('help')
            )
        }

        for h in self.handlers.values():
            self.client.add_handler(h)


    async def start(
        self, _,
        message: Message,
        context: 'stub.Context'
    ) -> None:
        await message.reply(self.i18n[context]['base_start'])
    
    async def help(
        self, _,
        message: 'Message',
        context: 'stub.Context'
    ) -> None:
        await message.reply(self.i18n[context]['base_help'])