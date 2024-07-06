from typing import Self, Optional, Tuple, Any, Callable, List
from pyrogram import filters, Client
import traceback
import asyncio
import sqlite3
import time


class TemporaryStorage:
  def __init__(self) -> Self:
    self._db: sqlite3.Connection = sqlite3.connect(
      ':memory:', check_same_thread=False)
    self._init_db()

  def _init_db(self) -> None:
    self._db.execute(
      'create table status_msg (chat_id integer primary key, message_id integer)')
    self._db.execute(
      'create table lock_data (chat_id integer primary key, time timestamp, lock_level integer)')
    self._db.execute(
      'create table playlist (' +
        'chat_id integer, song_url varchar, song_author varchar,' +
        'song_name varchar, song_length integer, time timestamp)')
    self._db.execute(
      'create table plsize (chat_id integer, size integer)')

  def _destroy_db(self) -> None:
    self._db.execute('drop status_msg')
    self._db.execute('drop lock_data')
    self._db.execute('drop playlist')
    self._db.execute('drop plsize')


  def get_lock_level(self, chat_id: int) -> int:
    cursor: sqlite3.Cursor = self._db.cursor()
    cursor.execute(
      'select lock_level from lock_data where chat_id=?', (chat_id,))
    ret: Optional[Tuple[int]] = cursor.fetchone()
    if not ret:
      return 0
    return ret[0]

  def get_lock_time(self, chat_id: int) -> int:
    cursor: sqlite3.Cursor = self._db.cursor()
    cursor.execute(
      'select time from lock_data where chat_id=?', (chat_id,))
    ret: Optional[Tuple[int]] = cursor.fetchone()
    if not ret:
      return 0
    return ret[0]

  def is_locked(self, chat_id: int) -> bool:
    # TODO: Implement auto-unlock
    return self.get_lock_level(chat_id) > 0

  def lock_chat(self, chat_id: int, lock_level: int = 1) -> int:
    lock_level = max(lock_level, self.get_lock_level(chat_id))
    timestamp: int = time.time()
    self._db.execute(
      'insert or replace into lock_data values (?, ?, ?)',
      (chat_id, timestamp, lock_level))
    return timestamp

  def unlock_chat(self, chat_id: int) -> None:
    self._db.execute(
      'delete from lock_data where chat_id=?', (chat_id,))


  def fetch_playlist(
    self, chat_id: int, limit: int = 10
  ) -> List[Tuple[str, int, str, str, int]]:
    cursor: sqlite3.Cursor = self._db.cursor()
    cursor.execute(
      'select song_url, time, song_author, song_name, song_length ' +
      'from playlist where chat_id = ? limit ?',
      (chat_id, limit))
    ret: Optional[List[Tuple[str, int, str, str, int]]] = cursor.fetchall()
    if not ret:
      return []
    return ret

  def playlist_dsize(self, chat_id: int) -> int:
    cursor: sqlite3.Cursor = self._db.cursor()
    cursor.execute(
      'select count(*) from playlist where chat_id = ?',
      (chat_id,))
    return cursor.fetchone()[0]

  def playlist_size(self, chat_id: int) -> int:
    cursor: sqlite3.Cursor = self._db.cursor()
    cursor.execute(
      'select size from plsize where chat_id = ?', (chat_id,))
    ret: Optional[Tuple[int]] = cursor.fetchone()
    if not ret:
      return 0
    return ret[0]

  def playlist_enqueue(
    self, chat_id: int, url: str,
    author: str = '', name: str = '',
    length: int = 0
  ) -> int:
    plsize: int = self.playlist_size(chat_id)
    if plsize == 0:
      self._db.execute(
        'insert into plsize values (?, ?)',
        (chat_id, 1))

    else:
      self._db.execute(
        'update plsize set size = ? where chat_id = ?',
        (plsize + 1, chat_id))

    self._db.execute(
      'insert into playlist values (?, ?, ?, ?, ?, ?)',
      (chat_id, url, author, name, length, time.time()))
    return plsize

  def playlist_actual(
    self, chat_id: int
  ) -> Optional[Tuple[int, str, str, str, int]]:
    cursor: sqlite3.Cursor = self._db.cursor()
    cursor.execute(
      'select song_url, time, song_author, song_name, song_length ' +
      'from playlist where chat_id = ? limit 1', (chat_id,))

    ret: Optional[Tuple[str, int, str, str]] = cursor.fetchone()
    if not ret:
      return None

    return (
      self.playlist_size(chat_id) - self.playlist_dsize(chat_id),
      ret[0], ret[2], ret[3], ret[4]
    )

  def playlist_dequeue(
    self, chat_id: int
  ) -> Optional[Tuple[int, str, str, str, int]]:
    cursor: sqlite3.Cursor = self._db.cursor()
    cursor.execute(
      'select song_url, time, song_author, song_name, song_length ' +
      'from playlist where chat_id = ? limit 2', (chat_id,))

    bef: Optional[Tuple[str, int, str, str, int]] = cursor.fetchone()
    ret: Optional[Tuple[str, int, str, str, int]] = cursor.fetchone()

    if not bef or not ret:
      self._db.execute(
        'delete from plsize where chat_id = ?', (chat_id,))
      return None

    self._db.execute(
      'delete from playlist where chat_id = ? and time = ?',
      (chat_id, bef[1]))

    return (
      self.playlist_size(chat_id) - self.playlist_dsize(chat_id),
      ret[0], ret[2], ret[3], ret[4]
    )

  def clean_playlist(self, chat_id: int) -> None:
    self._db.execute(
      'delete from playlist where chat_id = ?', (chat_id,))
    self._db.execute(
      'delete from status_msg where chat_id = ?', (chat_id,))
    self._db.execute(
      'delete from plsize where chat_id = ?', (chat_id,))


  def get_last_statusmsg(self, chat_id: int) -> int:
    cursor: sqlite3.Cursor = self._db.cursor()
    cursor.execute(
      'select message_id from status_msg where chat_id = ?',
      (chat_id,))
    ret: Optional[Tuple[int]] = cursor.fetchone()
    if not ret:
      return -1
    return ret[0]

  def set_last_statusmsg(self, chat_id: int, message_id: int) -> int:
    if self.get_last_statusmsg(chat_id) == -1:
      self._db.execute(
        'insert into status_msg values (?, ?)',
        (chat_id, message_id))
    else:
      self._db.execute(
        'update status_msg set message_id = ? where chat_id = ?',
        (message_id, chat_id))


