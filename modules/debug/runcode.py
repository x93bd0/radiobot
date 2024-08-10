from pyrogram.types import Message, MessageEntity
from pyrogram.handlers import MessageHandler
from pyrogram.enums import MessageEntityType
from stub import MetaClient, MetaModule
from pyrogram.client import Client
from pyrogram import filters
from typing import Any
import traceback
import functools
import html
import stub


class Module(MetaModule):
    i18n: MetaModule
    goodies: MetaModule
    ustorage: MetaModule


    def __init__(self, client: MetaClient):
        self.identifier: str = 'Debug.RunCode'
        self.client: MetaClient = client

    async def setup(self) -> None:
        pass

    async def install(self) -> None:
        if self.client.debug:
            self.i18n, self.goodies, self.ustorage = self.client.require_modules((
                'I18n', 'Goodies', 'UStorage'))

            self.client.require_configuration(
                self, 'superadmin_id')

            self.client.add_handler(MessageHandler(
                self.ustorage.c11e(
                    self.runcode, auto_update=False,
                    required=False
                ),

                filters.private &
                filters.command('run')
            ))

    async def post_install(self) -> None:
        pass

    def internal_print(
        self, *args,
        buffer: list[str],
        sep: str = ' ',
        end: str = '\n',
    ) -> None:
        buffer.append(sep.join([str(x) for x in args]) + end)

    async def runcode(
        self, _: Client,
        message: Message,
        context: 'stub.Context'
    ) -> None:
        try:
            ent: MessageEntity
            for ent in message.entities:
                if ent.type != MessageEntityType.PRE:
                    continue

                buffer: list[str] = []
                gl: dict[str, Any] = globals().copy()
                gl['print'] = functools.partial(self.internal_print, buffer=buffer)

                lc: dict[str, Any] = {}
                code: str = message.text[ent.offset:ent.offset+ent.length]

                # a.k.a. Ready To Run CODE
                rtr_code: str = f'''
async def entry_point(self):
    {code.replace('\n', '\n    ')}
                '''

                exec(rtr_code, gl, lc)
                print(buffer)
                out: Any = await lc['entry_point'](self.client)
                fmt: str = html.escape(html.escape(str(out)))
                bufout: str = html.escape(html.escape(''.join(buffer)))

                await message.reply(
                    self.i18n[context]['rc_res'].format(fmt, bufout))

        except Exception:
            await message.reply(self.i18n[context]['rc_exc'].format(
                traceback.format_exc(),
            ))


    def stub(self, root: dict[str, Any]) -> None:
        pass