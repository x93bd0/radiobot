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
from modules.baseui import Module as BaseUI
from modules.groupui import Module as GroupUI

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
# TODO: Further refactorization

class CustomClient(Client):
  def __init__(self, config: Dict[str, Any], *args, **kwargs) -> Self:
    Client.__init__(self, *args, **kwargs)
    self.ustorage = storage.TemporaryStorage()
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
    if time > 60 * 60:
      hour: int = int(time / 3600)
      time -= hour * 3600
      minutes: int = time / 60
      time -= minutes * 60
      return '{:0>2}:{:0>2}:{:0>2}'.format(hour, minutes, time)
    return '{:0>2}:{:0>2}'.format(int(time / 60), time % 60)

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

    last: int = self.ustorage.get_last_statusmsg(chat_id)
    if last == -1 or (_id != -1 and (_id - last) > self.config['msgid_threeshold']):
      if last != -1:
        await self.delete_messages(chat_id, last)

      newmsg: Message = await self.send_message(chat_id, *args, **kwargs)
      self.ustorage.set_last_statusmsg(chat_id, newmsg.id)
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


class CustomAPI(PyTgCalls):
  def __init__(self, nbot: CustomClient, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.nbot: CustomClient = nbot


@filters.create
async def Whitelisted(_, client: CustomClient, message: Message) -> bool:
  return await client.whitelisted(message.chat.id, message.from_user.id)


userbot: Client = Client(
  name=os.environ['CLIENT_NAME'] + '_userbot',
  api_id=int(os.environ['TG_API_ID']),
  api_hash=os.environ['TG_API_HASH'])

client: CustomClient = CustomClient(
  config=config,
  name=os.environ['CLIENT_NAME'],
  api_id=int(os.environ['TG_API_ID']),
  api_hash=os.environ['TG_API_HASH'])

callapi: CustomAPI = CustomAPI(client, userbot)
client.player = Player(client, userbot, callapi)
client.st = storage

BaseUI(client).install()
GroupUI(client).install()


@callapi.on_update(pfilters.stream_end)
@storage.NoLock
async def next_callback(
  _: PyTgCalls, update: Update, locked: bool = False
) -> None:
  chat_id: int = update.chat_id
  i: int = 0

  if not locked:
    lock_level: int = client.ustorage.get_lock_level(chat_id)
    while lock_level > 0 and i <= config['next_retry_count']:
      if lock_level == config['next_lock_level']:
        return

      await asyncio.sleep(config['next_sleep'])
      lock_level = client.ustorage.get_lock_level(chat_id)
      i += 1

    if i - 1 == config['next_retry_count']:
      return

    _id: int = client.ustorage.lock_chat(chat_id)
    await asyncio.sleep(0.1)
    if _id != client.ustorage.get_lock_time(chat_id):
      await asyncio.sleep(1)
      next_callback(_, update)
      return  # Another method is running

  await client.player.next(chat_id)
  if not locked:
    client.ustorage.unlock_chat(chat_id)


client.start()
callapi.start()
idle()
