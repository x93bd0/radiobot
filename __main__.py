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

from typing import Self, Dict, Any, Callable, Union, Optional, Tuple
from pytgcalls.types import MediaStream, AudioQuality, Update
from pytgcalls import PyTgCalls, filters as pfilters
from pyrogram.types import ChatInviteLink, Message
from pyrogram import Client, filters, idle, enums
from validators import url as vurl
from ntgcalls import FFmpegError
import traceback
import asyncio
import storage
import json
import os

if 'DEBUG' in os.environ:
  import tracemalloc
  tracemalloc.start()


# TODO: Implement status command
# TODO: Implement ignore(n) command
# TODO: Implement playlist limit
# TODO: Implement permissions
# TODO: Implement group language
# TODO: Implement player_* methods
# TODO: Implement playing from telegram audios
# TODO: Add song_time to playlist storage


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

  def _extract_language(self, message: Optional[Message], default: str = 'en') -> str:
    if not message or not hasattr(message, 'from_user') or \
        not hasattr(message.from_user, 'language_code'):
      return default
    lc: str = message.from_user.language_code
    if lc not in self.pseudo_ui:
      return default
    return lc

  def to_strtime(self, time: int) -> str:
    # TODO: Test
    if time > 59 * 60 + 60:
      return '{:0>2}:{:0>2}:{:0>2}'.format(
        int(time / 3600), int((time % 3600) / 60), int((time % 3600) % 60))
    return '{:0>2}:{:0>2}'.format(int(time / 60), int(time % 60))

  def cidnmsg(self, message: Union[Message, int]) -> Tuple[Optional[Message], int]:
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

  async def player_play(self, chat_id: Union[Message, int], url: str) -> None:
    message: Optional[Message]
    cid: int

    message, cid = self.cidnmsg(chat_id)
    if cid in (await callapi.calls):
      idx: int = self._ustorage.playlist_enqueue(
        cid, url)
      await self.send_status(
        message, self.ui(message)['enqueued'].format(idx, url))
      return

    info: Message = \
      await self.send_status(message, client.ui(message or cid)['joining_voice'])

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
      await callapi.play(cid, MediaStream(
        url, video_flags=MediaStream.Flags.IGNORE,
        audio_flags=MediaStream.Flags.REQUIRED
      ))

    except ChatAdminRequired:
      await info.edit_text(client.ui(message)['no_chat'])
      return

    except (NoAudioSourceFound, YtDlpError, FFmpegError, FileNotFoundError, AttributeError):
      # TODO: Better error
      await info.edit_text("ERROR")
      return

    self._ustorage.playlist_enqueue(cid, url)
    await self.player_playing(message)

  # TODO: Support message input
  async def player_next(self, chat_id: int) -> None:
    _next: Optional[Tuple[int, str, str, str]] = client._ustorage.playlist_dequeue(chat_id)
    if not _next:
      try:
        await callapi.leave_call(chat_id)
      except (NoActiveGroupCall, NotInCallError):
        pass
      await client.send_status(chat_id, client.ui({})['stream_ended'])
      return

    try:
      await callapi.play(chat_id, MediaStream(
        _next[1], video_flags=MediaStream.Flags.IGNORE,
        audio_flags=MediaStream.Flags.REQUIRED))
      await self.player_playing(chat_id)

    except (NoAudioSourceFound, YtDlpError, FFmpegError, FileNotFoundError):
      return await self.player_next(chat_id)

    except Exception as e:
      # TODO: report error
      print(traceback.format_exc())
      print("Unhandled exception", e)
      client._ustorage.clean_playlist(chat_id)

  async def player_stop(self, chat_id: int) -> None:
    pass

  async def player_resume(self, chat_id: int) -> None:
    pass

  async def player_playing(
    self, message: Union[Message, int],
    data: Optional[Tuple[str, int, str, str]] = None
  ) -> None:
    elapsed: int
    chat_id: int

    _, chat_id = self.cidnmsg(message)
    strings: Dict[str, str] = client.ui(message)

    try:
      elapsed = await callapi.played_time(chat_id)
      if not data:
        data = client._ustorage.playlist_actual(chat_id)

      if not data:
        raise NotInCallError()

    except NotInCallError:
      client._ustorage.clean_playlist(chat_id)
      await client.send_status(message, strings['not_in_voice'])
      return

    song: str
    if data[2] != '' or data[3] != '':
      song = strings['songfmt_wauthor'].format(
        data[0], data[1],
        data[2] or strings['no_author'],
        data[3] or strings['no_title'])

    else:
      song = strings['songfmt_nauthor'].format(
        data[0], data[1])

    await client.send_status(message, strings['playing'].format(
      song, client.to_strtime(elapsed)), title=strings['ptitle'])

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

    message, chat_id = self.cidnmsg(message)
    if message:
      _id = message.id

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



@filters.create
async def Whitelisted(_, client: CustomClient, message: Message) -> bool:
  return await client.whitelisted(message.chat.id, message.from_user.id)




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


@client.on_message(filters.command('play') & ~storage.ChatLocked & Whitelisted)
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


@client.on_message(filters.command('pause') & ~storage.ChatLocked & Whitelisted)
@storage.UseLock()
async def pause(client, message) -> None:
  try:
    await callapi.pause_stream(message.chat.id)
    await client.send_status(message, client.ui(message)['paused'])

  except NotInCallError:
    await client.send_status(message, client.ui(message)['not_in_voice'])
    return


@client.on_message(filters.command('resume') & ~storage.ChatLocked & Whitelisted)
@storage.UseLock()
async def resume(client, message) -> None:
  try:
    await callapi.resume_stream(message.chat.id)
    await client.send_status(message, client.ui(message)['resumed'])

  except NotInCallError:
    await client.send_status(message, client.ui(message)['not_in_voice'])
    return


@client.on_message(filters.command('next') & ~storage.ChatLocked & Whitelisted)
@storage.UseLock(NEXT_LOCK_LEVEL)
async def cnext(client, message) -> None:
  try:
    await client.player_next(message.chat.id)

  except NotInCallError:
    await client.send_status(message, client.ui(message)['not_in_voice'])
    return


@client.on_message(filters.command('volume') & ~storage.ChatLocked & Whitelisted)
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


@client.on_message(filters.command('stop') & ~storage.ChatLocked & Whitelisted)
@storage.UseLock()
async def stop(client, message) -> None:
  try:
    await callapi.leave_call(message.chat.id)
    await client.send_status(message, client.ui(message)['stopped'])
  except (NoActiveGroupCall, NotInCallError):
    await message.reply(client.ui(message)['not_in_voice'])
  client._ustorage.clean_playlist(message.chat.id)


@client.on_message(filters.command('status') & ~storage.ChatLocked & Whitelisted)
@storage.UseLock()
async def status(client, message) -> None:
  await client.player_playing(message)


@client.on_message(filters.command('playlist') & Whitelisted)
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
        size - pidx + i + 1, song[0],
        song[2] or strings['no_author'],
        song[3] or strings['no_title']) + '\n'

    else:
      o_songs += strings['songfmt_nauthor'].format(
        size - pidx + i + 1, song[0]) + '\n'
    i += 1

  await message.reply(strings['fmt'].format(strings['pltitle'], o_songs))


@callapi.on_update(pfilters.stream_end)
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
