"""
    Main Bot Code
"""
# TODO: Better Stub's

from typing import Any, Optional
import os.path
import importlib
import logging
import asyncio
import json
import uvloop
import click

from pyrogram.client import Client
from pyrogram.sync import idle

from pytgcalls import PyTgCalls
from dotenv import load_dotenv

from stub import MetaClient, MetaModule, MainException


class MainClient(MetaClient):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.modules: dict[str, MetaModule] = {}
        self.config: dict[str, Any] = {}
        self.defby: dict[str, MetaModule] = {}

        self.userbot: Optional[Client] = None
        self.api: Optional[PyTgCalls] = None

    def register_configuration(
        self, module: MetaModule,
        config: dict[str, dict[str, str]],
        check_collisions: bool = False
    ) -> None:
        for k, v in config.items():
            if k not in self.config:
                self.config[k] = v
                self.defby[k] = module.identifier

            elif check_collisions:
                if k in self.defby:
                    raise MainException(
                        f'Configuration `{k}` is already used by module ' +
                        f'`{self.defby[k].identifier}`' +
                        f'(requested by `{module.identifier}`)'
                    )


class MainAPI(PyTgCalls):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mainbot: Optional[MainClient] = None


async def _setup() -> MainClient:
    load_dotenv()
    envars: dict[str, str] = {}
    for var in ['CLIENT_NAME', 'TG_API_ID', 'TG_API_HASH']:
        if var not in os.environ:
            raise MainException(
                f'Unset `{var}` environmental variable'
                ' is required for startup (it is not in .env)'
            )

        envars[var] = os.environ[var]

    if os.getenv('DEBUG', ''):
        logging.basicConfig(level=logging.INFO)

    config: dict[str, Any] = {}
    if os.path.isfile('settings.json'):
        with open('settings.json', encoding='utf-8') as cfg:
            config.update(json.load(cfg))

    bot: MainClient = MainClient(
        api_id=envars['TG_API_ID'],
        api_hash=envars['TG_API_HASH'],
        name=envars['CLIENT_NAME'])

    bot.userbot = Client(
        api_id=envars['TG_API_ID'],
        api_hash=envars['TG_API_HASH'],
        name=envars['CLIENT_NAME'] + '_userbot')

    bot.api = MainAPI(bot.userbot)
    bot.api.mainbot = bot
    bot.config.update(config)

    return bot


async def main(setup: bool, test: bool):
    bot: MainClient = await _setup()

    modules: list[MetaModule] = []
    for mod in bot.config['BaseModules']:
        logging.info('Installing module `%s`', mod)
        module: MetaModule = importlib.import_module(mod).Module(bot)
        module.path = mod
        await module.install()
        modules.append(module)

        bot.modules[module.identifier] = module

    if setup:
        for mod in modules:
            if hasattr(mod, 'setup'):
                logging.info('Setting up `%s`', mod.path)
                await mod.setup()

        logging.info('Setup sequence ended! Quitting...')
        return

    for mod in modules:
        if hasattr(mod, 'post_install'):
            await mod.post_install()

    if test:
        for mod in modules:
            if hasattr(mod, 'test'):
                logging.info('Testing `%s`', mod.path)
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

    root: dict[str, Any] = {}

    for mod in bot.config['BaseModules']:
        module: MetaModule = importlib.import_module(mod).Module(bot)
        if hasattr(module, 'stub'):
            logging.info('Generating stub for module `%s`', mod)
            module.stub(root)

    stubpy: str = importlib.import_module('stubgen').generate(root)
    with open('stub.py', 'w', encoding='utf-8') as st:
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
