from pyrogram.errors.exceptions.bad_request_400 import (
  MessageIdInvalid,
  MessageNotModified
)

from typing import Dict, Optional, List
from pyrogram.types import Message
from pyrogram.client import Client
from datetime import datetime
from yt_dlp import YoutubeDL
import re

# For linting
from stub import *


youtube_regex = re.compile(
  r'(?:https?:\/\/)?(?:www\.)?youtu(?:\.be\/|be.com\/\S*(?:watch|embed)(?:(?:(?=\/[-a-zA-Z0-9_]{11,}(?!\S))\/)|(?:\S*v=|v\/)))([-a-zA-Z0-9_]{11,})')
ytdl: YoutubeDL = YoutubeDL()


class Module:
  def __init__(self, bot: Client):
    self.bot: Client = bot

  async def install(self) -> None:
    self.bot.goodies = self

  def format_duration(
    self, time: int
  ) -> str:
    ans: str = ''
    if time >= 60*60:
      temp: int = int(time / (60 * 60))
      ans += str(temp) + ':'
      time -= temp * 60 * 60

    return ans + f'{int(time / 60):0>2}:{time % 60:0>2}'

  def format_sd(
    self, context: 'Context',
    data: 'SongData',
    elapsed: Optional[int] = None,
    key: str = 'gd_sdata'
  ) -> str:
    # TODO: i18n genre
    return self.bot.i18n[context][key].format(
      author=data.author or self.bot.i18n[context]['gd_noauthor'],
      title=data.title or self.bot.i18n[context]['gd_notitle'],
      album=data.album or self.bot.i18n[context]['gd_noalbum'],
      genre=data.genre or self.bot.i18n[context]['gd_nogenre'],
      year=data.year or self.bot.i18n[context]['gd_noyear'],
      url=data.url,

      lyricist=data.lyricist or self.bot.i18n[context]['gd_nolcst'],
      elapsed=(
        self.format_duration(elapsed) if elapsed is not None
        else None
      ) or '?',

      duration=(
        self.format_duration(data.duration) if data.duration is not None
        else None
      ) or '?',
    )

  async def update_status(
    self, context: 'Context', text: str,
    title: Optional[str] = None
  ) -> Optional[Message]:
    # TODO: Format correctly & check for id separation
    msgtext: str = self.bot.i18n[context]['gd_container'].format(
      title=title or self.bot.i18n[context]['gd_deftitle'],
      content='\n'.join([('╠ ' if x else '║') + x for x in text.split('\n')])
    )

    out: Optional[Message] = None
    if context.logging:
      try:
        out = await self.bot.edit_message_text(
          chat_id=context.log_id,
          message_id=context.status_id,
          text=msgtext
        )

      except MessageIdInvalid:
        out = await self.bot.send_message(
          chat_id=context.log_id,
          text=msgtext
        )

        context.status_id = out.id

      except MessageNotModified:
        return None

    return out

  async def song_from_url(self, url: str) -> 'SongData':
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
        params: List[str] = url.rsplit('?', 1)[1].split('&')

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
        if self.bot.config.get('youtube_sname_parsing', True):
          if title.lower().startswith(author.lower()):
            if ' - ' in title:
              sp = title.split(' - ', 1)
              author = sp[0]
              title = sp[1]
        
        year = datetime.fromtimestamp(info['timestamp']).year
        nurl = info['webpage_url']
    
    return self.bot.ustorage.SongData(
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
    self, context: 'Context', exc: Exception,
    trace: str, method: str
  ) -> None:
    print(f'OPTIMISTICALLY I THOUGHT THIS WOULD NEVER BE CALLED (from {method})')
    print(f'  {type(exc).__name__}: {str(exc)}')
    print(trace)