def ExtractChatID(query: Any):
  if hasattr(query, 'chat'):
    return query.chat.id
  if hasattr(query, 'message'):
    return ExtractChatID(query.message)
  return 0


@filters.create
async def ChatLocked(_, client: Client, query: Any):
  return client.ustorage.is_locked(client.ExtractChatID(query))


async def _ChatLockedBetween(flt: Any, client: Client, query: Any) -> bool:
  level: int = client.ustorage.get_lock_level(client.ExtractChatID(query))
  return flt.left <= level and level <= flt.right


def ChatLockedBetween(left: int, right: int) -> Callable:
  return filters.create(_ChatLockedBetween, left=left, right=right)


def NoLock(method: Callable) -> Callable:
  async def new_method(*args, **kwargs) -> Any:
    try:
      await method(*args, **kwargs)

    except Exception as e:
      try:
        await args[0].report_error(
          args[1], e, traceback.format_exc(),
          method.__name__)

      except:
        print(traceback.format_exc())
        print('Unhandled exception', e)
  new_method.__name__ = '_ptctd_' + method.__name__
  return new_method

def UseLock(lock_level: int = 1) -> Callable:
  def decorator(method: Callable) -> Callable:
    async def new_method(*args, **kwargs) -> Any:
      is_locked: bool = False
      if 'locked' in kwargs:
        is_locked = kwargs['locked'] == True

      chat_id: int = args[0].ExtractChatID(args[1])
      if not is_locked:
        _id: int = args[0].ustorage.lock_chat(chat_id, lock_level)
        await asyncio.sleep(0.1)
        if _id != args[0].ustorage.get_lock_time(chat_id):
          return  # Another method is running

      try:
        await method(*args, **kwargs)

      except Exception as e:
        exc: str = traceback.format_exc()
        try:
          if not isinstance(args[0], Client):
            await args[0].nbot.report_error(
              args[1], e, exc,
              method.__name__)

          else:
            await args[0].report_error(
              args[1], e, exc,
              method.__name__)

        except:
          print(traceback.format_exc())
          print('Unhandled exception', e)

      if not is_locked:
        args[0].ustorage.unlock_chat(ExtractChatID(args[1]))
    new_method.__name__ = '_locked_' + method.__name__
    return new_method
  return decorator
