"""
    Base User Interface
"""

from typing import Any

from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.types import Message, CallbackQuery
from pyrogram import filters

from stub import MetaClient, MetaModule
import stub


class Module(MetaModule):
    """
    Base UI
    Add's common bot commands
    """

    i18n: MetaModule
    goodies: MetaModule
    ustorage: MetaModule

    close_prefix: str
    handlers: dict[str, MessageHandler | CallbackQueryHandler]


    def __init__(self, client: MetaClient) -> None:
        self.identifier: str = 'BaseUI'
        self.client: MetaClient = client

    async def setup(self) -> None:
        pass

    async def install(self) -> None:
        pass

    async def post_install(self) -> None:
        self.i18n, self.goodies, self.ustorage = \
            self.client.require_modules((
                'I18n', 'Goodies', 'UStorage'))
        self.close_prefix = self.goodies.get_callback_prefix()

        common = filters.private
        self.handlers = {
            'start': MessageHandler(
                self.ustorage.c11e(self.start),
                common & filters.command('start')
            ),
            'help': MessageHandler(
                self.ustorage.c11e(self.help),
                common & filters.command('help')
            ),
            'close_cbk': CallbackQueryHandler(
                self.close,
                filters.regex(self.close_prefix)
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
        message: Message,
        context: 'stub.Context'
    ) -> None:
        await message.reply(self.i18n[context]['base_help'])

    async def close(
        self, _,
        query: CallbackQuery
    ) -> None:
        await query.message.delete()


    def stub(self, root: dict[str, Any]) -> None:
        pass