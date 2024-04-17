from pytgcalls.exceptions import (
  GroupCallNotFound,
  NoAudioSourceFound,
  YtDlpError,
  NotInGroupCallError,
  NoActiveGroupCall
)

from pyrogram.errors.exceptions.bad_request_400 import (
  ChatAdminRequired,
  ChannelInvalid,
  InviteHashExpired,
  MessageNotModified
)

from pytgcalls.types import MediaStream, AudioQuality, Update
from pyrogram.types import ChatInviteLink, Message
from typing import Self, Dict, Any, Callable, Union
from pyrogram import Client, filters, idle
from validators import url as vurl
from ntgcalls import FFmpegError
from pytgcalls import PyTgCalls
import asyncio
import storage
import json
import os


# TODO: Implement status command
# TODO: Implement ignore(n) command
# TODO: Implement playlist limit
# TODO: Implement permissions
# TODO: Implement group language
# TODO: Implement player_* methods
# TODO: Implement playing from telegram audios
# TODO: Improve playing/enqueued messages


NEXT_LOCK_LEVEL:       int = 2
NEXT_RETRY_COUNT:      int = 15
NEXT_SLEEP:          float = 0.5
MSGID_THREESHOLD:      int = 3
CHAT_INVITE_LINK_NAME: str = 'RadioBot User'


class CustomClient(Client):
  def __init__(self, *args, **kwargs) -> Self:
    Client.__init__(self, *args, **kwargs)
    self._ustorage = storage.TemporaryStorage()
    self.ExtractChatID = storage.ExtractChatID

    with open('strings.json', 'r') as _ui:
      self.pseudo_ui: Dict[str, Any] = json.load(_ui)
    self.ui: Callable = lambda message: self.pseudo_ui[self._extract_language(message)]

  def _extract_language(self, message: Message, default: str = 'en') -> str:
    if not hasattr(message, 'from_user'):
      return default
    if not hasattr(message.from_user, 'language_code'):
      return default

    lc: str = message.from_user.language_code
    if lc not in self.pseudo_ui:
      return default
    return lc

  async def player_play(self, chat_id: Union[Message, int], url: str) -> None:
    message: Message
    cid: int

    if isinstance(chat_id, int):
      cid = chat_id
      message = Message(id=-1)

    elif isinstance(chat_id, Message):
      message = chat_id
      cid = message.chat.id

    else:
      raise Exception('Programming error!')

    try:
      await callapi.get_active_call(cid)
      idx: int = self._ustorage.playlist_enqueue(
        cid, url)
      await self.send_status(
        message, self.ui(message)['enqueued'].format(idx, url))
      return

    except GroupCallNotFound:
      pass

    info: Message = \
      await self.send_status(message, client.ui(message)['joining_voice'])
    try:
      await userbot.get_chat(cid)

    except ChannelInvalid:
      await info.edit_text(client.ui(message)['generating_link'])

      link: ChatInviteLink
      try:
        link = await client.create_chat_invite_link(
          cid, name=CHAT_INVITE_LINK_NAME, member_limit=1)

      except ChatAdminRequired:
        await info.edit_text(client.ui(messagae)['cant_generate_link'])
        return

      try:
        await info.edit_text(client.ui(message)['joining_chat'])
        await userbot.join_chat(link.invite_link)

      except InviteHashExpired:
        await info.edit_text(client.ui(message)['cant_join_chat'])
        return

    try:
      await callapi.join_group_call(cid, MediaStream(
        url, video_flags=MediaStream.IGNORE,
        audio_flags=MediaStream.REQUIRED
      ))

    except ChatAdminRequired:
      await info.edit_text(client.ui(message)['no_chat'])
      return

    await info.edit_text(client.ui(message)['playing'].format(0, url))
    self._ustorage.playlist_enqueue(cid, url)

  # TODO: Support message input
  async def player_next(self, chat_id: int) -> None:
    _next: Optional[Tuple[int, str, str, str]] = client._ustorage.playlist_dequeue(chat_id)
    if not _next:
      try:
        await callapi.leave_group_call(chat_id)
      except (NoActiveGroupCall, NotInGroupCallError):
        return

      await client.send_status(chat_id, client.ui({})['stream_ended'])
      return

    try:
      await callapi.change_stream(chat_id, MediaStream(
        _next[1], video_flags=MediaStream.IGNORE,
        audio_flags=MediaStream.REQUIRED
      ))

      # TODO: Replace with client.send_playing()
      await client.send_status(
        chat_id, client.ui({})['playing'].format(_next[0], _next[1]))

    except (NoAudioSourceFound, YtDlpError, FFmpegError, FileNotFoundError):
      return await self.player_next(chat_id)

    except:
      # TODO: report error
      client._ustorage.clean_playlist(chat_id)

  async def player_stop(self, chat_id: int) -> None:
    pass

  async def player_resume(self, chat_id: int) -> None:
    pass

  async def player_enqueue(self, chat_id: int, url: str) -> None:
    pass

  async def player_playing(self, chat_id: int, url: str) -> None:
    pass

  async def send_status(self, message: Union[Message, int], *args, **kwargs) -> Message:
    chat_id: int
    _id: int

    if isinstance(message, int):
      chat_id = message
      _id = -1

    elif isinstance(message, Message):
      chat_id = message.chat.id
      _id = message.id

    else:
      raise Exception('Programming error!')

    last: int = self._ustorage.get_last_statusmsg(chat_id)
    if last == -1 or (_id != -1 and (_id - last) > MSGID_THREESHOLD):
      if last != -1:
        await self.delete_messages(chat_id, last)

      newmsg: Message = await self.send_message(chat_id, *args, **kwargs)
      self._ustorage.set_last_statusmsg(chat_id, newmsg.id)
      return newmsg

    try:
      return await self.edit_message_text(chat_id, last, *args, **kwargs)

    except MessageNotModified:
      return Message(id=last)


