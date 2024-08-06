from typing import Callable, Tuple, Any, Optional, Dict
from dataclasses import dataclass
from datetime import datetime
from asyncpg import Record
import traceback
import asyncio
import time

# For linting
from stub import MetaClient, MetaModule
import stub


@dataclass
class ChatLock:
    level: int
    timestamp: int

ChatLockTuple = Tuple[int, int]


class Module(MetaModule):
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
        self.identifier = 'StMod.Lock'
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
        self.db.lock_chat = self.lock_chat
        self.db.unlock_chat = self.unlock_chat
        self.db.lock_time = self.lock_time
        self.db.UseLock = self.UseLock

        self.client.register_configuration(self, {
            'LockSt_AutoUnlock': True,
            'LockSt_Threeshold': 5
        })

    async def post_install(self) -> None:
        self.goodies = self.client.modules['Goodies']

        def encoder(data: ChatLock) -> ChatLockTuple:
            return data.level, data.timestamp

        def decoder(data: ChatLockTuple) -> ChatLock:
            return ChatLock(
                level=data[0],
                timestamp=data[1]
            )

        async with self.db.pool.acquire() as conn:
            async with conn.transaction():
                await conn.set_type_codec(
                    typename='lockdata',
                    schema='telegram',
                    format='tuple',
                    encoder=encoder,
                    decoder=decoder
                )

                await conn.execute('''
                    DELETE FROM Telegram.ChatLock;
                ''')


    async def lock_chat(
        self, context: 'stub.Context',
        lock_level: int
    ) -> float:
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
        async with self.db.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(self.query_del, context.voice_id)

    async def lock_time(
        self, context: 'stub.Context'
    ) -> Optional[float]:
        ltime: Optional[float] = None
        async with self.db.pool.acquire() as conn:
            async with conn.transaction():
                record: Optional[Record] = await conn.fetchrow(
                    self.query_get, context.voice_id)

                if record:
                    ltime = record['data'].timestamp.timestamp()
        return ltime

    def UseLock(
        self, method: Callable,
        lock_level: int = 1
    ) -> Callable:
        async def new_method(*args, **kwargs) -> Any:
            lockp: bool = True
            if 'lockp' in kwargs:
                lockp = kwargs.pop('lockp') is not False

            context = args[2]
            lck_when: Optional[float] = await self.lock_time(context)

            if lck_when:
                if self.client.config['LockSt_AutoUnlock']:
                    if time.time() - lck_when <= \
                            self.client.config['LockSt_Threeshold']:
                        return
                    await self.unlock_chat(context)

                else:
                    return

            if lockp:
                timestamp: int = await self.lock_chat(context, lock_level)
                await asyncio.sleep(0.1)
                if timestamp != await self.lock_time(context):
                    return

            data: Any = None
            try:
                data = await method(*args, **kwargs)

            except Exception as e:
                await self.goodies.report_error(
                    context, e, traceback.format_exc(),
                    method.__name__)

            if lockp:
                await self.unlock_chat(context)
            return data
        return new_method


    def stub(self, root: Dict[str, Any]) -> None:
        root['ustorage'].update({
            'lock_chat': Callable[['stub.Context', int], float],
            'unlock_chat': Callable[['stub.Context'], None],
            'lock_time': Callable[['stub.Context'], Optional[float]],
            'UseLock': Callable[[Callable, int], Callable]
        })
