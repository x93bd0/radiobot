"""
    Player API
"""

from typing import Optional, Tuple, List, Callable, Any
import traceback
import enum

from pyrogram.errors.exceptions.bad_request_400 import (
    ChatAdminRequired,
    ChannelInvalid,
    InviteHashExpired,
)

from pyrogram.types import ChatInviteLink
from pyrogram.client import Client

from pytgcalls.exceptions import (
    NoAudioSourceFound,
    YtDlpError,
    NoActiveGroupCall,
    NotInCallError
)

from pytgcalls.types import MediaStream
from pytgcalls import PyTgCalls
import ntgcalls

from stub import MetaClient, MetaModule
import stub


# TODO: Unify API.play
# TODO: Allow PlayerStatus to return "exceptions"


class PlayerStatus(enum.Enum):
    ENQUEUED = 1
    CANT_JOIN = 2
    NO_VOICE = 3
    ENDED = 4
    UNKNOWN_ERROR = 5
    OK = 6


class Module(MetaModule):
    ustorage: MetaClient
    goodies: MetaClient
    i18n: MetaClient

    def __init__(self, client: MetaClient):
        self.identifier: str = 'Player'
        self.client: MetaClient = client
        self.userbot: Client = self.client.userbot

        self.player_status = PlayerStatus
        self.api: PyTgCalls = self.client.api

    async def setup(self) -> None:
        pass

    async def install(self) -> None:
        self.client.register_configuration(self, {
            'Player_InviteLink': 'RadioBot'
        })

    async def post_install(self) -> None:
        self.i18n = self.client.modules['I18n']
        self.goodies = self.client.modules['Goodies']
        self.ustorage = self.client.modules['UStorage']


    async def play(
        self, context: 'stub.Context',
        data: 'stub.SongData'
    ) -> PlayerStatus:
        if context.voice_id in (await self.api.calls):
            index: int = await self.ustorage.pl_enqueue(context.voice_id, data)
            await self.goodies.update_status(
                context, self.i18n[context]['pl_enqueued'].format(
                    self.goodies.format_sd(context, data, key='gd_simpledata')))

            return PlayerStatus.ENQUEUED

        await self.goodies.update_status(
            context, self.i18n[context]['pl_joining'])

        try:
            await self.userbot.get_chat(context.voice_id)

        except ChannelInvalid:
            await self.goodies.update_status(
                context, self.i18n[context]['pl_glink'])

            link: ChatInviteLink
            try:
                link = await self.client.create_chat_invite_link(
                    context.voice_id, member_limit=1,
                    name=self.client.config['Player_InviteLink'])

            except ChatAdminRequired:
                await self.goodies.update_status(
                    context, self.i18n[context]['pl_cglink'])
                return PlayerStatus.CANT_JOIN

            await self.goodies.update_status(
                context, self.i18n[context]['pl_joningc'])

            try:
                await self.userbot.join_chat(link.invite_link)

            except InviteHashExpired:
                await self.goodies.update_status(
                    context, self.i18n[context]['pl_cjoin'])
                return PlayerStatus.CANT_JOIN

        await self.goodies.update_status(
            context, self.i18n[context]['pl_splaying'])

        try:
            await self.api.play(context.voice_id, MediaStream(
                data.url, video_flags=MediaStream.Flags.IGNORE,
                audio_flags=MediaStream.Flags.REQUIRED
            ))

        except ChatAdminRequired:
            await self.goodies.update_status(
                context, self.i18n[context]['pl_novoice'])
            return PlayerStatus.NO_VOICE

        except (
            NoAudioSourceFound, YtDlpError, ntgcalls.FFmpegError,
            FileNotFoundError, AttributeError
        ) as e:
            await self.goodies.report_error(
                context, e, traceback.format_exc(),
                'player_play[play]')

            await self.goodies.update_status(
                context, self.i18n[context]['pl_retry'])
            return PlayerStatus.UNKNOWN_ERROR

        # Just 4 logging (& saving the first element of the playlist)
        await self.ustorage.pl_enqueue(context.voice_id, data)
        await self.ustorage.pl_dequeue(context.voice_id)
        return PlayerStatus.OK

    async def stop(
        self, context: 'stub.Context',
        leave: bool = True
    ) -> None:
        await self.ustorage.pl_clean(context.voice_id)
        if leave:
            try:
                await self.api.leave_call(context.voice_id)

            except NotInCallError:
                pass

    async def pause(
        self, context: 'stub.Context'
    ) -> None:
        await self.api.pause_stream(context.voice_id)

    async def resume(
        self, context: 'stub.Context'
    ) -> None:
        await self.api.resume_stream(context.voice_id)

    async def next(
        self, context: 'stub.Context'
    ) -> PlayerStatus:
        next_data: Optional[Tuple[int, 'stub.SongData']] = \
            await self.ustorage.pl_dequeue(context.voice_id)

        if not next_data:
            await self.ustorage.pl_clean(context.voice_id)
            try:
                await self.stop(context)

            except (NoActiveGroupCall, NotInCallError):
                pass

            await self.goodies.update_status(
                context, self.i18n[context]['pl_ended'])

            return PlayerStatus.ENDED

        try:
            await self.api.play(context.voice_id, MediaStream(
                next_data[1].url, video_flags=MediaStream.Flags.IGNORE,
                audio_flags=MediaStream.Flags.REQUIRED))

        except ChatAdminRequired:
            await self.goodies.update_status(
                context, self.i18n[context]['pl_novoice'])
            return PlayerStatus.NO_VOICE

        except (
            NoAudioSourceFound, YtDlpError, ntgcalls.FFmpegError,
            FileNotFoundError, AttributeError
        ) as e:
            await self.goodies.report_error(
                context, e, traceback.format_exc(),
                'player_next[play]')

            await self.goodies.update_status(
                context, self.i18n[context]['pl_retry'])
            return PlayerStatus.UNKNOWN_ERROR
        return PlayerStatus.OK

    async def status(
        self, context: 'stub.Context'
    ) -> PlayerStatus:
        elapsed: int
        sdata: 'stub.SongData'

        try:
            elapsed = await self.api.played_time(context.voice_id)
            data: List['stub.SongData'] = await self.ustorage.pl_fetch(
                context.voice_id, limit=1,
                offset=(await self.ustorage.pl_position(context.voice_id)) - 1)

            if not data or len(data) == 0:
                raise NotInCallError()
            sdata = data[0]

        except NotInCallError:
            # await self.stop(context)
            await self.goodies.update_status(
                context, self.i18n[context]['pl_novoice'])
            return PlayerStatus.NO_VOICE

        await self.goodies.update_status(
            context, self.goodies.format_sd(
                context, sdata,
                elapsed=elapsed
            ))
        return PlayerStatus.OK


    def stub(self, root: dict[str, Any]):
        root['player'] = {
            '__name__': 'Player',
            'play': Callable[['stub.Context', 'stub.SongData'], 'PlayerStatus'],
            'stop': Callable[['stub.Context', bool], None],
            'pause': Callable[['stub.Context'], None],
            'resume': Callable[['stub.Context'], None],
            'next': Callable[['stub.Context'], 'PlayerStatus'],
            'status': Callable[['stub.Context'], 'PlayerStatus'],

            'PlayerStatus': {
                '__name__': 'PlayerStatus',
                'ENQUEUED': int,
                'CANT_JOIN': int,
                'NO_VOICE': int,
                'ENDED': int,
                'UNKNOWN_ERROR': int,
                'OK': int
            }
        }
