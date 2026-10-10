# -*- coding: utf-8 -*-
"""
payments.py — платёжные события Telegram Stars.

Два обязательных обработчика:
  1) pre_checkout_query  — Telegram ждёт ответ ok=True максимум 10 секунд,
     иначе платёж отклонится. Отвечаем мгновенно.
  2) successful_payment  — платёж прошёл: сохраняем заказ в SQLite,
     подтверждаем покупателю, отправляем отчёт админу.

Состав заказа читается ИЗ БД (pending_orders) по payload —
снимок сохраняется при выставлении счёта и переживает перезапуск бота.
Fallback: если снимок всё же не найден — заказ сохраняется
(сумма известна из successful_payment), состав помечается
как «состав утерян», админ получает отчёт и связывается с клиентом.
"""

import json
import logging

from aiogram import F, Router
from aiogram.types import Message, PreCheckoutQuery

from bot.utils.db import (
    delete_pending_order,
    get_pending_order,
    save_paid_order,
)
from config import ADMIN_ID

router = Router()

logger = logging.getLogger(__name__)


# 1. Pre-checkout: Telegram требует ответить в течение 10 секунд,
#    иначе платёж будет отклонён. Товары цифровые — всегда разрешаем.
@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery) -> None:
    await query.answer(ok=True)


# 2. Успешная оплата звёздами
@router.message(F.successful_payment)
async def on_payment(message: Message) -> None:
    sp = message.successful_payment
    payload = sp.invoice_payload
    total = sp.total_amount          # Сумма в звёздах (целое число)

    user = message.from_user
    user_name = user.full_name
    username = f"@{user.username}" if user.username else None

    # Состав заказа: из БД по payload (переживает перезапуск бота).
    # Если записи нет (например, счёт из старой версии) — сохраняем
    # заказ без состава и логируем для ручного разбора.
    pending = get_pending_order(payload)
    if pending is not None:
        items = json.loads(pending.items_json)
        items_json = pending.items_json
        items_summary = "; ".join(
            f"{it['name']} × {it['qty']}" if it["qty"] > 1 else it["name"]
            for it in items
        )
        delete_pending_order(payload)  # Снимок использован — чистим
    else:
        logging.warning("pending_orders: снимок не найден для payload=%s", payload[:50])
        items = []
        items_json = "{}"
        items_summary = f"{total} ⭐ (состав не сохранён)"

    # 1. Сохраняем оплаченный заказ в SQLite
    order_id = save_paid_order(
        user_id=user.id,
        user_name=user_name,
        username=username,
        total=total,
        payload=payload,
        items_json=items_json,
    )

    # 2. Подтверждение покупателю
    await message.answer("✅ <b>Оплата получена!</b>")

    # 3. Отчёт админу. try/except: Telegram запретит отправку,
    #    если админ ни разу не писал этому боту — заказ не теряем.
    if ADMIN_ID:
        uname = f" (@{user.username})" if user.username else ""
        try:
            await message.bot.send_message(
                ADMIN_ID,
                "💰 <b>Новый оплаченный заказ!</b>\n\n"
                f"От: {user_name}{uname}\n"
                f"Сумма: <b>{total} ⭐</b>\n"
                f"Состав: {items_summary}",
            )
        except Exception as e:  # noqa: BLE001
            print(f"[payments] Не удалось уведомить админа: {e}")
