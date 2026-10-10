# -*- coding: utf-8 -*-
"""
main.py — точка входа content-bot (цифровой контент за Telegram Stars).

Порядок запуска:
  1) логирование;
  2) init_db() — таблица orders в SQLite;
  3) сессия: прямая или через прокси (PROXY_URL из .env, Cloudflare Worker);
  4) Bot + Dispatcher с MemoryStorage;
  5) polling.
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.types import ErrorEvent
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.enums import ParseMode

from bot.handlers import router as root_router
from bot.middlewares.retry import RetryMiddleware
from bot.utils.db import delete_old_pending_orders, init_db
from bot.utils.sqlite_storage import SQLiteStorage
from config import BOT_TOKEN, ADMIN_ID, PROXY_URL

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logging.getLogger("aiogram.event").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def build_session() -> AiohttpSession:
    """
    Сессия Telegram API: прямая или через прокси-воркер (Cloudflare).

    Таймаут 60 с и лимит соединений 100 — устойчивость при нагрузке:
    долгие запросы не рвутся, пул не душит параллельные апдейты.
    """
    # Явные таймаут и пул соединений (BaseSession: timeout, AiohttpSession: limit)
    kwargs: dict = {"timeout": 60, "limit": 100}

    if PROXY_URL:
        # Все запросы пойдут на PROXY_URL/bot<token>/method
        api = TelegramAPIServer.from_base(PROXY_URL)
        logging.info("Telegram API через прокси: %s", PROXY_URL)
        return AiohttpSession(api=api, **kwargs)
    logging.info("Telegram API напрямую (прокси не задан)")
    return AiohttpSession(**kwargs)


async def main() -> None:
    init_db()

    # Очистка брошенных снимков корзин (счета не оплатили за 24 часа)
    removed = delete_old_pending_orders(hours=24)
    if removed:
        logging.info("Удалено устаревших pending_orders: %s", removed)

    bot = Bot(
        token=BOT_TOKEN,
        session=build_session(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # FSM-хранилище в SQLite: файл fsm.db в PERSISTENCE_DIR (/data на Amvera),
    # состояния и данные диалогов переживают перезапуск бота
    dp = Dispatcher(storage=SQLiteStorage())

    # Устойчивость к сетевым сбоям: RetryAfter и NetworkError
    # (outer-middleware — оборачивает всю обработку апдейта)
    dp.update.outer_middleware(RetryMiddleware())

    dp.include_router(root_router)

    # Глобальный обработчик ошибок: traceback в лог, админу — краткое
    # уведомление, пользователю — нейтральное сообщение
    @dp.errors()
    async def on_error(event: ErrorEvent, bot: Bot) -> bool:
        logger.exception(
            "Необработанная ошибка при обработке апдейта: %s", event.exception
        )
        if ADMIN_ID:
            err_type = type(event.exception).__name__
            err_msg = str(event.exception)[:200]
            try:
                await bot.send_message(
                    ADMIN_ID,
                    f"⚠️ <b>Ошибка в боте: {err_type}</b>\n{err_msg}",
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("Не удалось уведомить админа об ошибке: %s", e)

        update = event.update
        try:
            if update.message:
                await update.message.answer("⚠️ Произошла ошибка, попробуйте позже.")
            elif update.callback_query:
                await update.callback_query.answer(
                    "⚠️ Произошла ошибка, попробуйте позже.", show_alert=True
                )
        except Exception:  # noqa: BLE001
            pass  # Ответить не удалось — лог уже есть
        return True  # Ошибка обработана

    # Сбрасываем недоставленные старые обновления
    await bot.delete_webhook(drop_pending_updates=True)

    # Graceful shutdown: aiogram сам ловит SIGINT/SIGTERM
    # (loop.add_signal_handler внутри start_polling), дожидается
    # обработки апдейтов и закрывает сессию (close_bot_session=True).
    # Здесь только финальное сообщение о корректной остановке.
    try:
        await dp.start_polling(bot)
        logging.info("Бот остановлен корректно")
    except KeyboardInterrupt:
        logging.info("Бот остановлен корректно (Ctrl+C)")


if __name__ == "__main__":
    asyncio.run(main())
