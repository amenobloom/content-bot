# -*- coding: utf-8 -*-
"""
sqlite_storage.py — FSM-хранилище aiogram 3 в SQLite (data/fsm.db).

Своя реализация BaseStorage вместо стороннего пакета: полный контроль
над схемой БД и форматом данных, без лишних зависимостей.
Состояния и данные переживают перезапуск бота.

Потокобезопасность: asyncio.to_thread выполняет каждый вызов в случайном
потоке из пула, а SQLite по умолчанию запрещает использовать соединение
в чужом потоке. Поэтому соединение открывается и закрывается на КАЖДЫЙ
вызов (никакого кэша в self._conn). Для частоты обращений FSM-хранилища
затраты на открытие копеечные, зато никакой гонки по потокам.

Путь по умолчанию — data/fsm.db; на Amvera main.py передаёт
fsm.db внутри PERSISTENCE_DIR (/data), согласно amvera.yml.
"""

import asyncio
import json
import os
import sqlite3
from typing import Any

from aiogram.fsm.storage.base import BaseStorage, StorageKey

# Папка хранилища: та же, что и у БД заказов (PERSISTENCE_DIR из .env,
# по умолчанию data/). Папка создаётся при импорте модуля.
BASE_DIR = os.getenv("PERSISTENCE_DIR", "data")
os.makedirs(BASE_DIR, exist_ok=True)

# Схема таблицы: одна строка на пару (чат, пользователь, контекст)
_SCHEMA = """
CREATE TABLE IF NOT EXISTS fsm_storage (
    bot_id    INTEGER NOT NULL,
    chat_id   INTEGER NOT NULL,
    user_id   INTEGER NOT NULL,
    context   TEXT    NOT NULL DEFAULT '',
    state     TEXT,
    data      TEXT    NOT NULL DEFAULT '{}',
    PRIMARY KEY (bot_id, chat_id, user_id, context)
)
"""


class SQLiteStorage(BaseStorage):
    """FSM-хранилище в SQLite-файле (по умолчанию fsm.db в PERSISTENCE_DIR)."""

    def __init__(self, db_path: str | None = None):
        # None → берём путь из PERSISTENCE_DIR (совпадает с db.py)
        self.db_path = db_path or os.path.join(BASE_DIR, "fsm.db")

    # ---------- Синхронная работа с sqlite3 (выполняется в to_thread) ----------

    def _connect(self) -> sqlite3.Connection:
        """
        Открывает НОВОЕ соединение (без кэша) и создаёт таблицу, если её нет.

        Соединение живёт только в текущем потоке: вызывающий код обязан
        закрыть его в finally (см. каждый метод ниже).
        """
        directory = os.path.dirname(self.db_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute(_SCHEMA)
        return conn

    @staticmethod
    def _key_tuple(key: StorageKey) -> tuple:
        # destination (контекст FSM) включаем в ключ: разные машины состояний
        # для одного пользователя не должны мешать друг другу
        ctx = key.destiny or ""
        return (key.bot_id, key.chat_id, key.user_id, ctx)

    # ---------- Реализация BaseStorage (aiogram 3) ----------

    async def set_state(self, key: StorageKey, state: str | None = None) -> None:
        def _do() -> None:
            k = self._key_tuple(key)
            conn = self._connect()
            try:
                with conn:
                    conn.execute(
                        "INSERT INTO fsm_storage (bot_id, chat_id, user_id, context, state) "
                        "VALUES (?, ?, ?, ?, ?) "
                        "ON CONFLICT(bot_id, chat_id, user_id, context) "
                        "DO UPDATE SET state = excluded.state",
                        (*k[:3], k[3], state),
                    )
            finally:
                conn.close()

        await asyncio.to_thread(_do)

    async def get_state(self, key: StorageKey) -> str | None:
        def _do() -> str | None:
            k = self._key_tuple(key)
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT state FROM fsm_storage "
                    "WHERE bot_id = ? AND chat_id = ? AND user_id = ? AND context = ?",
                    k,
                ).fetchone()
                return row[0] if row else None
            finally:
                conn.close()

        return await asyncio.to_thread(_do)

    async def set_data(self, key: StorageKey, data: dict[str, Any]) -> None:
        payload = json.dumps(data, ensure_ascii=False)

        def _do() -> None:
            k = self._key_tuple(key)
            conn = self._connect()
            try:
                with conn:
                    conn.execute(
                        "INSERT INTO fsm_storage (bot_id, chat_id, user_id, context, data) "
                        "VALUES (?, ?, ?, ?, ?) "
                        "ON CONFLICT(bot_id, chat_id, user_id, context) "
                        "DO UPDATE SET data = excluded.data",
                        (*k[:3], k[3], payload),
                    )
            finally:
                conn.close()

        await asyncio.to_thread(_do)

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        def _do() -> dict[str, Any]:
            k = self._key_tuple(key)
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT data FROM fsm_storage "
                    "WHERE bot_id = ? AND chat_id = ? AND user_id = ? AND context = ?",
                    k,
                ).fetchone()
                return json.loads(row[0]) if row else {}
            finally:
                conn.close()

        return await asyncio.to_thread(_do)

    async def update_data(
        self, key: StorageKey, data: dict[str, Any] | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        """Сливает переданные ключи с уже сохранёнными данными."""
        merged = await self.get_data(key)
        if data:
            merged.update(data)
        merged.update(kwargs)
        await self.set_data(key, merged)
        return merged

    async def reset_state(self, key: StorageKey, with_data: bool = True) -> None:
        """Сбрасывает состояние (и данные, если with_data=True)."""
        def _do_all() -> None:
            k = self._key_tuple(key)
            conn = self._connect()
            try:
                with conn:
                    conn.execute(
                        "DELETE FROM fsm_storage "
                        "WHERE bot_id = ? AND chat_id = ? AND user_id = ? AND context = ?",
                        k,
                    )
            finally:
                conn.close()

        def _do_state_only() -> None:
            k = self._key_tuple(key)
            conn = self._connect()
            try:
                with conn:
                    conn.execute(
                        "UPDATE fsm_storage SET state = NULL "
                        "WHERE bot_id = ? AND chat_id = ? AND user_id = ? AND context = ?",
                        k[:3] + (k[3],),
                    )
            finally:
                conn.close()

        await asyncio.to_thread(_do_all if with_data else _do_state_only)

    async def close(self) -> None:
        """Соединения не кэшируются — закрывать нечего."""
