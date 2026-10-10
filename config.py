# -*- coding: utf-8 -*-
"""
config.py — конфигурация content-bot.

Читает настройки из .env (python-dotenv):
  BOT_TOKEN  — токен бота от @BotFather (обязателен);
  ADMIN_ID   — Telegram ID, куда уходят отчёты об оплатах;
  PROXY_URL  — базовый URL прокси Telegram API (необязателен),
               например Cloudflare Worker: https://worker.example.workers.dev
"""

import os

from dotenv import load_dotenv

load_dotenv()

# Токен бота от @BotFather
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Telegram ID администратора — получает уведомления об оплатах
ADMIN_ID = os.getenv("ADMIN_ID")

# Базовый URL прокси Telegram API. Пусто = прямое подключение
# к api.telegram.org
PROXY_URL = os.getenv("PROXY_URL", "").strip().rstrip("/")

# Валидация: без токена боту нечего запускать — падаем сразу с понятной ошибкой
if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN не найден! Скопируйте .env.example в .env "
        "и впишите токен от @BotFather: BOT_TOKEN=123456:ABC..."
    )

# ADMIN_ID не обязателен для старта, но без него отчёты об оплатах теряются
if not ADMIN_ID:
    print("[config] ВНИМАНИЕ: ADMIN_ID не задан — уведомления об оплатах отключены")
    ADMIN_ID = None
else:
    ADMIN_ID = int(ADMIN_ID)  # Telegram ждёт числовой ID

# PROXY_URL валидируем мягко: еслиscheme не http(s), отключаем прокси
if PROXY_URL and not PROXY_URL.startswith(("http://", "https://")):
    print("[config] ВНИМАНИЕ: PROXY_URL должен начинаться с http(s):// — прокси отключён")
    PROXY_URL = ""
