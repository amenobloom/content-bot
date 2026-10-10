# -*- coding: utf-8 -*-
"""
retry.py — outer-middleware устойчивости к сетевым сбоям.

Обёртывает обработку каждого апдейта:
  • TelegramRetryAfter  — Telegram просит подождать (флуд-контроль):
    ждём e.retry_after секунд и повторяем (до 5 попыток);
  • TelegramNetworkError — сеть отвалилась: пауза 3 секунды,
    повтор (до 3 попыток).

Middleware — outer: перехватывает и исключения из самих обработчиков.
"""

import asyncio
import logging

from aiogram import BaseMiddleware
from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter

logger = logging.getLogger(__name__)

MAX_FLOOD_RETRIES = 5      # Повторов при RetryAfter
MAX_NETWORK_RETRIES = 3    # Повторов при сетевых сбоях
NETWORK_RETRY_DELAY = 3    # Секунды между сетевыми повторами


class RetryMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        # --- Флуд-контроль Telegram ---
        for attempt in range(MAX_FLOOD_RETRIES):
            try:
                return await handler(event, data)
            except TelegramRetryAfter as e:
                if attempt == MAX_FLOOD_RETRIES - 1:
                    logger.error("RetryAfter: попытки исчерпаны (%s с)", e.retry_after)
                    return  # Сдаёмся — апдейт теряется, но бот живёт
                logger.warning(
                    "Flood control: жду %s с (попытка %s/%s)",
                    e.retry_after, attempt + 1, MAX_FLOOD_RETRIES,
                )
                await asyncio.sleep(e.retry_after)

        # --- Сетевые сбои ---
        for attempt in range(MAX_NETWORK_RETRIES):
            try:
                return await handler(event, data)
            except TelegramNetworkError as e:
                if attempt == MAX_NETWORK_RETRIES - 1:
                    logger.error("NetworkError: попытки исчерпаны — %s", e)
                    return
                logger.warning(
                    "NetworkError: повтор через %s с (попытка %s/%s) — %s",
                    NETWORK_RETRY_DELAY, attempt + 1, MAX_NETWORK_RETRIES, e,
                )
                await asyncio.sleep(NETWORK_RETRY_DELAY)
