# -*- coding: utf-8 -*-
"""
start.py — первый контакт: /start с приветствием и Reply-меню,
кнопка «ℹ️ Помощь» с кнопкой «✉️ Написать продавцу».
"""

from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.keyboards.main_menu import main_menu
from config import ADMIN_ID

router = Router()

# Момент старта процесса — для расчёта uptime в /ping
STARTED_AT = datetime.now()

# Telegram продавца — прямая ссылка (замените, если продавец другой)
SELLER_TG = "https://t.me/linusinn"

HELP_TEXT = (
    "ℹ️ <b>Как пользоваться ботом</b>\n\n"
    "🖼 <b>Каталог</b> — всё меню одним сообщением; нажмите на позицию, "
    "чтобы добавить её в корзину (меню не закроется).\n"
    "🧺 <b>Корзина</b> — кнопка на панели ниже: состав, сумма в ⭐ "
    "и кнопка «⭐ Оплатить».\n"
    "⭐ <b>Оплата</b> — счёт приходит в чат, платите звёздами прямо "
    "в Telegram. После оплаты заказ подтверждается автоматически.\n\n"
    "Остались вопросы — напишите продавцу 👇"
)


# «✉️ Написать продавцу» — URL-кнопка: открывает профиль продавца
# прямо в Telegram-приложении
SELLER_KB = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="✉️ Написать продавцу", url=SELLER_TG)]]
)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """/start: приветствие по имени + главное Reply-меню."""
    name = message.from_user.first_name
    await message.answer(
        f"Привет, <b>{name}</b>! 👋\n\n"
        "Это магазин цифрового контента: обои, пресеты, арты и стикеры.\n"
        "Оплата — звёздами Telegram ⭐, доставка мгновенно.\n\n"
        "Выбирайте раздел на клавиатуре ниже 👇",
        reply_markup=main_menu(),
    )


@router.message(F.text == "ℹ️ Помощь")
async def help_button(message: Message) -> None:
    """Кнопка «ℹ️ Помощь»: текст справки + кнопка «✉️ Написать продавцу»."""
    await message.answer(HELP_TEXT, reply_markup=SELLER_KB)


# ---------- Мониторинг: /ping для админа ----------

@router.message(Command("ping"))
async def cmd_ping(message: Message) -> None:
    """
    /ping — только для админа: жив ли бот и сколько работает.
    Для остальных — молчание (команда не существует).
    """
    if not ADMIN_ID or message.from_user.id != ADMIN_ID:
        return  # Молча игнорируем чужие /ping

    uptime = datetime.now() - STARTED_AT
    total = int(uptime.total_seconds())
    hours, rest = divmod(total, 3600)
    minutes, seconds = divmod(rest, 60)

    parts = []
    if hours:
        parts.append(f"{hours} ч")
    if minutes:
        parts.append(f"{minutes} мин")
    parts.append(f"{seconds} с")

    await message.answer(f"🟢 Бот жив. Время работы: {' '.join(parts)}")
