# -*- coding: utf-8 -*-
"""
db.py — база данных content-bot (SQLite через SQLAlchemy 2.x).

Две таблицы:
  pending_orders — снимки корзин на момент выставления счёта Stars.
                   Записываются при send_invoice, читаются при
                   successful_payment, удаляются после использования.
                   Переживают перезапуск бота.
  orders         — одна строка на каждый successful_payment.
                   Состав заказа хранится строкой JSON (items_json).
"""

import os
from datetime import datetime, timedelta

from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

# --- Путь к хранилищу ---
# Локально: data/ (по умолчанию). На Amvera: PERSISTENCE_DIR=/data
# (постоянное хранилище монтируется в /data согласно amvera.yml).
BASE_DIR = os.getenv("PERSISTENCE_DIR", "data")
os.makedirs(BASE_DIR, exist_ok=True)   # Папка создаётся при старте, если её нет

DB_PATH = os.path.join(BASE_DIR, "shop.db")

engine = create_engine(
    f"sqlite:///{os.path.normpath(DB_PATH)}",
    connect_args={"check_same_thread": False},
)


class Base(DeclarativeBase):
    """Базовый класс всех ORM-моделей."""


class PendingOrder(Base):
    """
    Снимок корзины на момент выставления счёта в Stars.

    Живёт от «⭐ Оплатить» до successful_payment (после чего удаляется).
    Если пользователь не оплатил счёт — запись остаётся как история
    брошенных корзин (не мешает, объём копеечный).
    """

    __tablename__ = "pending_orders"

    payload: Mapped[str] = mapped_column(primary_key=True)  # invoice_payload
    user_id: Mapped[int]
    items_json: Mapped[str]                                 # Состав корзины (JSON)
    total: Mapped[int]                                      # Сумма в звёздах
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)


class Order(Base):
    """Оплаченный заказ (создаётся после successful_payment)."""

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int]                             # Telegram ID покупателя
    user_name: Mapped[str]                           # Имя (для отчёта админу)
    username: Mapped[str | None] = mapped_column(default=None)  # @username, если есть
    total: Mapped[int]                               # Сумма в звёздах (целое число)
    payload: Mapped[str]                             # invoice_payload из счёта
    items_json: Mapped[str]                          # Состав заказа (JSON) или пометка об утере
    status: Mapped[str] = mapped_column(default="paid")  # paid / fallen_back
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)


def init_db() -> None:
    """Создаёт таблицы, если их ещё нет. Вызывается один раз при старте бота."""
    Base.metadata.create_all(engine)


def save_pending_order(payload: str, user_id: int, items_json: str, total: int) -> None:
    """
    Сохраняет снимок корзины при выставлении счёта Stars.

    Вызывается из cart.py прямо перед send_invoice — чтобы после
    перезапуска бота состав заказа всё равно читался из БД.
    """
    with Session(engine) as session:
        session.add(
            PendingOrder(
                payload=payload,
                user_id=user_id,
                items_json=items_json,
                total=total,
            )
        )
        session.commit()


def get_pending_order(payload: str) -> PendingOrder | None:
    """Читает снимок корзины по payload (не удаляя его)."""
    with Session(engine) as session:
        row = session.get(PendingOrder, payload)
        if row is None:
            return None
        _ = row.items_json  # Подгружаем поле, пока сессия открыта
        return row


def delete_pending_order(payload: str) -> None:
    """Удаляет снимок корзины после успешной обработки платежа."""
    with Session(engine) as session:
        row = session.get(PendingOrder, payload)
        if row is not None:
            session.delete(row)
            session.commit()


def save_paid_order(
    user_id: int,
    user_name: str,
    username: str | None,
    total: int,
    payload: str,
    items_json: str,
) -> int:
    """
    Сохраняет оплаченный заказ. Возвращает номер заказа (id).

    items_json — JSON-строка с составом корзины либо
    пометка «состав утерян», если снимок не найден.
    """
    with Session(engine) as session:
        order = Order(
            user_id=user_id,
            user_name=user_name,
            username=username,
            total=total,
            payload=payload,
            items_json=items_json,
            status="paid",
        )
        session.add(order)
        session.commit()
        return order.id


def get_user_orders(user_id: int) -> list[Order]:
    """История оплаченных заказов пользователя (новые — первыми)."""
    with Session(engine) as session:
        result = session.execute(
            select(Order).where(Order.user_id == user_id).order_by(Order.id.desc())
        )
        return list(result.scalars().all())


def delete_old_pending_orders(hours: int = 24) -> int:
    """
    Удаляет снимки корзин старше N часов (брошенные неоплаченные счета).

    Вызывается при старте бота: неоплаченный счёт живёт максимум
    один сеанс — за 24 часа его точно оплатили или бросили.
    Возвращает число удалённых записей.
    """
    with Session(engine) as session:
        result = session.execute(
            delete(PendingOrder).where(
                PendingOrder.created_at < datetime.now() - timedelta(hours=hours)
            )
        )
        session.commit()
        return result.rowcount
