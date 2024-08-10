"""
    Lock API for UStorage
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Optional
from datetime import datetime
import traceback
import asyncio
import time

from asyncpg.connection import Connection
from asyncpg import Record

from stub import MetaClient, MetaModule
import stub


@dataclass
class ChatLock:
    """
    Basic data structure for Chat Locks
    It holds two parameters:
    - level:int     -> The current lock level
    - timestamp:int -> ChatLock creation time
    """

    level: int
    timestamp: int

ChatLockTuple = tuple[int, int]


class Module(MetaModule):
    """
    Lock API Module

    Provides methods for saving Lock Data to the DB,
    allowing the bot to have lock states. In those
    states, the bot will not answer any operation
    that blocks the logic, or acceses logic of the
    same level.
    """

    goodies: MetaModule

    query_upd: str = '''
        INSERT INTO Telegram.ChatLock
        VALUES ($1, $2)
        ON CONFLICT (voice_id) DO
        UPDATE SET data=$2
    '''

    query_get: str = '''
        SELECT data FROM Telegram.ChatLock
        WHERE voice_id=$1
    '''

    query_del: str = '''
        DELETE FROM Telegram.ChatLock
        WHERE voice_id=$1
    '''


    def __init__(self, client: MetaClient, db: MetaModule):
        self.identifier = 'Lock'
        self.client: MetaClient = client
        self.db: MetaModule = db

    async def setup(self) -> None:
        async with self.db.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute('''
                    DO $$
                    BEGIN
                        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'lockdata') THEN
                            CREATE TYPE Telegram.LockData AS (
                                level integer,
                                timestamp timestamp
                            );
                        END IF;
                    END $$;

                    CREATE TABLE Telegram.ChatLock (
                        voice_id bigint unique,
                        data Telegram.LockData
                    );
                ''')

    async def install(self) -> None:
        self.db.acquire_lock = self.acquire_lock
        self.db.unlock_chat = self.unlock_chat
        self.db.lock_chat = self.lock_chat
        self.db.lock_time = self.lock_time
        self.db.use_lock = self.use_lock

        self.client.register_configuration(self, {
            'LockSt_AutoUnlock': True,
            'LockSt_Threeshold': 240,
            'LockSt_AcquireTries': 10,
            'LockSt_AcquireSleep': 500
        })

    async def post_install(self) -> None:
        self.goodies, = self.client.require_modules(('Goodies',))
        async with self.db.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute('''
                    DELETE FROM Telegram.ChatLock;
                ''')

    async def db_init(self, conn: Connection) -> None:
        def encoder(data: ChatLock) -> ChatLockTuple:
            return data.level, data.timestamp

        def decoder(data: ChatLockTuple) -> ChatLock:
            return ChatLock(
                level=data[0],
                timestamp=data[1]
            )

        await conn.set_type_codec(
            typename='lockdata',
            schema='telegram',
            format='tuple',
            encoder=encoder,
            decoder=decoder
        )


    async def lock_chat(
        self, context: 'stub.Context',
        lock_level: int = 1
    ) -> float:
        """Locks a chat

        Parameters
        ----------
        context
            The context of the chat
        lock_level
            Target lock level

        Returns
        -------
        float
            The timestamp of the lock event (used as a lock_id)
        """

        key: datetime
        async with self.db.pool.acquire() as conn:
            async with conn.transaction():
                key = datetime.now()
                await conn.execute(self.query_upd,
                    context.voice_id, ChatLock(lock_level, key))

        return key.timestamp()

    async def unlock_chat(
        self, context: 'stub.Context'
    ) -> None:
        """Unlocks a chat

        Parameters
        ----------
        context
            The context of the chat
        """

        async with self.db.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(self.query_del, context.voice_id)

    async def lock_time(
        self, context: 'stub.Context'
    ) -> Optional[float]:
        """Retrieves the timestamp of the last lock

        Parameters
        ----------
        context
            The context of the chat

        Returns
        -------
        float | None
            the timestamp of the lock event (used as a lock_id)
            (if it exist's)
        """

        ltime: Optional[float] = None
        async with self.db.pool.acquire() as conn:
            async with conn.transaction():
                record: Optional[Record] = await conn.fetchrow(
                    self.query_get, context.voice_id)

                if record:
                    ltime = record['data'].timestamp.timestamp()
        return ltime

    async def acquire_lock(
        self, context: 'stub.Context',
        lock_level: int = 1
    ) -> float:
        sleep_time: float = self.client.config['LockSt_AcquireSleep'] / 1000
        acquire_tries: int = self.client.config['LockSt_AcquireTries']
        auto_unlock: bool = self.client.config['LockSt_AutoUnlock']
        threeshold: int = self.client.config['LockSt_Threeshold']

        times: int = 0
        while times < acquire_tries:
            if times > 0:
                await asyncio.sleep(sleep_time)
            times += 1

            lockt: Optional[float] = await self.lock_time(context)
            if lockt:
                if not auto_unlock or (time.time() - lockt) <= threeshold:
                    continue

                await self.unlock_chat(context)

            lock_id: float = await self.lock_chat(context, lock_level)
            await asyncio.sleep(0.1)

            if lock_id != await self.lock_time(context):
                continue

            return lock_id

        # 'Brute force' the Lock Mechanism
        # TODO: Test the case of 4 threads trying to acquire lock
        #       at the same time

        lock_id: float
        while True:
            lock_id = await self.lock_chat(context, lock_level)
            await asyncio.sleep(0.1)
            if lock_id == await self.lock_time(context):
                break

        return lock_id


    def use_lock(
        self, method: Callable,
        lock_level: int = 1
    ) -> Callable:
        async def new_method(*args, **kwargs) -> Any:
            use_lock: bool = True
            if 'use_lock' in kwargs:
                use_lock = kwargs.pop('use_lock') is not False

            context = args[2]
            if use_lock:
                await self.acquire_lock(context, lock_level)

            data: Any = None
            try:
                data = await method(*args, **kwargs)

            except Exception as e:
                await self.goodies.report_error(
                    context, e, traceback.format_exc(),
                    method.__name__)

            if use_lock:
                await self.unlock_chat(context)
            return data
        return new_method


    def stub(self, root: dict[str, Any]) -> None:
        root['ustorage'].update({
            'lock_chat': Callable[['stub.Context', int], float],
            'unlock_chat': Callable[['stub.Context'], None],
            'lock_time': Callable[['stub.Context'], Optional[float]],
            'use_lock': Callable[[Callable, int], Callable]
        })
