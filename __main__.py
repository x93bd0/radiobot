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
from ntgcalls import FFmpegError
from pytgcalls import PyTgCalls
import asyncio
import storage
import json
import os


# TODO: Modify last 'playing' status message on next
# TODO: Protect from accesing files
# TODO: Implement playlist limit
# TODO: Implement permissions
# TODO: Implement group language


NEXT_RETRY_COUNT: int = 15
NEXT_SLEEP: float = 0.5
MSGID_THREESHOLD: int = 5


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
  await message.reply_text('Prueba')


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
  try:
    await callapi.get_active_call(message.chat.id)
    # TODO: Validate url & inform user
    client._ustorage.playlist_enqueue(message.chat.id, ctx)
    return

  except GroupCallNotFound:
    pass

  info: Message = \
    await client.send_status(message, client.ui(message)['joining_voice'])
  try:
    await userbot.get_chat(message.chat.id)

  except ChannelInvalid:
    await info.edit_text(client.ui(message)['generating_link'])

    link: ChatInviteLink
    try:
      link = await client.create_chat_invite_link(
        message.chat.id, name='RadioBot Link', member_limit=1)

    except ChatAdminRequired:
      await info.edit_text(client.ui(messagae)['cant_generate_link'])
      return

    try:
      await info.edit_text(client.ui(message)['joining_chat'])
      await userbot.join_chat(link.invite_link)

    except InviteHashExpired:
      await info.edit_text(client.ui(message)['cant_join_chat'])
      return

  # TODO: Detect whether group call is inactive or else
  await callapi.join_group_call(message.chat.id, MediaStream(
    ctx, video_flags=MediaStream.IGNORE,
    audio_flags=MediaStream.REQUIRED
  ))

  await info.edit_text(client.ui(message)['playing'].format(0, ctx))


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


@callapi.on_stream_end()
async def next_callback(_: PyTgCalls, update: Update) -> None:
  chat_id: int = update.chat_id
  i: int = 0
  while client._ustorage.is_locked(chat_id) and i <= NEXT_RETRY_COUNT:
    await asyncio.sleep(NEXT_SLEEP)
    i += 1

  if i - 1 == NEXT_RETRY_COUNT:
    return

  _id: int = client._ustorage.lock_chat(chat_id)
  await asyncio.sleep(0.1)
  if _id != client._ustorage.get_lock_time(chat_id):
    await asyncio.sleep(1)
    next_callback(_, update)
    return  # Another method is running

  _next: Tuple[int, str] = client._ustorage.playlist_dequeue(chat_id)
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
    client._ustorage.unlock_chat(chat_id)
    return await next_callback(_, update)

  except:
    # TODO: Implement this & throw error
    client._ustorage.clean_playlist(chat_id)
  client._ustorage.unlock_chat(chat_id)


client.start()
callapi.start()
idle()
