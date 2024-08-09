"""
    Main Bot Code
"""
# TODO: Better Stub's

from collections.abc import Callable
from typing import Any, Optional
import importlib.util
import importlib
import os.path
import logging
import asyncio
import json
import uvloop
import click

from pyrogram.client import Client
from pyrogram.sync import idle

from pytgcalls import PyTgCalls
from dotenv import load_dotenv

from stub import (
    MetaClient, MetaModule, MainException,
    SettingsCollision, InvalidSettings
)


class MainClient(MetaClient):
    userbot: Client
    api: PyTgCalls

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.modules: dict[str, MetaModule] = {}
        self.config: dict[str, Any] = {}
        self.defby: dict[str, MetaModule] = {}

    def require_configuration(
        self, module: MetaModule | MetaClient,
        config: str
    ) -> None:
        if config not in self.config:
            raise InvalidSettings(
                f'Settings key `{config}` is not defined ' +
                f'(and it\'s required by {module.identifier})')

    def register_configuration(
        self, module: MetaModule | MetaClient,
        config: dict[str, dict[str, str]],
        check_collisions: bool = True
    ) -> None:
        for k, v in config.items():
            if k not in self.config:
                self.config[k] = v
                self.defby[k] = module

            elif check_collisions:
                if k in self.defby:
                    raise SettingsCollision(
                        f'Configuration `{k}` is already used by module ' +
                        f'`{self.defby[k].identifier}`' +
                        f'(requested by module `{module.identifier}`)'
                    )

                self.defby[k] = module


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
        logging.basicConfig(level=logging.DEBUG)

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

    bot.api = PyTgCalls(bot.userbot)
    bot.api.mainbot = bot

    bot.config.update(config)
    bot.require_configuration(bot, 'BaseModules')

    for mod in bot.config['BaseModules']:
        module: MetaModule = importlib \
            .import_module(mod) \
            .Module(bot)

        if module.identifier in bot.modules:
            raise MainException(
                f'Module `{module.identifier}` has two options ' +
                f'({type(bot.modules[module.identifier]).__module__}' +
                f' and {mod})'
            )

        bot.modules[module.identifier] = module

    return bot



@click.group()
def cli():
    pass


async def async_run(
    setup_mode: bool = False
) -> None:
    bot: MainClient = await _setup()

    for v in bot.modules.values():
        logging.debug(
            'Installing `%s` module', v.identifier)
        await v.install()
    logging.info('Installed modules!')
    
    if setup_mode:
        for v in bot.modules.values():
            logging.debug('Setting up `%s` module', v.identifier)
            await v.setup()
        logging.info('Setted up all modules!')
        return

    for v in bot.modules.values():
        logging.debug(
            'Running post-install of module `%s`', v.identifier)
        await v.post_install()
    logging.info('Ran `post-install` method of every module')

    logging.info('Starting bot')
    await bot.start()

    logging.info('Starting userbot')
    await bot.api.start()

    logging.info('Idling')
    await idle()

@cli.command()
@click.option(
    '--setup', '-s', 'setup_mode',
    is_flag=True)
def run(setup_mode: bool):
    asyncio.run(async_run(setup_mode))


async def async_test() -> None:
    bot: MainClient = await _setup()
    bot.require_configuration(bot, 'tests')

    for v in bot.modules.values():
        logging.debug('Installing `%s` module', v.identifier)
        await v.install()

    tests: dict[str, dict[str, list[Callable]]] = {}
    for k in bot.modules.keys():
        tests[k] = {}

    for testmod in bot.config['tests']:
        spec: Any = importlib.util.spec_from_file_location(
            os.path.normpath(testmod).replace('/', '.'),
            testmod)

        mod: Any = spec.loader.load_module()
        tmod: str = mod.test_module

        if tmod not in tests:
            continue

        steps: dict[str, Callable] = mod.steps
        for step, cbl in steps.items():
            if step not in tests[tmod]:
                tests[tmod][step] = [cbl]

            else:
                tests[tmod][step].append(cbl)

    for mod, tdata in tests.items():
        if 'install' in tdata:
            module: MetaModule = bot.modules[mod]
            identifier: str = module.identifier

            logging.info('Running test_install of `%s` module (0/%d)',
                identifier, len(tdata['install']))

            no: int = 1
            for cbl in tdata['install']:
                resp: Optional[Exception] = await cbl(module)

                if resp:
                    logging.debug('Raising exception from test_install of `%s`',
                        identifier)
                    raise resp

                logging.info('Running test_install of `%s` module (%d/%d)',
                    identifier, no, len(tdata['install']))
                no += 1

    for v in bot.modules.values():
        logging.debug('Running post-install of `%s` module', v.identifier)
        await v.post_install()

    for mod, tdata in tests.items():
        if 'post_install' in tdata:
            module: MetaModule = bot.modules[mod]
            identifier: str = module.identifier

            logging.info('Running test_post_install of `%s` module (0/%d)',
                identifier, len(tdata['post_install']))

            no: int = 1
            for cbl in tdata['post_install']:
                resp: Optional[Exception] = await cbl(module)

                if resp:
                    logging.debug('Raising exception from test_post_install of `%s`',
                        identifier)
                    raise resp

                logging.info('Running test_post_install of `%s` module (%d/%d)',
                    identifier, no, len(tdata['post_install']))
                no += 1
                await cbl(bot.modules[mod])

@cli.command()
def test() -> None:
    asyncio.run(async_test())


async def async_stub():
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

@cli.command()
def stub():
    asyncio.run(async_stub())


if __name__ == '__main__':
    uvloop.install()
    cli()
