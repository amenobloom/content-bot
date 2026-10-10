# -*- coding: utf-8 -*-
"""
handlers — сборка всех обработчиков в один общий роутер.

Порядок включения важен для payments: pre_checkout_query и
successful_payment обрабатываются раньше/независимо от текстовых.
"""

from aiogram import Router

from .cart import router as cart_router
from .catalog import router as catalog_router
from .payments import router as payments_router
from .start import router as start_router

router = Router()
router.include_routers(start_router, catalog_router, cart_router, payments_router)
