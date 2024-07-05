# TODO: Remove unused imports
from pytgcalls.exceptions import (
  GroupCallNotFound,
  NoAudioSourceFound,
  YtDlpError,
  NotInCallError,
  NoActiveGroupCall
)

from pyrogram.errors.exceptions.bad_request_400 import (
  ChatAdminRequired,
  ChannelInvalid,
  InviteHashExpired,
  MessageNotModified
)

from pytgcalls.types import MediaStream, AudioQuality, Update
from typing import Dict, Any, List, Optional, Union, Tuple
from validators import url as vurl
from pyrogram.types import Message
from ntgcalls import FFmpegError
from pytgcalls import PyTgCalls
from pyrogram import Client
from yt_dlp import YoutubeDL
import traceback
import re


# TODO: Better formatting (avoid >80 chars)
# From https://stackoverflow.com/a/61033353
youtube_regex = re.compile(
  r'(?:https?:\/\/)?(?:www\.)?youtu(?:\.be\/|be.com\/\S*(?:watch|embed)(?:(?:(?=\/[-a-zA-Z0-9_]{11,}(?!\S))\/)|(?:\S*v=|v\/)))([-a-zA-Z0-9_]{11,})')
ytdl: YoutubeDL = YoutubeDL()


class Player:
  def __init__(self, bot: Client, userbot: Client, callapi: PyTgCalls):
    self.api: PyTgCalls = callapi
    self.bot: Client = bot
    self.ubot: Client = userbot

  async def get_song_info(self, url: str, ctx: str) -> Tuple[str, str, int, str]:
    author: str
    title: str
    length: int
    refurl: str

    if isinstance(url, str) and youtube_regex.match(url):
      info = ytdl.extract_info(url, download=False, process=False)
      if info['extractor'] != 'youtube':
        url = info['webpage_url']
        params = url.rsplit('?', 1)[1].split('&')

        watchv = ''
        for param in params:
          if param.startswith('v='):
            watchv = param[2:]
            break

        url = f'https://youtube.com/watch?v={watchv}'
        info = ytdl.extract_info(url, download=False, process=False)

      if info['extractor'] == 'youtube':
        author = (' & '.join(info['artists']) if 'artists' in info else info['uploader'])
        title = info['title']
        length = info['duration']

        if self.bot.config['youtube_sname_parsing']:
          if title.lower().startswith(author.lower()):
            if ' - ' in title:
              sp = title.split(' - ', 1)
              author = sp[0]
              title = sp[1]
        refurl = info['webpage_url']

    elif ctx:
      author = ctx.get('author', None)
      title = ctx.get('title', None)
      length = ctx.get('duration', None)
      refurl = ctx.get('refurl', url)

    return (author, title, length, refurl)

  async def play(
    self, chat_id: Union[Message, int],
    url: str, ctx: Optional[Dict[str, Any]] = None
  ) -> None:
    message: Optional[Message]
    cid: int

    message, cid = self.bot.parse_message_cid(chat_id)
    if cid in (await self.api.calls):
      idx: int = self.bot.ustorage.playlist_enqueue(
        cid, url)
      await self.bot.send_status(
        message, self.bot.ui(message)['enqueued'].format(idx, url))
      return

    info: Message = \
      await self.bot.send_status(message, self.bot.ui(message or cid)['joining_voice'])

    try:
      await self.ubot.get_chat(cid)

    except ChannelInvalid:
      await info.edit_text(self.bot.ui(message)['generating_link'])

      link: ChatInviteLink
      try:
        link = await self.bot.create_chat_invite_link(
          cid, name=self.bot.config['chat_invite_link_name'], member_limit=1)

      except ChatAdminRequired:
        await info.edit_text(self.bot.ui(messagae)['cant_generate_link'])
        return

      try:
        await info.edit_text(self.bot.ui(message)['joining_chat'])
        await self.ubot.join_chat(link.invite_link)

      except InviteHashExpired:
        await info.edit_text(self.bot.ui(message)['cant_join_chat'])
        return

    await self.bot.send_status(message, self.bot.ui(message)['start_playing'])
    author, title, length, refurl = \
      await self.get_song_info(url, ctx)

    try:
      await self.api.play(cid, MediaStream(
        url, video_flags=MediaStream.Flags.IGNORE,
        audio_flags=MediaStream.Flags.REQUIRED
      ))

    except ChatAdminRequired:
      await info.edit_text(self.bot.ui(message)['no_chat'])
      return

    except (
      NoAudioSourceFound, YtDlpError, FFmpegError,
      FileNotFoundError, AttributeError
    ) as e:
      # TODO: Better error (include message as context)
      await self.bot.report_error(
        message, e, traceback.format_exc(), 'player_play[play]')
      await info.edit_text("ERROR")
      return

    self.bot.ustorage.playlist_enqueue(
      cid, refurl or url, author=author,
      name=title, length=length)
    await self.send_playing(message)

  # TODO: Support message input
  async def next(self, chat_id: int) -> None:
    _next: Optional[Tuple[int, str, str, str]] = \
      self.bot.ustorage.playlist_dequeue(chat_id)

    if not _next:
      self.bot.ustorage.clean_playlist(chat_id)

      try:
        await self.api.leave_call(chat_id)
      except (NoActiveGroupCall, NotInCallError):
        pass
      await self.bot.send_status(
        chat_id, self.bot.ui({})['stream_ended'])
      return

    try:
      await self.api.play(chat_id, MediaStream(
        _next[1], video_flags=MediaStream.Flags.IGNORE,
        audio_flags=MediaStream.Flags.REQUIRED))
      await self.send_playing(chat_id)

    except (
      NoAudioSourceFound, YtDlpError,
      FFmpegError, FileNotFoundError
    ):
      return await self.next(chat_id)

    except Exception as e:
      await self.bot.report_error(
        'player_next[play]', e, traceback.format_exc())
      self.bot.ustorage.clean_playlist(chat_id)

  async def stop(self, chat_id: int) -> None:
    await self.api.leave_call(chat_id)

  async def resume(self, chat_id: int) -> None:
    await self.api.resume_stream(chat_id)

  async def pause(self, chat_id: int) -> None:
    await self.api.pause_stream(chat_id)


  async def send_playing(
    self, message: Union[Message, int],
    data: Optional[Tuple[str, int, str, str]] = None
  ) -> None:
    elapsed: int
    chat_id: int

    _, chat_id = self.bot.parse_message_cid(message)
    strings: Dict[str, str] = self.bot.ui(message)

    try:
      elapsed = await self.api.played_time(chat_id)
      if not data:
        data = self.bot.ustorage.playlist_actual(chat_id)

      if not data:
        raise NotInCallError()

    except NotInCallError:
      self.bot.ustorage.clean_playlist(chat_id)
      await self.bot.send_status(message, strings['not_in_voice'])
      return

    song: str
    if data[2] != '' or data[3] != '':
      song = strings['songfmt_wauthor'].format(
        data[0], '' if not vurl(data[1]) else data[1],
        data[2] or strings['no_author'],
        data[3] or strings['no_title'])

    else:
      song = strings['songfmt_nauthor'].format(
        data[0], data[1])

    duration: str = '?'
    if data[4]:
      duration = self.bot.to_strtime(data[4])

    await self.bot.send_status(message, strings['playing'].format(
      song, self.bot.to_strtime(elapsed), duration), title=strings['ptitle'])
