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

from modules.player import Player

from typing import Self, Dict, Any, Callable, Union, Optional, Tuple
from pytgcalls.types import MediaStream, AudioQuality, Update
from pyrogram.types import ChatInviteLink, Message, Audio
from pytgcalls import PyTgCalls, filters as pfilters
from pyrogram import Client, filters, idle, enums
from mimetypes import guess_extension
from validators import url as vurl
from ntgcalls import FFmpegError
from yt_dlp import YoutubeDL
import traceback
import asyncio
import storage
import math
import json
import os
import re

if 'DEBUG' in os.environ:
  import tracemalloc
  tracemalloc.start()


config = {
# locking level for /next command
  'next_lock_level': 2,
# next_[command|callback] max allowed retries
  'next_retry_count': 15,
# next logic is programmed for it to
# sleep after requesting lock for avoiding
# lock collision
  'next_sleep': 0.5,
# when a status message is sent, and the
# last msgid - status.msgid is greather or
# equal than this quantity, a new one is
# sent when requested
  'msgid_threeshold': 3,  
# a chat for the error logging
  'error_logging_id': 1211166567,
# max allowed file_size from telegram audios
  'telegram_media_size': 50 * 1024 * 1024,
# when radiobot needs to create internal
# invite links, it needs to name them, this
# is the name that it uses
  'chat_invite_link_name': 'RadioBot user',
# whether you want the bot to parse youtube links
# like this one '[author] - [song title]' or not
  'youtube_sname_parsing': 1
}


if os.path.isfile('config.json'):
  with open('config.json') as cfg:
    config.update(json.load(cfg))


# WARNING: RADIOBOT DOES NOT PROVIDE A METHOD
#           FOR DELETING MEDIA FILES DOWNLOADED FROM TELEGRAM!
# TODO: Include a trash manager

# TODO: Better modularization
# TODO: Better language managment
# TODO: Implement playlist limit
# TODO: Implement permissions
# TODO: Implement group language
# TODO: Complete spanish i18n
# TODO: Implement playing from telegram audios (50% done)


