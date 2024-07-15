from pytgcalls.exceptions import NotInCallError, NoActiveGroupCall
from pyrogram.handlers.message_handler import MessageHandler
from typing import Optional, Dict, List
from pyrogram.types import Message
from pyrogram import filters
import validators

# For linting
from stub import *


class Module:
  def __init__(self, bot: 'MainClient'):
    self.bot: 'MainClient' = bot
    self.ustorage: Optional['Module'] = None

  async def install(self):
    common = filters.group
    self.ustorage = self.bot.ustorage
    self.handlers: Dict[str, MessageHandler] = {
      'play': MessageHandler(
        self.ustorage.Contextualize(
          self.ustorage.UseLock(self.play),
          auto_update=False),
        filters.command('play') & common
      ),
      'pause': MessageHandler(
        self.ustorage.Contextualize(
          self.ustorage.UseLock(self.pause)),
        filters.command('pause') & common
      ),
      'resume': MessageHandler(
        self.ustorage.Contextualize(
          self.ustorage.UseLock(self.resume)),
        filters.command('resume') & common
      ),
      'next': MessageHandler(
        self.ustorage.Contextualize(
          self.ustorage.UseLock(self.next)),
        filters.command('next') & common
      ),
      'volume': MessageHandler(
        self.ustorage.Contextualize(
          self.ustorage.UseLock(self.volume)),
        filters.command('volume') & common
      ),
      'stop': MessageHandler(
        self.ustorage.Contextualize(
          self.ustorage.UseLock(self.stop)),
        filters.command('stop') & common
      ),
      'status': MessageHandler(
        self.ustorage.Contextualize(
          self.ustorage.UseLock(self.status)),
        filters.command('status') & common
      ),
      'playlist': MessageHandler(
        self.ustorage.Contextualize(
          self.ustorage.UseLock(self.playlist)),
        filters.command('playlist') & common
      )
    }

    for h in self.handlers.values():
      self.bot.add_handler(h)

  async def post_install(self):
    self.player = self.bot.player
    self.goodies = self.bot.goodies


  async def play(
    self, client: 'MainClient',
    message: Message, context: 'Context'
  ) -> None:
    if not context.voice_id:
      context.voice_id = message.chat.id

    if message.text.count(' ') == 0:
      await self.goodies.update_status(
        context, self.bot.i18n[context]['gpl_nopayload'])
      return

    url: str = message.text.split(' ', 1)[1]
    if not validators.url(url):
      await self.goodies.update_status(
        context, self.bot.i18n[context]['gpl_invalidurl'])
      return

    sdata: 'SongData' = await self.goodies.song_from_url(url)
    sdata.url = url

    if await self.player.play(context, sdata) == self.player.Status.OK:
      await self.ustorage.ctx_upd(context)
      await self.player.status(context)

    else:
      # TODO: Fail gracefully
      pass

  async def pause(
    self, client: 'MainClient',
    message: Message, context: 'Context'
  ) -> Optional[bool]:
    if not context.voice_id:
      await self.goodies.update_status(
        context, self.bot.i18n[context]['pl_novoice'])
      return False

    try:
      await self.player.pause(context)
      await self.goodies.update_status(
        context, self.bot.i18n[context]['gpl_paused'])

    except NotInCallError:
      await self.goodies.update_status(
        context, self.bot.i18n[context]['pl_novoice'])
      return False

  async def resume(
    self, client: 'MainClient',
    message: Message, context: 'Context'
  ) -> Optional[bool]:
    if not context.voice_id:
      await self.goodies.update_status(
        context, self.bot.i18n[context]['pl_novoice'])
      return False

    try:
      await self.player.resume(context)
      await self.goodies.update_status(
        context, self.bot.i18n[context]['gpl_resumed'])

    except NotInCallError:
      await self.goodies.update_status(
        context, self.bot.i18n[context]['pl_novoice'])
      return False

  async def next(
    self, client: 'MainClient',
    message: Message, context: 'Context'
  ) -> Optional[bool]:
    if not context.voice_id:
      await self.goodies.update_status(
        context, self.bot.i18n[context]['pl_novoice'])
      return False

    try:
      await self.player.next(context)

    except NotInCallError:
      await self.goodies.update_status(
        context, self.bot.i18n[context]['pl_novoice'])
      return False

  async def volume(
    self, client: 'MainClient',
    message: Message, context: 'Context'
  ) -> Optional[bool]:
    if not context.voice_id:
      await self.goodies.update_status(
        context, self.bot.i18n[context]['pl_novoice'])
      return False

    if message.text.count(' ') == 0:
      await self.goodies.update_status(
        context, self.bot.i18n[context]['gpl_volvale'])
      return

    ctx: str = message.text.split(' ', 1)[1]
    try:
      await self.player.api.change_volume_call(
        context.voice_id, int(ctx))
      await self.goodies.update_status(
        context, self.bot.i18n[context]['gpl_volupd'].format(ctx))

    except ValueError:
      await self.goodie.supdate_status(
        context, self.bot.i18n[context]['gpl_volvale'])
      return

    except (NotInCallError, NoActiveGroupCall, AttributeError):
      await self.goodies.update_status(
        context, self.bot.i18n[context]['pl_novoice'])
      return False

  async def stop(
    self, client: 'MainClient',
    message: Message, context: 'Context'
  ) -> Optional[bool]:
    if not context.voice_id:
      await self.goodies.update_status(
        context, self.bot.i18n[context]['pl_novoice'])
      return False

    try:
      await self.player.stop(context)
      await self.goodies.update_status(
        context, self.bot.i18n[context]['gpl_stopped'])

    except (NoActiveGroupCall, NotInCallError):
      await self.goodies.update_status(
        context, self.bot.i18n[context]['pl_novice'])

    return False

  async def status(
    self, client: 'MainClient',
    message: Message, context: 'Context'
  ) -> Optional[bool]:
    if not context.voice_id:
      await self.goodies.update_status(
        context, self.bot.i18n[context]['pl_novoice'])
      return False
    await self.player.status(context)

  async def playlist(
    self, client: 'MainClient',
    message: Message, context: 'Context'
  ) -> Optional[bool]:
    await self.goodies.report_error(context, Exception('Juan'), 'xd', 'owo:2')
    if not context.voice_id:
      await self.goodies.update_status(
        context, self.bot.i18n[context]['pl_novoice'])
      return False

    data: List['SongData'] = await self.ustorage.pl_fetch(
      context.voice_id)
    if not data:
      await self.goodies.update_status(
        context, self.bot.i18n[context]['gpl_nonext'])
      return

    await self.goodies.update_status(
      context, self.bot.i18n[context]['gpl_playlist'].format(
        '\n\n'.join([
          self.goodies.format_sd(
            context, x, key='gd_simpledata'
          ) for x in data
        ])
      )
    )