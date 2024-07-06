from pyrogram.handlers import MessageHandler
from pyrogram import Client, filters
from pyrogram.types import Message
from typing import Self

class Module:
  def __init__(self, client: Client) -> Self:
    self.client = client
    self.handlers = {
      'start': MessageHandler(self.start, filters.command('start') & filters.private),
      'help': MessageHandler(self.help, filters.command('help') & filters.private)
    }


  def install(self) -> None:
    for h in self.handlers.values():
      self.client.add_handler(h)

  async def start(self, client: Client, message: Message) -> None:
    await message.reply(client.ui(message)['start'])

  async def help(self, client: Client, message: Message) -> None:
    await message.reply(client.ui(message)['help'], disable_web_page_preview=True)
