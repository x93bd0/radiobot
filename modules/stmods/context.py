from collections.abc import Callable
from dataclasses import dataclass
from typing import Optional, Any

from pyrogram.types import Message, CallbackQuery, Update
from pyrogram import Client

from asyncpg.connection import Connection
from asyncpg import Record

from stub import MetaClient, MetaModule


@dataclass
class Context:
    """Basic data structure that holds the context of any chat.

    Notes
    -----
    This class should not be created manually, as there are methods
    for doing so (see Module.ctx_new)

    Attributes
    ----------
    voice_id
        A Group/Channel ID for the player to do the main logic
    log_id
        A Group/Channel/User ID for the player to log current
        status of the playing
    logging
        Enables/Disables the logging on the current session
        making log_id directly dependant on this attribute
    lang_code
        The language to be used by the bot
    status_id
        The last update message ID, it may be used for not to
        repeat many messages on the Chat
    """

    voice_id: int = 0
    log_id: int = 0
    logging: bool = False
    lang_code: str = 'en'
    status_id: int = -1

ContextTuple = tuple[int, bool, str, int]


class Module(MetaModule):
    i18n: MetaModule

    query_new: str = '''
        INSERT INTO Telegram.Context VALUES($1, $2)
        ON CONFLICT (voice_id) DO UPDATE
            SET context = excluded.context;
    '''

    query_byvoice: str = '''
        SELECT context::Telegram.ContextObj FROM Telegram.Context
        WHERE voice_id = $1
    '''

    query_bylogid: str = '''
        SELECT voice_id, context::Telegram.ContextObj FROM Telegram.Context
        WHERE (context).log_id = $1
    '''

    query_byaid: str = '''
        SELECT voice_id, context::Telegram.ContextObj FROM Telegram.Context
        WHERE (context).log_id = $1 OR voice_id = $1
        LIMIT 1
    '''

    query_delete: str = '''
        DELETE FROM Telegram.Context
        WHERE voice_id = $1
    '''


    def __init__(self, client: MetaClient, db: MetaModule):
        self.identifier: str = 'Context'
        self.client: MetaClient = client
        self.db: MetaModule = db
        self.context: Context = Context

    async def setup(self):
        async with self.db.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute('''
                    DROP SCHEMA IF EXISTS Telegram CASCADE;
                    CREATE SCHEMA Telegram;
                    DO $$
                    BEGIN
                        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'contextobj') THEN
                            CREATE TYPE Telegram.ContextObj AS (
                                log_id bigint,
                                logging boolean,
                                lang_code varchar(16),
                                status_id bigint
                            );
                        END IF;
                    END $$;
                    CREATE TABLE Telegram.Context (
                        voice_id bigint unique,
                        context Telegram.ContextObj
                    );
                ''')

    async def install(self):
        self.db.Context = Context
        self.db.c11e = self.c11e

        self.db.ctx_new = self.ctx_new
        self.db.ctx_upd = self.ctx_upd
        self.db.ctx_delete = self.ctx_delete
        self.db.ctx_get_by_aid = self.ctx_get_by_aid
        self.db.ctx_get_by_voice = self.ctx_get_by_voice
        self.db.ctx_get_by_logid = self.ctx_get_by_logid
        self.db.ctx_delete_by_voice = self.ctx_delete_by_voice

    async def post_install(self):
        self.i18n = self.client.modules['I18n']
        async with self.db.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute('''
                    DELETE FROM Telegram.Context;
                ''')

    async def db_init(self, conn: Connection) -> None:
        def encoder(data: Context) -> ContextTuple:
            return (
                data.log_id, data.logging,
                data.lang_code, data.status_id
            )

        def decoder(data: ContextTuple) -> Context:
            return Context(
                voice_id=0,
                log_id=data[0],
                logging=data[1],
                lang_code=data[2],
                status_id=data[3]
            )

        await conn.set_type_codec(
            typename='contextobj',
            schema='telegram',
            format='tuple',
            encoder=encoder,
            decoder=decoder
        )


    def c11e(
        self, method: Callable[[MetaClient, Update], Any],
        auto_update: bool = True, required: bool = False
    ) -> Callable:
        """Give context to a Telegram Handler Method

        Parameters
        ----------
        method
            Method to `contextualize`
        auto_update
            Auto update the context after a modification
            is detected when the method execution ends.
        required
            Used for disallowing method execution when
            there is no `Context` to use

        Returns
        -------
        Callable
            The new contextualized handler method
        """

        async def middle(
            client: MetaClient, update: Message | CallbackQuery
        ) -> Any:
            if isinstance(update, Message):
                chat_id: int = update.chat.id

            else:
                chat_id: int = update.message.chat.id

            context: Optional['Context'] = \
                await self.db.ctx_get_by_aid(chat_id)

            if required and not context:
                return

            if not context:
                lc: str = self.i18n.default
                if hasattr(update, 'from_user') and \
                        hasattr(update.from_user, 'language_code'):
                    lc = update.from_user.language_code

                chat: Optional[int] = None
                if hasattr(update, 'chat'):
                    chat = update.chat.id

                if chat is not None:
                    context = self.db.Context(
                        voice_id=chat,
                        log_id=chat,
                        logging=True,
                        lang_code=lc,
                        status_id=-1
                    )

            output: Any = await method(client, update, context)
            if auto_update and output is not None:
                print('delete context from')
                await self.db.ctx_upd(context)

            elif output is False and context is not None:
                await self.db.ctx_delete(context)

            return output

        return middle

    async def ctx_new(
        self, voice_id: int,
        logging: bool = True,
        log_id: Optional[int] = None,
        lang_code: Optional[str] = None,
        status_id: Optional[int] = None
    ) -> Context:
        """Creates the context based on the required data

        Parameters
        ----------
        voice_id
            Channel/Group ID for the bot to play music on
        logging
            Availability of status messages on the chat
        log_id
            Channel/Group/User ID for the status messages
        lang_code
            User language code
        status_id
            The message to be updated to reflect the status
            of the player

        Returns
        -------
        Context
            The new `Context` object
        """

        return await self.ctx_upd(Context(
            voice_id=voice_id,
            log_id=log_id or 0,
            logging=logging,
            lang_code=lang_code or
                self.i18n.default,
            status_id=status_id or -1
        ))

    async def ctx_upd(
        self, context: Context
    ) -> Context:
        """Reflects a previously created context updates on the DB

        Parameters
        ----------
        context
            The `Context` object to update, with the
            new information

        Returns
        -------
        Context
            The `Context` object
        """

        async with self.db.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(self.query_new,
                    context.voice_id, context)
        return context

    async def ctx_get_by_voice(
        self, voice_id: int
    ) -> Optional[Context]:
        """Gets an old `Context` based on its voice_id

        Parameters
        ----------
        voice_id
            The `Context` object voice id to search
        
        Returns
        -------
        Context
            The `Context` object, if it exists
        """

        context: Optional[Context] = None
        async with self.db.pool.acquire() as conn:
            row: Optional[Record] = await conn.fetchrow(
                self.query_byvoice, voice_id)

            if row:
                ctx: Context = row['context']
                ctx.voice_id = voice_id
                context = ctx
        return context

    async def ctx_get_by_logid(
        self, log_id: int
    ) -> Optional[Context]:
        """Gets an old `Context` based on its log_id

        Parameters
        ----------
        voice_id
            The `Context` object log id to search
        
        Returns
        -------
        Context
            The `Context` object, if it exists
        """

        context: Optional[Context] = None
        async with self.db.pool.acquire() as conn:
            row: Optional[Record] = await conn.fetchrow(
                self.query_bylogid, log_id)

            if row:
                ctx: Context = row['context']
                ctx.voice_id = row['voice_id']
                context = ctx
        return context

    async def ctx_get_by_aid(
        self, aid: int
    ) -> Optional[Context]:
        """Gets an old `Context` based on its voice_id or log_id

        Notes
        -----
        This method is unreliable, it may return a `Context` that
        isn't the one that was being searched in the first place

        Parameters
        ----------
        aid
            The `Context` object voice/log id to search

        Returns
        -------
        Context
            The `Context` object, if it exists
        """

        context: Optional[Context] = None
        async with self.db.pool.acquire() as conn:
            row: Optional[Record] = await conn.fetchrow(
                self.query_byaid, aid)

            if row:
                ctx: Context = row['context']
                ctx.voice_id = row['voice_id']
                context = ctx
        return context

    async def ctx_delete(
        self, context: Context
    ) -> None:
        # traceback.print_stack()
        async with self.db.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    self.query_delete, context.voice_id)

    async def ctx_delete_by_voice(
        self, voice_id: int
    ) -> None:
        async with self.db.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    self.query_delete, voice_id)


    def stub(self, root: dict[str, Any]) -> None:
        root['ustorage'].update({
            'Context': {
                '__name__': 'Context',
                'voice_id': int,
                'log_id': int,
                'logging': bool,
                'lang_code': str,
                'status_id': int
            },

            'c11e': Callable[
                [Callable, bool],
                Callable[[Client, Message | CallbackQuery], Any
            ]],

            'ctx_new': Callable[[
                int, bool, Optional[int],
                Optional[str], Optional[int]
            ], 'Context'],
            'ctx_upd': Callable[['Context'], 'Context'],
            'ctx_delete': Callable[['Context'], None],
            'ctx_get_by_aid': Callable[[int], 'Context'],
            'ctx_get_by_voice': Callable[[int], 'Context'],
            'ctx_get_by_logid': Callable[[int], 'Context'],
            'ctx_delete_by_voice': Callable[[int], None]
        })
