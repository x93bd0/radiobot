from typing import Dict, Any, Optional, Union, List, Callable
from pyrogram.client import Client
from pytgcalls import PyTgCalls
from pyrogram.sync import idle
from dotenv import load_dotenv
import importlib
import os.path
import logging
import asyncio
import uvloop
import click
import json

# For linting
from stub import *


default_config = {
  'bot_invite_link_name': 'RadioBot link',
  'youtube_sname_parsing': True,

  'i18n_strings': 'strings.json',
  'modules': [
    'modules.ustorage',
    'modules.goodies',
    'modules.player',
    'modules.groupui'
  ],

  'ustorage_mods': [
    'modules.stmods.playlist',
    'modules.stmods.context',
    'modules.stmods.lock'
  ]
}


class i18n:
  def __init__(self, bot: 'MainClient'):
    # TODO: better practice for getting first key
    with open(bot.config['i18n_strings']) as i18n:
      temp: Dict[str, Union[str, Dict[str, str]]] = \
        json.load(i18n)

      if 'default' in temp:
        self.default: str = str(temp['default'])
        temp.pop('default')

      else:
        self.default: str = [*temp.keys()][0]
      self.strings: Dict[str, Dict[str, str]] = temp # type: ignore

  def __getitem__(self, key: 'Context') -> Dict[str, str]:
    return self.strings.get(key.lang_code, self.strings[self.default])    


class MainClient(Client):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.config: Dict[str, Any] = {}
    self.ubot: Optional[Client] = None
    self.api: Optional[PyTgCalls] = None
    self.i18n: Optional[i18n] = None


class MainAPI(PyTgCalls):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.mainbot: Optional[MainClient] = None



async def _setup() -> MainClient:
  load_dotenv()
  envars: Dict[str, str] = {}
  for var in ['CLIENT_NAME', 'TG_API_ID', 'TG_API_HASH']:
    if var not in os.environ:
      raise Exception(
        f'Unset `{var}` environmental variable'
        ' is required for startup (it is not in .env)'
      )

    envars[var] = os.environ[var]

  if os.getenv('DEBUG', False):
    logging.basicConfig(level=logging.INFO)

  config: Dict[str, Any] = default_config
  if os.path.isfile('config.json'):
    with open('config.json') as cfg:
      config.update(json.load(cfg))

  bot: MainClient = MainClient(
    api_id=envars['TG_API_ID'],
    api_hash=envars['TG_API_HASH'],
    name=envars['CLIENT_NAME'])

  bot.ubot = Client(
    api_id=envars['TG_API_ID'],
    api_hash=envars['TG_API_HASH'],
    name=envars['CLIENT_NAME'] + '_userbot')
  if os.getenv('DEBUG', False):
    logging.basicConfig(level=logging.INFO)

  config: Dict[str, Any] = default_config
  if os.path.isfile('config.json'):
    with open('config.json') as cfg:
      config.update(json.load(cfg))

  config: Dict[str, Any] = default_config
  if os.path.isfile('config.json'):
    with open('config.json') as cfg:
      config.update(json.load(cfg))

  bot: MainClient = MainClient(
    api_id=envars['TG_API_ID'],
    api_hash=envars['TG_API_HASH'],
    name=envars['CLIENT_NAME'])

  bot.ubot = Client(
    api_id=envars['TG_API_ID'],
    api_hash=envars['TG_API_HASH'],
    name=envars['CLIENT_NAME'] + '_userbot')

  bot.api = MainAPI(bot.ubot)
  bot.api.mainbot = bot
  bot.config.update(config)
  bot.i18n = i18n(bot)

  bot.api = MainAPI(bot.ubot)
  bot.api.mainbot = bot
  bot.config.update(config)
  bot.i18n = i18n(bot)

  return bot


async def main(setup: bool, test: bool):
  bot: MainClient = await _setup()

  modules: List['Module'] = []
  for mod in bot.config['modules']:
    logging.info(f'Installing module `{mod}`')
    module: 'Module' = importlib.import_module(mod).Module(bot)
    module.path = mod
    await module.install()
    modules.append(module)

  if setup:
    for mod in modules:
      if hasattr(mod, 'setup'):
        logging.info(f'Setting up `{mod.path}`')
        await mod.setup()

    logging.info('Setup sequence ended! Quitting...')
    return

  for mod in modules:
    if hasattr(mod, 'post_install'):
      await mod.post_install()

  if test:
    for mod in modules:
      if hasattr(mod, 'test'):
        logging.info(f'Testing {mod.path}')
        await mod.test()

    logging.info('Test sequence ended! Quitting...')
    return

  logging.info('Starting bot...')
  await bot.start()
  logging.info('Starting userbot api...')
  await bot.api.start()
  logging.info('Idling...')
  await idle()

async def generate_stub():
  bot: MainClient = await _setup()
  logging.info('Starting to generate stub\'s')

  root: Dict[str, Any] = {
    'bot': {
      '__name__': 'MainClient',
      'i18n': {
        '__name__': 'i18n',
        'default': str,
        '__getitem__': Callable[['Context'], Dict[str, str]]
      },
    },
    'Module': {
      '__name__': 'Module',
      'install': Callable[[], None],
      'setup': Callable[[], None],
      'post_install': Callable[[], None]
    }
  }

  for mod in bot.config['modules']:
    module: 'Module' = importlib.import_module(mod).Module(bot)
    if hasattr(module, 'stub'):
      logging.info(f'Generating stub for module `{mod}`')
      module.stub(root)

  stubpy: str = importlib.import_module('stubgen').generate(root)
  with open('stub.py', 'w') as st:
    st.write(stubpy + '\n')

  logging.info('`stub.py` generated correctly')

@click.group()
def cli():
  pass

@cli.command()
def run():
  asyncio.run(main(False, False))

@cli.command()
def setup():
  asyncio.run(main(True, False))

@cli.command()
def test():
  asyncio.run(main(False, True))

@cli.command()
def stub():
  asyncio.run(generate_stub())

if __name__ == '__main__':
  uvloop.install()
  cli()