from typing import Optional, Any, Callable
import importlib
import logging
import os

from asyncpg.pool import Pool, create_pool
from stub import  MetaClient, MetaModule


class Module(MetaModule):
    modules: list[MetaModule]

    def __init__(self, client: MetaClient):
        self.identifier: str = 'UStorage'
        self.client: MetaClient = client
        self.pool: Optional[Pool] = None

    async def install(self) -> None:
        self.client.register_configuration(self, {
            'Ustorage_Modules': []
        })

        self.pool = await create_pool(
            user=os.getenv('PDB_USER', 'admin'),
            password=os.getenv('PDB_PAWD', 'admin'),
            host=os.getenv('PDB_HOST', '127.0.0.1'),
            port=int(os.getenv('PDB_PORT', '5432')),
            database=os.getenv('PDB_NAME', 'radiobot')
        )

        self.modules = []
        for mod in self.client.config['Ustorage_Modules']:
            logging.info('Installing ustorage module `%s`', mod)
            module: MetaModule = importlib.import_module(mod).Module(
                self.client, self)

            module.path = mod
            await module.install()
            self.modules.append(module)

    async def setup(self) -> None:
        for mod in self.modules:
            if hasattr(mod, 'setup'):
                logging.info('- Setting up ustorage[%s]', mod.path)
                await mod.setup()

    async def post_install(self) -> None:
        for mod in self.modules:
            if hasattr(mod, 'post_install'):
                await mod.post_install()

    async def test(self) -> None:
        for mod in self.modules:
            if hasattr(mod, 'test'):
                logging.info('- Testing ustorage[%s]', mod.path)
                await mod.test()


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
