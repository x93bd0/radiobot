"""
    Group User Interface
"""

from typing import Optional
from pytgcalls.exceptions import NotInCallError, NoActiveGroupCall
from pyrogram.handlers.message_handler import MessageHandler
from pyrogram.types import Message
from pyrogram import filters
import validators

from stub import MetaClient, MetaModule
import stub


class Module(MetaModule):
    """
    Group UI Module
    Add's usseful commands for
    group interaction
    """

    i18n: MetaModule
    player: MetaModule
    goodies: MetaModule
    ustorage: MetaModule

    player_status: object
    handlers: dict[str, MessageHandler]


    def __init__(self, client: MetaClient):
        self.identifier = 'GroupUI'
        self.client: MetaClient = client

    async def setup(self) -> None:
        pass

    async def install(self):
        pass

    async def post_install(self):
        self.i18n = self.client.modules['I18n']
        self.player = self.client.modules['Player']
        self.goodies = self.client.modules['Goodies']
        self.ustorage = self.client.modules['UStorage']

        self.player_status = self.player.player_status

        common = filters.group
        self.handlers = {
            'play': MessageHandler(
                self.ustorage.c11e(
                    self.ustorage.use_lock(self.play),
                    auto_update=False),
                filters.command('play') & common
            ),
            'pause': MessageHandler(
                self.ustorage.c11e(
                    self.ustorage.use_lock(self.pause)),
                filters.command('pause') & common
            ),
            'resume': MessageHandler(
                self.ustorage.c11e(
                    self.ustorage.use_lock(self.resume)),
                filters.command('resume') & common
            ),
            'next': MessageHandler(
                self.ustorage.c11e(
                    self.ustorage.use_lock(self.next)),
                filters.command('next') & common
            ),
            'volume': MessageHandler(
                self.ustorage.c11e(
                    self.ustorage.use_lock(self.volume)),
                filters.command('volume') & common
            ),
            'stop': MessageHandler(
                self.ustorage.c11e(
                    self.ustorage.use_lock(self.stop)),
                filters.command('stop') & common
            ),
            'status': MessageHandler(
                self.ustorage.c11e(
                    self.ustorage.use_lock(self.status)),
                filters.command('status') & common
            ),
            'playlist': MessageHandler(
                self.ustorage.c11e(
                    self.ustorage.use_lock(self.playlist)),
                filters.command('playlist') & common
            )
        }

        for h in self.handlers.values():
            self.client.add_handler(h)


    async def play(
        self, _, message: Message, context: 'stub.Context'
    ) -> None:
        if not context.voice_id:
            context.voice_id = message.chat.id

        if message.text.count(' ') == 0:
            await self.goodies.update_status(
                context, self.i18n[context]['gpl_nopayload'])
            return

        url: str = message.text.split(' ', 1)[1]
        if not validators.url(url):
            await self.goodies.update_status(
                context, self.i18n[context]['gpl_invalidurl'])
            return

        await self.goodies.update_status(
            context, self.i18n[context]['gpl_fetchingsd'])

        sdata: 'stub.SongData' = await self.goodies.song_from_url(url)
        sdata.url = url

        status: object = self.player_status
        async for upd in self.player.play(context, sdata):
            match upd:
                case status.ENQUEUED:
                    await self.goodies.update_status(
                        context, self.i18n[context]['pl_enqueued'].format(
                            self.goodies.format_sd(
                                context, sdata, key='gd_simpledata')))

                case status.GENERATING_CHAT_LINK:
                    await self.goodies.update_status(
                        context, self.i18n[context]['pl_glink'])

                case status.JOINING:
                    await self.goodies.update_status(
                        context, self.i18n[context]['pl_joining'])

                case status.OK:
                    await self.ustorage.ctx_upd(context)
                    await self.player.status(context)
                    break

                case status.CANT_GENERATE_LINK:
                    await self.goodies.update_status(
                        context, self.i18n[context]['pl_cglink'])
                    break

                case status.CANT_JOIN:
                    await self.goodies.update_status(
                        context, self.i18n[context]['pl_cjoin'])
                    break

                case status.NO_VOICE:
                    await self.goodies.update_status(
                        context, self.i18n[context]['pl_novoice'])
                    break

                case status.UNKNOWN_ERROR:
                    await self.goodies.update_status(
                        context, self.i18n[context]['pl_retry'])
                    break

    async def pause(
        self, _, __, context: 'stub.Context'
    ) -> Optional[bool]:
        if not context.voice_id:
            await self.goodies.update_status(
                context, self.i18n[context]['pl_novoice'])
            return False

        try:
            await self.player.pause(context)
            await self.goodies.update_status(
                context, self.i18n[context]['gpl_paused'])

        except NotInCallError:
            await self.goodies.update_status(
                context, self.i18n[context]['pl_novoice'])
            return False

    async def resume(
        self, _, __, context: 'stub.Context'
    ) -> Optional[bool]:
        if not context.voice_id:
            await self.goodies.update_status(
                context, self.i18n[context]['pl_novoice'])
            return False

        try:
            await self.player.resume(context)
            await self.goodies.update_status(
                context, self.i18n[context]['gpl_resumed'])

        except NotInCallError:
            await self.goodies.update_status(
                context, self.i18n[context]['pl_novoice'])
            return False

    async def next(
        self, _, __, context: 'stub.Context'
    ) -> Optional[bool]:
        if not context.voice_id:
            await self.goodies.update_status(
                context, self.i18n[context]['pl_novoice'])
            return False

        try:
            await self.player.next(context)

        except NotInCallError:
            await self.goodies.update_status(
                context, self.i18n[context]['pl_novoice'])
            return False

    async def volume(
        self, _, message: Message, context: 'stub.Context'
    ) -> Optional[bool]:
        if not context.voice_id:
            await self.goodies.update_status(
                context, self.i18n[context]['pl_novoice'])
            return False

        if message.text.count(' ') == 0:
            await self.goodies.update_status(
                context, self.i18n[context]['gpl_volvale'])
            return

        ctx: str = message.text.split(' ', 1)[1]
        try:
            await self.player.api.change_volume_call(
                context.voice_id, int(ctx))
            await self.goodies.update_status(
                context, self.bot.i18n[context]['gpl_volupd'].format(ctx))

        except ValueError:
            await self.goodies.supdate_status(
                context, self.i18n[context]['gpl_volvale'])
            return

        except (NotInCallError, NoActiveGroupCall, AttributeError):
            await self.goodies.update_status(
                context, self.i18n[context]['pl_novoice'])
            return False

    async def stop(
        self, _, __, context: 'stub.Context'
    ) -> Optional[bool]:
        if not context.voice_id:
            await self.goodies.update_status(
                context, self.i18n[context]['pl_novoice'])
            return False

        try:
            await self.player.stop(context)
            await self.goodies.update_status(
                context, self.i18n[context]['gpl_stopped'])

        except (NoActiveGroupCall, NotInCallError):
            await self.goodies.update_status(
                context, self.i18n[context]['pl_novice'])

        return False

    async def status(
        self, _, __, context: 'stub.Context'
    ) -> Optional[bool]:
        if not context.voice_id:
            await self.goodies.update_status(
                context, self.i18n[context]['pl_novoice'])
            return False

        await self.player.status(context)

    async def playlist(
        self, _, __, context: 'stub.Context'
    ) -> Optional[bool]:
        if not context.voice_id:
            await self.goodies.update_status(
                context, self.i18n[context]['pl_novoice'])
            return False

        pos: Optional[int] = await self.ustorage.pl_position(
            context.voice_id)

        data: list['stub.SongData']
        if pos:
            data = await self.ustorage.pl_fetch(
                context.voice_id, offset=pos)

        if not pos or not data:
            await self.goodies.update_status(
                context, self.i18n[context]['gpl_nonext'])
            return

        await self.goodies.update_status(
            context, self.i18n[context]['gpl_playlist'].format(
                '\n\n'.join([
                    self.i18n[context]['gpl_placeholder'].format(
                        no=1 + pos + x,
                        data=self.goodies.format_sd(
                            context, data[x], key='gd_simpledata')
                    ) for x in range(0, len(data))
                ])
            )
        )

    def stub(self, root: dict[str, any]) -> None:
        pass
