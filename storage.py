from typing import Self, Optional, Tuple, Any, Callable, List
from pyrogram import filters, Client
import sqlite3
import time


class TemporaryStorage:
  def __init__(self) -> Self:
    self._db: sqlite3.Connection = sqlite3.connect(
      ':memory:', check_same_thread=False)
    self._init_db()

  def _init_db(self) -> None:
    self._db.execute(
      'create table lock_data (chat_id integer primary key, time timestamp, lock_level integer)')
    self._db.execute(
      'create table playlist (chat_id integer, song_url varchar, time timestamp)')

  def _destroy_db(self) -> None:
    self._db.execute('drop lock_data')
    self._db.execute('drop playlist')


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


  def fetch_playlist(self, chat_id: int, limit: int = 10) -> List[Tuple[int, int]]:
    cursor: sqlite3.Cursor = self._db.cursor()
    cursor.execute(
      'select song_url, time from playlist where chat_id = ? limit ?',
      (chat_id, limit))
    ret: Optional[List[Tuple[int, int]]] = cursor.fetchall()
    if not ret:
      return []
    return ret

  def playlist_size(self, chat_id: int) -> int:
    cursor: sqlite3.Cursor = self._db.cursor()
    cursor.execute(
      'select count(*) from playlist where chat_id = ?', (chat_id,))
    return cursor.fetchone()[0]

  def playlist_enqueue(self, chat_id: int, url: str) -> int:
    self._db.execute(
      'insert into playlist values (?, ?, ?)',
      (chat_id, url, time.time()))
    return self.playlist_size(chat_id)

  def playlist_dequeue(self, chat_id: int) -> Optional[str]:
    cursor: sqlite3.Cursor = self._db.cursor()
    cursor.execute(
      'select song_url, time from playlist where chat_id = ? limit 1', (chat_id,))
    ret: Optional[Tuple[int, int]] = cursor.fetchone()
    if not ret:
      return None
    self._db.execute(
      'delete from playlist where chat_id = ? and time = ?',
      (chat_id, ret[1]))
    return ret[0]

  def clean_playlist(self, chat_id: int) -> None:
    self._db.execute(
      'delete from playlist where chat_id = ?', (chat_id,))


def ExtractChatID(query: Any):
  if hasattr(query, 'chat'):
    return query.chat.id
  if hasattr(query, 'message'):
    return ExtractChatID(query.message)
  return 0


@filters.create
async def ChatLocked(_, client: Client, query: Any):
  return client._ustorage.is_locked(client.ExtractChatID(query))


async def _ChatLockedBetween(flt: Any, client: Client, query: Any) -> bool:
  level: int = client._ustorage.get_lock_level(client.ExtractChatID(query))
  return flt.left <= level and level <= flt.right


def ChatLockedBetween(left: int, right: int) -> Callable:
  return filters.create(_ChatLockedBetween, left=left, right=right)


def UseLock(lock_level: int = 1) -> Callable:
  def decorator(method: Callable) -> Callable:
    async def new_method(*args, **kwargs) -> Any:
      chat_id: int = args[0].ExtractChatID(args[1])
      _id: int = args[0]._ustorage.lock_chat(chat_id, lock_level)
      time.sleep(0.1)
      if _id != args[0]._ustorage.get_lock_time(chat_id):
        return  # Another method is running
      await method(*args, **kwargs)
      args[0]._ustorage.unlock_chat(ExtractChatID(args[1]))
    new_method.__name__ = '_locked_' + method.__name__
    return new_method
  return decorator
