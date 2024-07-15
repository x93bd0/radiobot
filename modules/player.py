from pyrogram.errors.exceptions.bad_request_400 import (
  ChatAdminRequired,
  ChannelInvalid,
  InviteHashExpired,
)

from pytgcalls.exceptions import (
  NoAudioSourceFound,
  YtDlpError,
  NoActiveGroupCall,
  NotInCallError
)

from typing import Optional, Tuple, List, Callable, Dict, Any
from pytgcalls.types import MediaStream, AudioQuality
from pyrogram.types import ChatInviteLink
from ntgcalls import FFmpegError
from pytgcalls import PyTgCalls
import traceback
import enum

# For linting
from stub import *


# TODO: Unify API.play
# TODO: Allow PlayerStatus to return "exceptions"


class PlayerStatus(enum.Enum):
  ENQUEUED = 1
  CANT_JOIN = 2
  NO_VOICE = 3
  ENDED = 4
  UNKNOWN_ERROR = 5
  OK = 6


class Module:
  def __init__(self, bot: 'MainClient'):
    self.bot: 'MainClient' = bot
    self.ubot: 'MainClient' = self.bot.ubot

    self.Status = PlayerStatus
    self.api: PyTgCalls = bot.api
    self.i18n: 'i18n' = self.bot.i18n

  async def install(self) -> None:
    self.bot.player = self
    self.bot.register_configs([
      'Player_InviteLink'
    ], [
      'RadioBot'
    ])

  async def post_install(self) -> None:
    self.goodies = self.bot.goodies
    self.ustorage = self.bot.ustorage


  async def play(
    self, context: 'Context',
    data: 'SongData'
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
      await self.ubot.get_chat(context.voice_id)

    except ChannelInvalid:
      await self.goodies.update_status(
        context, self.i18n[context]['pl_glink'])

      link: ChatInviteLink
      try:
        link = await self.bot.create_chat_invite_link(
          context.voice_id, member_limit=1,
          name=self.bot.config['Player_InviteLink'])

      except ChatAdminRequired:
        await self.goodies.update_status(
          context, self.i18n[context]['pl_cglink'])
        return PlayerStatus.CANT_JOIN

      await self.goodies.update_status(
        context, self.i18[context]['pl_joningc'])

      try:
        await self.ubot.join_chat(link.invite_link)

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
      NoAudioSourceFound, YtDlpError, FFmpegError,
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
    self, context: 'Context',
    leave: bool = True
  ) -> None:
    await self.ustorage.pl_clean(context.voice_id)
    if leave:
      try:
        await self.api.leave_call(context.voice_id)

      except NotInCallError:
        pass

  async def pause(
    self, context: 'Context'
  ) -> None:
    await self.api.pause_stream(context.voice_id)

  async def resume(
    self, context: 'Context'
  ) -> None:
    await self.api.resume_stream(context.voice_id)

  async def next(
    self, context: 'Context'
  ) -> PlayerStatus:
    next_data: Optional[Tuple[int, 'SongData']] = \
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
      NoAudioSourceFound, YtDlpError, FFmpegError,
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
    self, context: 'Context'
  ) -> PlayerStatus:
    elapsed: int
    sdata: 'SongData'

    try:
      elapsed = await self.api.played_time(context.voice_id)
      data: List['SongData'] = await self.ustorage.pl_fetch(
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


  def stub(self, root: Dict[str, Any]):
    root['bot'].update({
      'player': {
        '__name__': 'Player',
        'play': Callable[['Context', 'SongData'], 'PlayerStatus'],
        'stop': Callable[['Context', bool], None],
        'pause': Callable[['Context'], None],
        'resume': Callable[['Context'], None],
        'next': Callable[['Context'], 'PlayerStatus'],
        'status': Callable[['Context'], 'PlayerStatus'],

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
    })