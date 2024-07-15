from typing import Optional, Any, Dict, List, Callable
from asyncpg.pool import Pool
import importlib
import asyncpg
import logging
import os

# For linting
from stub import *


# Just a container
class Module:
  def __init__(self, bot: 'MainClient'):
    self.bot: 'MainClient' = bot
    self.pool: Optional[Pool] = None

  async def install(self) -> None:
    self.pool = await asyncpg.create_pool(
      user=os.getenv('PDB_USER', 'admin'),
      password=os.getenv('PDB_PAWD', 'admin'),
      host=os.getenv('PDB_HOST', '127.0.0.1'),
      port=int(os.getenv('PDB_PORT', 5432)),
      database=os.getenv('PDB_NAME', 'radiobot')
    )

    self.bot.ustorage = self
    self.modules: List[Module] = []
    for mod in self.bot.config['Ustorage_Modules']:
      logging.info(f'Installing ustorage module `{mod}`')
      module: 'UModule' = importlib.import_module(mod).UModule(
        self.bot, self)
      module.path = mod
      await module.install()
      self.modules.append(module)

  async def setup(self) -> None:
    for mod in self.modules:
      if hasattr(mod, 'setup'):
        logging.info(f'- Setting up ustorage[{mod.path}]')
        await mod.setup()

  async def post_install(self) -> None:
    for mod in self.modules:
      if hasattr(mod, 'post_install'):
        await mod.post_install()

  async def test(self) -> None:
    for mod in self.modules:
      if hasattr(mod, 'test'):
        logging.info(f'- Testing ustorage[{mod.path}]')
        await mod.test()


  def stub(self, root: Dict[str, Any]) -> None:
    root['ustorage'] = {
      '__name__': 'Storage',
      'pool': Optional[Pool]
    }

    root['umodule'] = {
      '__name__': 'UModule',
      'install': Callable[[], None],
      'setup': Callable[[], None],
      'post_install': Callable[[], None],
      'test': Callable[[], None],
      'stub': Callable[[Dict[str, Any]], None],
      'path': str
    }

    root['bot'].update({
      'ustorage': 'Storage'
    })

    for mod in self.bot.config['Ustorage_Modules']:
      logging.info(f'Generating stub for ustorage module `{mod}`')
      module: 'UModule' = importlib.import_module(mod).UModule(self.bot, self)
      if hasattr(module, 'stub'):
        module.stub(root)