userbot: Client = Client(
  name=os.environ['CLIENT_NAME'] + '_userbot',
  api_id=int(os.environ['TG_API_ID']),
  api_hash=os.environ['TG_API_HASH'])
callapi: PyTgCalls = PyTgCalls(userbot)

client: CustomClient = CustomClient(
  name=os.environ['CLIENT_NAME'],
  api_id=int(os.environ['TG_API_ID']),
  api_hash=os.environ['TG_API_HASH'])


@client.on_message(filters.command('start'))
async def start(client, message) -> None:
  pass


@client.on_message(filters.command('help'))
async def help(client, message) -> None:
  pass


@client.on_message(filters.command('play') & ~storage.ChatLocked)
@storage.UseLock()
async def play(client, message) -> None:
  if message.text.count(' ') == 0:
    await client.send_status(message, client.ui(message)['no_payload_play'])
    return

  ctx: str = message.text.split(' ', 1)[1]
  if not vurl(ctx):
    await client.send_status(message, client.ui(message)['invalid_url'])
    return
  await client.player_play(message, ctx)


@client.on_message(filters.command('pause') & ~storage.ChatLocked)
@storage.UseLock()
async def pause(client, message) -> None:
  try:
    await callapi.pause_stream(message.chat.id)
    await client.send_status(message, client.ui(message)['paused'])

  except NotInGroupCallError:
    await client.send_status(message, client.ui(message)['not_in_voice'])
    return


@client.on_message(filters.command('resume') & ~storage.ChatLocked)
@storage.UseLock()
async def resume(client, message) -> None:
  try:
    await callapi.resume_stream(message.chat.id)
    await client.send_status(message, client.ui(message)['resumed'])

  except NotInGroupCallError:
    await client.send_status(message, client.ui(message)['not_in_voice'])
    return


@client.on_message(filters.command('next') & ~storage.ChatLocked)
@storage.UseLock(NEXT_LOCK_LEVEL)
async def cnext(client, message) -> None:
  try:
    await client.player_next(message.chat.id)

  except NotInGroupCallError:
    await client.send_status(message, client.ui(message)['not_in_voice'])
    return


@client.on_message(filters.command('volume') & ~storage.ChatLocked)
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

  except (NotInGroupCallError, NoActiveGroupCall, AttributeError):
    await client.send_status(message, client.ui(message)['not_in_voice'])


@client.on_message(filters.command('stop') & ~storage.ChatLocked)
@storage.UseLock()
async def stop(client, message) -> None:
  try:
    await callapi.leave_group_call(message.chat.id)
    await client.send_status(message, client.ui(message)['stopped'])
  except (NoActiveGroupCall, NotInGroupCallError):
    await message.reply(client.ui(message)['not_in_voice'])
  client._ustorage.clean_playlist(message.chat.id)


@client.on_message(filters.command('status') & ~storage.ChatLocked)
@storage.UseLock()
async def status(client, message) -> None:
  pass


@client.on_message(filters.command('playlist'))
async def playlist(client, message) -> None:
  size: int = client._ustorage.playlist_size(message.chat.id)
  if size == 0:
    await client.send_status(message, client.ui(message)['not_in_voice'])
    return

  pidx: int = client._ustorage.playlist_dsize(message.chat.id)
  songs: List[str, int, str, str] = \
    client._ustorage.fetch_playlist(message.chat.id, 10)

  o_songs: str = ""
  i: int = 0
  for song in songs:
    if song[2] != '' or song[3] != '':
      o_songs += client.ui(message)['songfmt_wauthor'].format(
        size - pidx + i + 1, song[0], song[2], song[3]) + '\n'

    else:
      o_songs += client.ui(message)['songfmt_nauthor'].format(
        size - pidx + i + 1, song[0]) + '\n'
    i += 1

  await message.reply(client.ui(message)['playlistfmt'].format(o_songs))


@callapi.on_stream_end()
async def next_callback(
  _: PyTgCalls, update: Update, locked: bool = False
) -> None:
  chat_id: int = update.chat_id
  i: int = 0

  if not locked:
    lock_level: int = client._ustorage.get_lock_level(chat_id)
    while lock_level > 0 and i <= NEXT_RETRY_COUNT:
      if lock_level == NEXT_LOCK_LEVEL:
        return

      await asyncio.sleep(NEXT_SLEEP)
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

  await client.player_next(chat_id)
  if not locked:
    client._ustorage.unlock_chat(chat_id)


client.start()
callapi.start()
idle()
