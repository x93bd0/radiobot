"""
    Telegram Goodies
"""

from datetime import datetime
from typing import Optional, Any
import re

from pyrogram.errors.exceptions.bad_request_400 import (
    MessageIdInvalid,
    MessageNotModified
)

from pyrogram.types import Message
from yt_dlp import YoutubeDL

from stub import MetaClient, MetaModule
import stub


youtube_regex = re.compile(
    r'(?:https?:\/\/)?(?:www\.)?youtu(?:\.be\/|be.com\/\S*(?:watch|embed)(?:(?:(?=\/[-a-zA-Z0-9_]{11,}(?!\S))\/)|(?:\S*v=|v\/)))([-a-zA-Z0-9_]{11,})')
ytdl: YoutubeDL = YoutubeDL()


class Module(MetaModule):
    """
    Goodies Module
    Provides methods for making the interaction
    with Telegram easier
    """

    i18n: MetaModule
    ustorage: MetaModule

    def __init__(self, client: MetaClient):
        self.identifier = 'Goodies'
        self.client: MetaClient = client
        self.cbkid: int = 0

    async def setup(self) -> None:
        pass

    async def install(self) -> None:
        self.client.register_configuration(self, {
            'Goodies_YTParseName': True,
            'Goodies_ReportErrorID': -1
        })

    async def post_install(self) -> None:
        self.i18n = self.client.modules['I18n']
        self.ustorage = self.client.modules['UStorage']

    def format_duration(
        self, time: int
    ) -> str:
        """Gives format to a period of `time` seconds

        Parameters
        ----------
        time
            The time to be formatted (time <= 24H, preferably)

        Returns
        -------
        str
            The requested time, formatted
        """

        ans: str = ''
        if time >= 60*60:
            temp: int = int(time / (60 * 60))
            ans += str(temp) + ':'
            time -= temp * 60 * 60

        return ans + f'{int(time / 60):0>2}:{time % 60:0>2}'

    def get_callback_prefix(self) -> str:
        self.cbkid += 1
        return str(self.cbkid - 1) + ' '

    def format_sd(
        self, context: 'stub.Context',
        data: 'stub.SongData',
        elapsed: Optional[int] = None,
        key: str = 'gd_sdata'
    ) -> str:
        # TODO: i18n genre
        return self.i18n[context][key].format(
            author=data.author or self.i18n[context]['gd_noauthor'],
            title=data.title or self.i18n[context]['gd_notitle'],
            album=data.album or self.i18n[context]['gd_noalbum'],
            genre=data.genre or self.i18n[context]['gd_nogenre'],
            year=data.year or self.i18n[context]['gd_noyear'],
            url=data.url,

            lyricist=data.lyricist or self.i18n[context]['gd_nolcst'],
            elapsed=(
                self.format_duration(elapsed) if elapsed is not None
                else None
            ) or '?',

            duration=(
                self.format_duration(data.duration)
                    if data.duration is not None
                else None
            ) or '?',
        )

    async def update_status(
        self, context: 'stub.Context', text: str,
        title: Optional[str] = None, **kwargs
    ) -> Optional[Message]:
        # TODO: Format correctly & check for id separation
        msgtext: str = self.i18n[context]['gd_container'].format(
            title=title or self.i18n[context]['gd_deftitle'],
            content='\n'.join([
                ('╠ ' if x else '║') + x for x in text.split('\n')])
        )

        out: Optional[Message] = None
        if context.logging:
            try:
                out = await self.client.edit_message_text(
                    chat_id=context.log_id,
                    message_id=context.status_id,
                    text=msgtext, **kwargs
                )

            except MessageIdInvalid:
                out = await self.client.send_message(
                    chat_id=context.log_id,
                    text=msgtext, **kwargs
                )

                context.status_id = out.id

            except MessageNotModified:
                return None

        return out

    async def song_from_url(self, url: str) -> 'stub.SongData':
        duration: int = 0
        year: int = 0

        lyricist: str = ''
        author: str = ''
        title: str = ''
        album: str = ''
        genre: str = ''
        nurl: str = ''

        if youtube_regex.match(url):
            info = ytdl.extract_info(url,
                download=False, process=False)

            if info['extractor'] != 'youtube':
                url = info['webpage_url']
                params: list[str] = url.rsplit('?', 1)[1].split('&')

                watchv: str = ''
                for param in params:
                    if not param.startswith('v='):
                        continue
                    watchv = param[2:]
                    break

                url = f'https://youtube.com/watch?v={watchv}'
                info = ytdl.extract_info(url,
                    download=False, process=False)

            if info['extractor'] == 'youtube':
                author = info['uploader']
                if 'artists' in info:
                    author = ' & '.join(info['artists'])

                title = info['title']
                duration = info['duration']
                if self.client.config['Goodies_YTParseName']:
                    if title.lower().startswith(author.lower()):
                        if ' - ' in title:
                            sp = title.split(' - ', 1)
                            author = sp[0]
                            title = sp[1]

                year = datetime.fromtimestamp(info['timestamp']).year
                nurl = info['webpage_url']

        return self.ustorage.SongData(
            author=author,
            title=title,
            album=album,
            genre=genre,
            year=year,
            lyricist=lyricist,
            duration=duration,
            url=nurl or url
        )

    async def report_error(
        self, context: 'stub.Context', exc: Exception,
        trace: str, method: str
    ) -> None:
        rid: int = int(self.client.config['Goodies_ReportErrorID'])
        if rid == -1:
            print('NO REPORT ID (settings.json:Goodies_ReportErrorID) DEFINED')
            print('- REPORTING ERROR TO STANDARD OUTPUT:')
            print(f'FROM `{method}` GOT {type(exc).__name__}: {str(exc)}')
            print(trace)
            return

        await self.client.send_message(
            chat_id=rid,
            text=self.i18n[context]['gd_report'].format(
                method=method,
                excname=type(exc).__name__,
                excdata=str(exc),
                trace=trace,

                ctx_voice_id=context.voice_id,
                ctx_log_id=context.log_id,
                ctx_logging=self.i18n[context]
                    ['gd_b' + str(int(context.logging))],
                ctx_statusid=context.status_id,
                ctx_langcode=context.lang_code
            )
        )

    def stub(self, root: dict[str, Any]) -> None:
        pass
