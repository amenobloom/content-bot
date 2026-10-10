# -*- coding: utf-8 -*-
"""
catalog.py — «🖼 Каталог» и добавление товаров в корзину.

Каталог отправляется ОДНИМ сообщением: весь список в тексте
и inline-клавиатура под ним (кнопка = товар). После нажатия
на позицию меню НЕ закрывается — то же сообщение редактируется
на месте: обновляется счётчик корзины в тексте и на кнопке.

Каталог ЧИТАЕТСЯ ИЗ ФАЙЛА при каждом запросе: правки цен/состава
в data/products.json подхватываются без перезапуска бота.
Путь берётся из PERSISTENCE_DIR? Нет: products.json — это КОНТЕНТ
(должен быть в репозитории), поэтому путь фиксированный:
bot/handlers/../../data/products.json.
"""

import json
import os

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from bot.handlers.cart import add_item, get_cart
from bot.keyboards.main_menu import catalog_kb

router = Router()

# Путь к каталогу: от bot/handlers вверх на два уровня — в data/
_PRODUCTS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "products.json"
)


def load_products() -> list[dict]:
    """Читает каталог из JSON заново при каждом вызове — правки без перезапуска."""
    with open(_PRODUCTS_PATH, encoding="utf-8") as f:
        return json.load(f)


def catalog_text(products: list[dict], cart: list[dict]) -> str:
    """
    Текст каталога одним сообщением + строка состояния корзины.
    cart передаётся, чтобы строка «В корзине…» всегда была актуальной.
    """
    lines = ["🖼 <b>Каталог цифрового контента</b>", ""]
    for i, p in enumerate(products, 1):
        lines.append(f"{i}. <b>{p['name']}</b> — {p['price']} ⭐")
        # description опционален: товары без описания выводятся без пустой строки
        desc = p.get("description", "").strip()
        if desc:
            lines.append(f"      {desc}")
    lines.append("")
    if cart:
        lines.append(
            f"🧺 В корзине: {sum(i['qty'] for i in cart)} шт. "
            f"на {sum(i['price'] * i['qty'] for i in cart)} ⭐\n"
            "Корзина — кнопка «🧺 Корзина» в меню."
        )
    else:
        lines.append("👇 Нажмите на позицию ниже, чтобы добавить её в корзину")
    return "\n".join(lines)


@router.message(F.text == "🖼 Каталог")
async def show_catalog(message: Message) -> None:
    """Каталог одним сообщением: весь список + inline-кнопки добавления."""
    products = load_products()
    cart = get_cart(message.from_user.id)
    qty = sum(i["qty"] for i in cart)
    await message.answer(
        catalog_text(products, cart),
        reply_markup=catalog_kb(products, qty),
    )


@router.callback_query(F.data.startswith("add:"))
async def cb_add_to_cart(callback: CallbackQuery) -> None:
    """
    Добавление товара: callback_data имеет вид add:<id>.
    Меню НЕ закрывается — то же сообщение перерисовывается
    с обновлённым счётчиком корзины.
    """
    try:
        product_id = int(callback.data.split(":", 1)[1])
    except (IndexError, ValueError):
        await callback.answer("Не удалось распознать товар", show_alert=True)
        return

    products = load_products()
    product = next((p for p in products if p["id"] == product_id), None)
    if product is None:
        # Товар могли убрать из каталога, а старые кнопки остались в чате
        await callback.answer("Товар больше недоступен", show_alert=True)
        return

    add_item(callback.from_user.id, product)

    # Меню остаётся открытым: правим то же сообщение
    cart = get_cart(callback.from_user.id)
    await callback.message.edit_text(
        catalog_text(products, cart),
        reply_markup=catalog_kb(
            products,
            sum(i["qty"] for i in cart),
        ),
    )
    await callback.answer(f"✅ {product['name']} в корзине")
