from pyrogram.handlers import MessageHandler
from pyrogram import Client, filters
from pyrogram.types import Message
from typing import Self

class Module:
  def __init__(self, client: Client) -> Self:
    self.client: Client = client
    self.st = self.client.st


  def install(self):
    # TODO: add whitelisted as common filter
    # TODO: add setting for configuring
    #       playlist command role requirements
    self.player = self.client.player
    common = ~self.st.ChatLocked & filters.group

    self.handlers: Dict[str, MessageHandler] = \
      {
        'play': MessageHandler(
          self.st.UseLock()(self.play),
          filters.command('play') & common
        ),
        'pause': MessageHandler(
          self.st.UseLock()(self.pause),
          filters.command('pause') & common
        ),
        'resume': MessageHandler(
          self.st.UseLock()(self.resume),
          filters.command('resume') & common
        ),
        'next': MessageHandler(
          self.st.UseLock(self.client.config['next_lock_level'])(self.next),
          filters.command('next') & common
        ),
        'volume': MessageHandler(
          self.st.UseLock()(self.volume),
          filters.command('volume') & common
        ),
        'stop': MessageHandler(
          self.st.UseLock()(self.stop),
          filters.command('stop') & common
        ),
        'status': MessageHandler(
          self.st.UseLock()(self.status),
          filters.command('status') & common
        ),
        'playlist': MessageHandler(
          self.playlist,
          filters.command('playlist') & common
        )
      }

    for h in self.handlers.values():
      self.client.add_handler(h)


  async def play(self, client: Client, message: Message) -> None:
    top = message
    if hasattr(message, 'reply_to_message'):
      top = message.reply_to_message

    if hasattr(top, 'audio'):
      await self.player.from_telegram(message, top.audio)
      return

    if message.text.count(' ') == 0:
      await self.client.send_status(
        message, self.client.ui(message)['no_payload_play'])
      return

    ctx: str = message.text.split(' ', 1)[1]
    if not vurl(ctx):
      await self.client.send_status(
        message, self.client.ui(message)['invalid_url'])
      return

    await self.player.play(message, ctx)


  async def pause(self, client: Client, message: Message) -> None:
    try:
      await self.player.pause(message.chat.id)
      await self.client.send_status(
        message, self.client.ui(message)['paused'])

    except NotInCallError:
      await self.client.send_status(
        message, self.client.ui(message)['not_in_voice'])


  async def resume(self, client: Client, message: Message) -> None:
    try:
      await self.player.resume(message.chat.id)
      await self.client.send_status(
        message, self.client.ui(message)['resumed'])

    except NotInCallError:
      await self.client.send_status(
        message, self.client.ui(message)['not_in_voice'])
      return


  async def next(self, client: Client, message: Message) -> None:
    try:
      await self.player.next(message.chat.id)

    except NotInCallError:
      await self.client.send_status(
        message, self.client.ui(message)['not_in_voice'])
      return


  async def volume(self, client: Client, message: Message) -> None:
    if message.text.count(' ') == 0:
      await self.client.send_status(
        message, self.client.ui(message)['volume_valueerror'])
      return

    ctx: str = message.text.split(' ', 1)[1]
    try:
      await self.player.api.change_volume_call(message.chat.id, int(ctx))
      await self.client.send_status(
        message, self.client.ui(message)['volume_set_to'].format(int(ctx)))

    except ValueError:
      await self.client.send_status(
        message, self.client.ui(message)['volume_valueerror'])

    except (NotInCallError, NoActiveGroupCall, AttributeError):
      await self.client.send_status(
        message, self.client.ui(message)['not_in_voice'])


  async def stop(self, client: Client, message: Message) -> None:
    try:
      await self.player.stop(message.chat.id)
      await self.client.send_status(
        message, self.client.ui(message)['stopped'])

    except (NoActiveGroupCall, NotInCallError):
      await message.reply(self.client.ui(message)['not_in_voice'])
    self.client.ustorage.clean_playlist(message.chat.id)


  async def status(self, client: Client, message: Message) -> None:
    await self.player.send_playing(message)


  async def playlist(self, client: Client, message: Message) -> None:
    size: int = self.client.ustorage.playlist_size(message.chat.id)
    if size == 0:
      await self.client.send_status(
        message, self.client.ui(message)['not_in_voice'])
      return

    pidx: int = self.client.ustorage.playlist_dsize(message.chat.id)
    songs: List[str, int, str, str] = \
      self.client.ustorage.fetch_playlist(message.chat.id, 10)
    strings: Dict[str, str] = self.client.ui(message)

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

    await message.reply(
      strings['fmt'].format(strings['pltitle'], o_songs.strip()))
