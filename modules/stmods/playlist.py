from typing import Tuple, Optional, List, Dict, Callable, Any
from dataclasses import dataclass
from asyncpg import Record

# For linting
from stub import MetaClient, MetaModule


@dataclass
class SongData:
    author: str
    title: str
    album: str

    genre: str
    year: int
    lyricist: str

    duration: int
    url: str

SongDataTuple = Tuple[str, str, str, str, int, str, int, str]


class Module(MetaModule):
    query_enqueue: str = \
        '''
            INSERT INTO Player.Playlist VALUES (
                $1, $2::player.songdata, $3
            );
        '''

    query_dequeue: str = \
        '''
            SELECT data FROM Player.Playlist
            WHERE id = (
                SELECT position FROM Player.PlStatus
                WHERE voice_id = $1
            ) AND voice_id = $1;
        '''

    query_next: str = \
        '''
            UPDATE Player.PlStatus
            SET position = 1 + (
                SELECT position FROM Player.PlStatus
                WHERE voice_id = $1
            ) WHERE voice_id = $1
            RETURNING position;
        '''

    query_ustatus: str = \
        '''
            UPDATE Player.PlStatus SET size = 1 + (
                SELECT size FROM Player.PlStatus
                WHERE voice_id = $1
            ) WHERE voice_id = $1;
        '''

    query_istatus: str = \
        '''
            INSERT INTO Player.PlStatus
            VALUES ($1, 1, 0);
        '''

    query_fetch: str = \
        '''
            SELECT data FROM Player.Playlist
            WHERE voice_id = $1
            ORDER BY ctid
            OFFSET $2
            LIMIT $3;
        '''

    query_clean: str = \
        '''
            DELETE FROM Player.Playlist
            WHERE voice_id = $1;
        '''

    query_size: str = \
        '''
            SELECT size FROM Player.PlStatus
            WHERE voice_id = $1;
        '''

    query_pos: str = \
        '''
            SELECT position FROM Player.PlStatus
            WHERE voice_id = $1;
        '''


    def __init__(self, client: MetaClient, db: MetaModule):
        self.identifier: str = 'StMod.Playlist'
        self.client: MetaClient = client
        self.db: MetaModule = db

    async def setup(self) -> None:
        async with self.db.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute('''
                    DROP SCHEMA IF EXISTS Player CASCADE;
                    CREATE SCHEMA Player;
                    DO $$
                    BEGIN
                        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'songdata') THEN
                            CREATE TYPE Player.SongData AS (
                                author varchar(32),
                                title varchar(64),
                                album varchar(64),
                                genre varchar(32),
                                year integer,
                                lyricist varchar(64),
                                duration integer,
                                url varchar(256)
                            );
                        END IF;
                    END$$;
                    CREATE TABLE Player.Playlist (
                        voice_id bigint,
                        data Player.SongData,
                        id integer
                    );
                    CREATE TABLE Player.PlStatus (
                        voice_id bigint,
                        size integer,
                        position integer
                    );
                ''')

    async def install(self) -> None:
        self.db.SongData = SongData
        self.db.pl_default_data = lambda: SongData(
            author='',
            title='',
            album='',
            genre='',
            year=0,
            lyricist='',
            duration=0,
            url=''
        )

        self.db.pl_enqueue = self.pl_enqueue
        self.db.pl_dequeue = self.pl_dequeue
        self.db.pl_clean = self.pl_clean
        self.db.pl_fetch = self.pl_fetch

        self.db.pl_position = self.pl_position
        self.db.pl_size = self.pl_size

    async def post_install(self) -> None:
        def encoder(data: SongData) -> SongDataTuple:
            return (
                data.author, data.title, data.album,
                data.genre, data.year, data.lyricist,
                data.duration, data.url
            )

        def decoder(data: SongDataTuple) -> SongData:
            return SongData(*data)

        async with self.db.pool.acquire() as conn:
            async with conn.transaction():
                await conn.set_type_codec(
                    typename='songdata',
                    schema='player',
                    format='tuple',
                    encoder=encoder,
                    decoder=decoder
                )

                await conn.execute('''
                    DELETE FROM Player.Playlist;
                    DELETE FROM Player.PlStatus;
                ''')


    async def pl_enqueue(
        self, voice_id: int,
        data: SongData
    ) -> None:
        async with self.db.pool.acquire() as conn:
            async with conn.transaction():
                size: Optional[int] = await self.pl_size(voice_id)
                if size is None:
                    await conn.execute(self.query_istatus, voice_id)
                    size = 0

                else:
                    await conn.execute(self.query_ustatus, voice_id)

                await conn.execute(self.query_enqueue,
                    voice_id, data, size)

    async def pl_dequeue(
        self, voice_id: int
    ) -> Optional[Tuple[int, SongData]]:
        data: Optional[SongData] = None
        index: int = 0

        async with self.db.pool.acquire() as conn:
            async with conn.transaction():
                row: Record = await conn.fetchrow(
                    self.query_dequeue, voice_id)
                idx: Record = await conn.fetchrow(
                    self.query_next, voice_id)

                if row:
                    data = row['data']
                    index = idx['position']

        if data:
            return (index - 1, data)
        return None

    async def pl_fetch(
        self, voice_id: int,
        limit: int = 10,
        offset: Optional[int] = None
    ) -> List[SongData]:
        if offset is None:
            offset = await self.pl_position(voice_id)

        playlist: List[SongData] = []
        async with self.db.pool.acquire() as conn:
            records: List[Record] = \
                await conn.fetch(
                    self.query_fetch, voice_id, offset, limit)

            for record in records:
                playlist.append(record['data'])
        return playlist

    async def pl_clean(
        self, voice_id: int
    ) -> None:
        async with self.db.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(self.query_clean, voice_id)

    async def pl_size(
        self, voice_id: int
    ) -> Optional[int]:
        size: Optional[int] = None
        async with self.db.pool.acquire() as conn:
            row = await conn.fetchrow(self.query_size, voice_id)
            if row:
                size = row['size']
        return size

    async def pl_position(
        self, voice_id: int
    ) -> Optional[int]:
        position: Optional[int] = None
        async with self.db.pool.acquire() as conn:
            row = await conn.fetchrow(self.query_pos, voice_id)
            if row:
                position = row['position']
        return position


    def stub(self, root: Dict[str, Any]) -> None:
        root['ustorage'].update({
            'SongData': {
                '__name__': 'SongData',
                'author': str,
                'title': str,
                'album': str,
                'genre': str,
                'year': int,
                'lyricist': str,
                'duration': int,
                'url': str
            },

            'pl_default_data': Callable[[], 'SongData'],
            'pl_enqueue': Callable[[int, 'SongData'], None],
            'pl_dequeue': Callable[[int], Optional[Tuple[int, 'SongData']]],
            'pl_clean': Callable[[int], None],
            'pl_fetch': Callable[[int, int, Optional[int]], List['SongData']],
            'pl_position': Callable[[int], Optional[int]],
            'pl_size': Callable[[int], Optional[int]]
        })
