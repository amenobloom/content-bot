# -*- coding: utf-8 -*-
"""
cart.py — корзина и отправка счёта в Telegram Stars.

Корзина живёт В ПАМЯТИ процесса (CART: user_id -> позиции).
При «⭐ Оплатить» выставляется счёт (send_invoice, XTR), а снимок
корзины сохраняется в SQLite (таблица pending_orders) — поэтому
данные не теряются при перезапуске бота. По payload модуль
payments.py читает состав из БД при successful_payment.

ВАЖНО про Telegram Stars:
  • currency="XTR"
  • provider_token НЕ передаётся вообще (не пустая строка!)
  • prices — РОВНО ОДИН LabeledPrice с общей суммой заказа
"""

import json
import time

from aiogram import F, Router
from aiogram.types import CallbackQuery, LabeledPrice, Message

from bot.keyboards.main_menu import cart_kb, catalog_kb
from bot.utils.db import save_pending_order

router = Router()

# Корзины пользователей: user_id -> [{"id","name","price","qty"}, ...]
CART: dict[int, list[dict]] = {}


# ---------- Функции-помощники ----------

def add_item(user_id: int, product: dict) -> None:
    """Добавляет товар в корзину или увеличивает количество (+1)."""
    cart = CART.setdefault(user_id, [])
    for item in cart:
        if item["id"] == product["id"]:
            item["qty"] += 1
            return
    cart.append(
        {"id": product["id"], "name": product["name"], "price": product["price"], "qty": 1}
    )


def get_cart(user_id: int) -> list[dict]:
    """Позиции корзины пользователя (пустой список, если корзина пуста)."""
    return CART.get(user_id, [])


def clear_cart(user_id: int) -> None:
    """Очищает корзину пользователя."""
    CART.pop(user_id, None)


def cart_total(cart: list[dict]) -> int:
    """Сумма корзины в звёздах (цены целые — XTR дробных не поддерживает)."""
    return sum(item["price"] * item["qty"] for item in cart)


def render_cart(cart: list[dict]) -> str:
    """Текст корзины: позиции, количества, итог в ⭐."""
    if not cart:
        return "🧺 Корзина пуста.\n\nЗагляните в «🖼 Каталог» — есть красивые паки."
    lines = ["🧺 <b>Ваша корзина:</b>", ""]
    for item in cart:
        qty = f" × {item['qty']}" if item["qty"] > 1 else ""
        lines.append(f"• {item['name']}{qty} — {item['price']} ⭐")
    lines.append("")
    lines.append(f"<b>Итого: {cart_total(cart)} ⭐</b>")
    return "\n".join(lines)


# ---------- Обработчики ----------

# «🖼 Каталог»: всё меню одним сообщением, редактируется на месте
@router.message(F.text == "🖼 Каталог")
async def show_catalog(message: Message) -> None:
    from bot.handlers.catalog import PRODUCTS, catalog_text

    cart = get_cart(message.from_user.id)
    await message.answer(
        catalog_text(cart),
        reply_markup=catalog_kb(PRODUCTS, sum(i["qty"] for i in cart)),
    )


# «🧺 Корзина» с Reply-панели — новое сообщение с кнопками управления
@router.message(F.text == "🧺 Корзина")
async def cart_button(message: Message) -> None:
    cart = get_cart(message.from_user.id)
    await message.answer(render_cart(cart), reply_markup=cart_kb(sum(i["qty"] for i in cart)))


# «← В каталог»: корзина превращается обратно в каталог (ленивый импорт —
# catalog.py импортирует из этого модуля функции корзины)
@router.callback_query(F.data == "cart:back")
async def cb_cart_back(callback: CallbackQuery) -> None:
    from bot.handlers.catalog import PRODUCTS, catalog_text

    cart = get_cart(callback.from_user.id)
    await callback.message.edit_text(
        catalog_text(cart),
        reply_markup=catalog_kb(PRODUCTS, sum(i["qty"] for i in cart)),
    )
    await callback.answer()


# «🗑 Очистить»: очищаем и на месте показываем открытый каталог
@router.callback_query(F.data == "cart:clear")
async def cb_cart_clear(callback: CallbackQuery) -> None:
    from bot.handlers.catalog import PRODUCTS, catalog_text

    clear_cart(callback.from_user.id)
    await callback.message.edit_text(
        catalog_text([]),
        reply_markup=catalog_kb(PRODUCTS),
    )
    await callback.answer("Корзина очищена")


# «⭐ Оплатить»: выставляем счёт Telegram Stars
@router.callback_query(F.data == "cart:pay")
async def cb_cart_pay(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    cart = get_cart(user_id)

    if not cart:
        await callback.answer("Корзина пуста", show_alert=True)
        return

    # payload уникален для счёта: user_id + время выставления.
    # Лимит payload — 128 байт, наш укладывается с запасом.
    payload = f"order:{user_id}:{int(time.time())}"

    total = cart_total(cart)

    # Снимок корзины — в SQLite (переживает перезапуск бота)
    save_pending_order(
        payload=payload,
        user_id=user_id,
        items_json=json.dumps(cart, ensure_ascii=False),
        total=total,
    )

    # Краткое описание заказа для счёта (лимит 255 символов)
    description = ", ".join(
        f"{it['name']} × {it['qty']}" if it["qty"] > 1 else it["name"]
        for it in cart
    )[:255]

    # ВАЖНО для Telegram Stars:
    #   • currency="XTR"
    #   • provider_token НЕ передаём вообще (не "" — а просто без параметра)
    #   • prices — РОВНО ОДИН LabeledPrice с общей суммой заказа
    await callback.bot.send_invoice(
        chat_id=user_id,
        title="Заказ в магазине",           # до 32 символов
        description=description,             # до 255 символов
        payload=payload,
        currency="XTR",
        prices=[
            LabeledPrice(label="Оплата заказа", amount=total),
        ],
    )

    await callback.answer()
    await callback.message.answer("🧾 Счёт отправлен, оплатите звёздами ⭐")