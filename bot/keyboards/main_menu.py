# -*- coding: utf-8 -*-
"""
main_menu.py — клавиатуры content-bot.

Reply-меню: 🖼 Каталог | 🧺 Корзина | ℹ️ Помощь.
Inline-каталог: «➕ Товар · N ⭐» на каждую позицию.
Inline-корзина: «⭐ Оплатить» | «🗑 Очистить» / «← В каталог».

callback_data договорённости:
  add:<id>   — добавить товар в корзину
  cart:back  — вернуться в каталог
  cart:pay   — отправить счёт (Telegram Stars)
"""

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)


def main_menu() -> ReplyKeyboardMarkup:
    """Главное Reply-меню: корзина вынесена на панель."""
    keyboard = [
        [KeyboardButton(text="🖼 Каталог")],
        [KeyboardButton(text="🧺 Корзина")],
        [KeyboardButton(text="ℹ️ Помощь")],
    ]
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,      # Компактные кнопки
        input_field_placeholder="Выберите раздел…",
    )


def catalog_kb(
    products: list[dict],
    cart_qty: int = 0,
) -> InlineKeyboardMarkup:
    """
    Клавиатура каталога одним сообщением:
    кнопка на каждый товар («➕ Название · N ⭐» → add:<id>).
    """
    rows = [
        [
            InlineKeyboardButton(
                text=f"➕ {p['name']} · {p['price']} ⭐",
                callback_data=f"add:{p['id']}",
            )
        ]
        for p in products
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cart_kb(cart_qty: int = 0) -> InlineKeyboardMarkup:
    """Клавиатура корзины: оплатить, очистить, вернуться в каталог."""
    label = "⭐ Оплатить"
    if cart_qty:
        label += f" ({cart_qty} шт.)"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label, callback_data="cart:pay")],
            [
                InlineKeyboardButton(text="🗑 Очистить", callback_data="cart:clear"),
                InlineKeyboardButton(text="← В каталог", callback_data="cart:back"),
            ],
        ]
    )