class CustomClient(Client):
  def __init__(self, config: Dict[str, Any], *args, **kwargs) -> Self:
    Client.__init__(self, *args, **kwargs)
    # TODO: Transition from _ustorage to ustorage
    self._ustorage = storage.TemporaryStorage()
    self.ustorage = self._ustorage
    self.ExtractChatID = storage.ExtractChatID
    self.config = config

    with open('strings.json', 'r') as _ui:
      self.pseudo_ui: Dict[str, Any] = json.load(_ui)
    self.ui: Callable = lambda message: \
      self.pseudo_ui.get(self._extract_language(message),
        self.pseudo_ui[self.pseudo_ui['default']])

    self.player = None

  def _extract_language(self, message: Optional[Message]) -> str:
    if not message or not hasattr(message, 'from_user') or \
        not hasattr(message.from_user, 'language_code'):
      return self.pseudo_ui['default']
    lc: str = message.from_user.language_code
    if lc not in self.pseudo_ui:
      return self.pseudo_ui['default']
    return lc

  def to_strtime(self, time: int) -> str:
    # TODO: Test
    if time > 59 * 60 + 60:
      return '{:0>2}:{:0>2}:{:0>2}'.format(
        int(time / 3600), int((time % 3600) / 60), int((time % 3600) % 60))
    return '{:0>2}:{:0>2}'.format(int(time / 60), int(time % 60))

  def parse_message_cid(self, message: Union[Message, int]) -> Tuple[Optional[Message], int]:
    if isinstance(message, int):
      return (None, message)

    elif isinstance(message, Message):
      return (message, message.chat.id)

    raise Exception('Programming Error!')

  async def whitelisted(self, chat_id: int, user_id: int) -> bool:
    # TODO: cache response
    async for admin in self.get_chat_members(
        chat_id, filter=enums.ChatMembersFilter.ADMINISTRATORS):
      if hasattr(admin, 'user') and admin.user.id == user_id:
        return True
    return False

  async def _progress(self, part: int, total: int):
    print(part, total)

  async def player_from_telegram(self, message: Message, audio: Audio) -> None:
    if audio.file_size > self.config['telegram_media_size']:
      # TODO: better errors
      return

    # TODO: catch error
    url: str = await self.download_media(
      audio.file_id,
      f'/tmp/{audio.file_unique_id}{guess_extension(audio.mime_type)}',
      progress=self._progress, in_memory=False, block=True)

    pid: int = message.chat.id
    if pid < 0:
      pid = norm_cid(-message.chat.id)

    mid = message.id
    if hasattr(message, 'reply_to_message') and hasattr(message.reply_to_message, 'audio'):
      mid = message.reply_to_message.id

    await self.player.play(message, url, {
      'author': audio.performer if hasattr(audio, 'performer') else None,
      'title': audio.title if hasattr(audio, 'title') else None,
      'duration': audio.duration if hasattr(audio, 'duration') else None,
      'refurl': f'https://t.me/c/{pid}/{mid}'
    })

  async def send_status(self, message: Union[Message, int], *args, **kwargs) -> Message:
    chat_id: int
    _id: int = -1

    title: str
    if 'title' in kwargs:
      title = kwargs['title']
      del kwargs['title']

    else:
      title = self.ui(message)['deftitle']

    if 'text' not in kwargs:
      args = list(args)
      args[0] = self.ui(message)['fmt'].format(title, args[0])

    else:
      kwargs['text'] = self.ui(message)['fmt'].format(title, kwargs['text'])

    message, chat_id = self.parse_message_cid(message)
    if message:
      _id = message.id

    last: int = self._ustorage.get_last_statusmsg(chat_id)
    if last == -1 or (_id != -1 and (_id - last) > self.config['msgid_threeshold']):
      if last != -1:
        await self.delete_messages(chat_id, last)

      newmsg: Message = await self.send_message(chat_id, *args, **kwargs)
      self._ustorage.set_last_statusmsg(chat_id, newmsg.id)
      return newmsg

    try:
      return await self.edit_message_text(chat_id, last, *args, **kwargs)

    except MessageNotModified:
      return Message(id=last)

  async def report_error(
    self, ctx: Union[Message, str],
    exc: Exception, formatexc: str,
    method_name: str = ''
  ) -> None:
    if isinstance(ctx, Message):
      message: Message = ctx
      try:
        ctx = self.ui(None)['remsg'].format(
          message.id, message.date,
          message.from_user.first_name, message.from_user.id,
          (message.from_user.username if hasattr(message.from_user, 'username')
            else 'username'),
          message.from_user.language_code,
          message.chat.title, message.chat.id,
          (message.chat.username if hasattr(message.chat, 'username')
            else 'username'),
          '\n\t\t\t'.join(str(message.chat.permissions).split('\n'))
            if message.chat.permissions else 'None', message.text)

      except (KeyError, AttributeError) as at:
        pass

    await self.send_message(chat_id=config['error_logging_id'],
      text=self.ui(None)['rerror'].format(
        method_name, ctx, type(exc).__name__, str(exc), formatexc))



@filters.create
async def Whitelisted(_, client: CustomClient, message: Message) -> bool:
  return await client.whitelisted(message.chat.id, message.from_user.id)




userbot: Client = Client(
  name=os.environ['CLIENT_NAME'] + '_userbot',
  api_id=int(os.environ['TG_API_ID']),
  api_hash=os.environ['TG_API_HASH'])
callapi: PyTgCalls = PyTgCalls(userbot)

client: CustomClient = CustomClient(
  config=config,
  name=os.environ['CLIENT_NAME'],
  api_id=int(os.environ['TG_API_ID']),
  api_hash=os.environ['TG_API_HASH'])

client.player = Player(client, userbot, callapi)

# Deletes the first 3 digits of a number by calculating
#  number % 10^max(number of digits - 3, 1)
norm_cid: Callable = lambda n: n % 10**int(max(math.log10(n) - 2, 1))


@client.on_message(filters.command('start') & filters.private)
async def start(client, message) -> None:
  await message.reply(client.ui(message)['start'])


@client.on_message(filters.command('help') & filters.private)
async def help(client, message) -> None:
  await message.reply(client.ui(message)['help'], disable_web_page_preview=True)


@client.on_message(filters.command('play') & ~storage.ChatLocked & Whitelisted & filters.group)
@storage.UseLock()
async def play(client, message) -> None:
  top = message
  if hasattr(message, 'reply_to_message'):
    top = message.reply_to_message

  if hasattr(top, 'audio'):
    await client.player_from_telegram(message, top.audio)
    return

  if message.text.count(' ') == 0:
    await client.send_status(message, client.ui(message)['no_payload_play'])
    return

  ctx: str = message.text.split(' ', 1)[1]
  if not vurl(ctx):
    await client.send_status(message, client.ui(message)['invalid_url'])
    return
  await client.player.play(message, ctx)


