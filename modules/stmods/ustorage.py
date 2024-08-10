from collections.abc import Callable
from typing import Optional, Any
import importlib
import logging
import os

from asyncpg.pool import Pool, create_pool
from asyncpg.connection import Connection
from stub import  MetaClient, MetaModule


class Module(MetaModule):
    modules: dict[str, MetaModule]

    def __init__(self, client: MetaClient):
        self.identifier: str = 'UStorage'
        self.client: MetaClient = client
        self.pool: Optional[Pool] = None

    async def install(self) -> None:
        self.client.register_configuration(self, {
            'Ustorage_Modules': []
        })

        self.modules = {}
        for mod in self.client.config['Ustorage_Modules']:
            module: MetaModule = importlib.import_module(mod).Module(
                self.client, self)

            identifier: str = self.identifier + '.' + module.identifier
            logging.info('Installing `%s` module', identifier)

            module.path = mod
            await module.install()

            self.modules[module.identifier] = module

        self.pool = await create_pool(
            user=os.getenv('PDB_USER', 'admin'),
            password=os.getenv('PDB_PAWD', 'admin'),
            host=os.getenv('PDB_HOST', '127.0.0.1'),
            port=int(os.getenv('PDB_PORT', '5432')),
            database=os.getenv('PDB_NAME', 'radiobot'),
            init=self.db_init
        )

    async def setup(self) -> None:
        for mod in self.modules.values():
            if hasattr(mod, 'setup'):
                logging.info('- Setting up `ustorage[%s]`', mod.path)
                await mod.setup()

    async def post_install(self) -> None:
        for mod in self.modules.values():
            if hasattr(mod, 'post_install'):
                await mod.post_install()

    async def test_helper(self, identifier: str) -> Optional[MetaModule]:
        if identifier in self.modules:
            logging.debug('Running test of `%s` module', identifier)
            return self.modules[identifier]

    async def db_init(self, conn: Connection) -> None:
            for mod in self.modules.values():
                if hasattr(mod, 'db_init'):
                    try:
                        await mod.db_init(conn)
        
                    except Exception:
                        logging.warning(
                            'Can\'t initialize connetion with module'
                            '`%s` parameters, please check it...')


    def stub(self, root: dict[str, Any]) -> None:
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
            'stub': Callable[[dict[str, Any]], None],
            'path': str
        }

        for mod in self.client.config['Ustorage_Modules']:
            logging.info('Generating stub for ustorage module `%s`', mod)
            module: MetaClient = importlib.import_module(mod).Module(
                self.client, self)
            if hasattr(module, 'stub'):
                module.stub(root)
