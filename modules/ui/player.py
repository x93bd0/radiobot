from typing import Any
from pyrogram.types import (
    InlineKeyboardMarkup as IKM, InlineKeyboardButton as IKB,
    CallbackQuery
)

from pyrogram.handlers import CallbackQueryHandler
from pyrogram.client import Client
from pyrogram import filters

from pytgcalls.exceptions import NotInCallError
from pytgcalls.types import Call
from stub import MetaClient, MetaModule
import stub


class Module(MetaModule):
    i18n: MetaModule
    baseui: MetaModule
    player: MetaModule
    goodies: MetaModule
    ustorage: MetaModule

    buttons: dict[str, str]
    handlers: dict[str, CallbackQueryHandler]


    def __init__(self, client: MetaClient):
        self.identifier: str = 'PlayerUI'
        self.client: MetaClient= client

    async def setup(self) -> None:
        pass

    async def install(self) -> None:
        self.i18n, self.baseui, self.player, self.goodies, self.ustorage = \
            self.client.require_modules((
                'I18n', 'BaseUI', 'Player', 'Goodies', 'UStorage'))

        self.buttons = {
            'reload': self.goodies.get_callback_prefix(),
            'toggle': self.goodies.get_callback_prefix(),
            'next': self.goodies.get_callback_prefix(),
            'stop': self.goodies.get_callback_prefix(),
        }

        self.handlers = {
            'reload': CallbackQueryHandler(
                self.ustorage.c11e(self.reload, required=True),
                filters.regex(self.buttons['reload'])
            ),
            'toggle': CallbackQueryHandler(
                self.ustorage.c11e(self.toggle, required=True),
                filters.regex(self.buttons['toggle'])
            ),
            'next': CallbackQueryHandler(
                self.ustorage.c11e(self.next, required=True),
                filters.regex(self.buttons['next'])
            ),
            'stop': CallbackQueryHandler(
                self.ustorage.c11e(self.stop, required=True),
                filters.regex(self.buttons['stop'])
            )
        }

        for h in self.handlers.values():
            self.client.add_handler(h)


    async def post_install(self) -> None:
        pass


    async def player_init(self, context: 'stub.Context') -> None:
        song_data: 'stub.SongData'
        elapsed: int
        call: Call

        try:
            call = (await self.player.api.group_calls)[context.voice_id]
            elapsed = await self.player.api.played_time(
                context.voice_id)

            data: list['stub.SongData'] = await self.ustorage.pl_fetch(
                context.voice_id, limit=1,
                offset=(await self.ustorage.pl_position(context.voice_id)) - 1
            )

            if not data or len(data) == 0:
                raise NotInCallError()
            song_data = data[0]

        except NotInCallError:
            await self.goodies.update_status(
                context, self.i18n[context]['pl_novoice'])
            return

        is_playing: bool = call.status == Call.Status.PLAYING

        consts: dict[str, str] = self.i18n.consts
        kbd: IKM = IKM([
            [
                IKB(consts['reload'], self.buttons['reload']),
                IKB(
                    consts['pause' if is_playing else 'play'],
                    self.buttons['toggle']
                ),
                IKB(consts['next'], self.buttons['next'])
            ], [
                IKB(consts['stop'], self.buttons['stop']),
                IKB(consts['close'], self.baseui.close_prefix)
            ]
        ])

        await self.goodies.update_status(
            context, self.goodies.format_sd(
                context, song_data, elapsed=elapsed
            ), reply_markup=kbd
        )

    async def reload(
        self, _: Client,
        query: CallbackQuery,
        context: 'stub.Context'
    ) -> None:
        await self.player_init(context)
        await query.answer(
            self.i18n[context]['cpl_updated'])

    async def toggle(
        self, _: Client,
        query: CallbackQuery,
        context: 'stub.Context'
    ) -> None:
        call: Call
        try:
            call = (await self.player.api.group_calls)[context.voice_id]

        except NotInCallError:
            await query.answer(
                self.i18n[context]['cpl_unknownerr'])
            return

        if call.status == Call.Status.PLAYING:
            await self.player.pause(context)
            await query.answer(self.i18n[context]['cpl_paused'])
        
        else:
            await self.player.resume(context)
            await query.answer(self.i18n[context]['cpl_resumed'])
        await self.player_init(context)

    async def next(
        self, _: Client,
        query: CallbackQuery,
        context: 'stub.Context'
    ) -> None:
        await query.answer('Not implemented')

    async def stop(
        self, _: Client,
        query: CallbackQuery,
        context: 'stub.Context'
    ) -> None:
        await self.player.stop(context)
        await query.answer(self.i18n[context]['cpl_ended'])
        await self.goodies.update_status(
            context, self.i18n[context]['gpl_ended'],
            reply_markup=None
        )


    def stub(self, root: dict[str, Any]) -> None:
        pass