@client.on_message(filters.command('pause') & ~storage.ChatLocked & Whitelisted& filters.group)
@storage.UseLock()
async def pause(client, message) -> None:
  try:
    await client.player.pause(message.chat.id)
    await client.send_status(message, client.ui(message)['paused'])

  except NotInCallError:
    await client.send_status(message, client.ui(message)['not_in_voice'])
    return


@client.on_message(filters.command('resume') & ~storage.ChatLocked & Whitelisted & filters.group)
@storage.UseLock()
async def resume(client, message) -> None:
  try:
    await client.player.resume(message.chat.id)
    await client.send_status(message, client.ui(message)['resumed'])

  except NotInCallError:
    await client.send_status(message, client.ui(message)['not_in_voice'])
    return


@client.on_message(filters.command('next') & ~storage.ChatLocked & Whitelisted & filters.group)
@storage.UseLock(config['next_lock_level'])
async def cnext(client, message) -> None:
  try:
    await client.player.next(message.chat.id)

  except NotInCallError:
    await client.send_status(message, client.ui(message)['not_in_voice'])
    return


@client.on_message(filters.command('volume') & ~storage.ChatLocked & Whitelisted& filters.group)
@storage.UseLock()
async def volume(client, message) -> None:
  if message.text.count(' ') == 0:
    await client.send_status(message, client.ui(message)['volume_valueerror'])
    return

  ctx: str = message.text.split(' ', 1)[1]
  try:
    await callapi.change_volume_call(message.chat.id, int(ctx))
    await client.send_status(message, client.ui(message)['volume_set_to'].format(int(ctx)))

  except ValueError:
    await client.send_status(message, client.ui(message)['volume_valueerror'])

  except (NotInCallError, NoActiveGroupCall, AttributeError):
    await client.send_status(message, client.ui(message)['not_in_voice'])


@client.on_message(filters.command('stop') & ~storage.ChatLocked & Whitelisted & filters.group)
@storage.UseLock()
async def stop(client, message) -> None:
  try:
    await client.player.stop(message.chat.id)
    await client.send_status(message, client.ui(message)['stopped'])
  except (NoActiveGroupCall, NotInCallError):
    await message.reply(client.ui(message)['not_in_voice'])
  client._ustorage.clean_playlist(message.chat.id)


@client.on_message(filters.command('status') & ~storage.ChatLocked & Whitelisted & filters.group)
@storage.UseLock()
async def status(client, message) -> None:
  await client.player.send_playing(message)


@client.on_message(filters.command('playlist') & Whitelisted & filters.group)
@storage.NoLock
async def playlist(client, message) -> None:
  size: int = client._ustorage.playlist_size(message.chat.id)
  if size == 0:
    await client.send_status(message, client.ui(message)['not_in_voice'])
    return

  pidx: int = client._ustorage.playlist_dsize(message.chat.id)
  songs: List[str, int, str, str] = \
    client._ustorage.fetch_playlist(message.chat.id, 10)
  strings: Dict[str, str] = client.ui(message)

  o_songs: str = ""
  i: int = 0
  for song in songs:
    if song[2] != '' or song[3] != '':
      o_songs += strings['songfmt_wauthor'].format(
        size - pidx + i, song[0],
        song[2] or strings['no_author'],
        song[3] or strings['no_title']) + '\n'

    else:
      o_songs += strings['songfmt_nauthor'].format(
        size - pidx + i, song[0]) + '\n'
    i += 1

  await message.reply(strings['fmt'].format(strings['pltitle'], o_songs.strip()))


@callapi.on_update(pfilters.stream_end)
@storage.NoLock
async def next_callback(
  _: PyTgCalls, update: Update, locked: bool = False
) -> None:
  chat_id: int = update.chat_id
  i: int = 0

  if not locked:
    lock_level: int = client._ustorage.get_lock_level(chat_id)
    while lock_level > 0 and i <= config['next_retry_count']:
      if lock_level == config['next_lock_level']:
        return

      await asyncio.sleep(config['next_sleep'])
      lock_level = client._ustorage.get_lock_level(chat_id)
      i += 1

    if i - 1 == NEXT_RETRY_COUNT:
      return

    _id: int = client._ustorage.lock_chat(chat_id)
    await asyncio.sleep(0.1)
    if _id != client._ustorage.get_lock_time(chat_id):
      await asyncio.sleep(1)
      next_callback(_, update)
      return  # Another method is running

  await client.player.next(chat_id)
  if not locked:
    client._ustorage.unlock_chat(chat_id)


client.start()
callapi.start()
idle()
