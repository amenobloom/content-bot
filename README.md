# TEPLO Content Bot

Telegram-бот-магазин цифрового контента (обои, пресеты, арты, стикеры)
на **aiogram 3.x** с оплатой **Telegram Stars (XTR)**.

## Структура проекта

```
content-bot/
├── main.py              # точка входа (+ прокси-сессия, если задан PROXY_URL)
├── config.py            # BOT_TOKEN, ADMIN_ID, PROXY_URL из .env
├── requirements.txt     # aiogram 3.x, python-dotenv, SQLAlchemy
├── .env.example         # шаблон настроек (скопировать в .env)
├── bot/
│   ├── handlers/        # start, catalog, cart, payments (Stars)
│   ├── keyboards/       # Reply-меню и inline-клавиатуры
│   └── utils/db.py      # SQLite: таблица orders
└── data/
    ├── products.json    # каталог товаров (цены в ⭐, целые)
    └── shop.db          # создаётся автоматически при первом запуске
```

## Запуск

### 1. Зависимости

```bash
cd content-bot
python -m venv venv
venv\Scripts\activate          # Windows (Linux/Mac: source venv/bin/activate)
pip install -r requirements.txt
```

### 2. `.env`

```bash
cp .env.example .env
```

| Переменная | Откуда взять |
|---|---|
| `BOT_TOKEN` | Новый бот у [@BotFather](https://t.me/BotFather): `/newbot` |
| `ADMIN_ID` | Ваш Telegram ID ([@userinfobot](https://t.me/userinfobot)) |
| `PROXY_URL` | Адрес вашего Cloudflare Worker (или оставьте как есть) |

### 3. Запуск

```bash
python main.py
```

В консоли появится `Start polling` — откройте бота и нажмите **Start**.

## Оплата Telegram Stars (XTR)

- **provider_token обязателен пустой строкой** — так Telegram понимает,
  что платёж в звёздах.
- Цены в `products.json` — **целые числа** (дробных звёзд не бывает).
- При «⭐ Оплатить» бот присылает счёт; пользователь платит звёздами
  прямо в Telegram.
- Обработчики `pre_checkout_query` (ответ в течение 10 секунд)
  и `successful_payment` (сохранение в SQLite + отчёт админу) —
  в `bot/handlers/payments.py`.

### Тестирование

1. Пополните звёзды: Telegram → Настройки → Мои звёзды (или через Fragment).
2. Откройте бота → «🛒 Каталог» → добавьте позиции → «🛒 Открыть корзину»
   → «⭐ Оплатить» → оплатите счёт.
3. Проверьте: сообщение «✅ Оплата получена», запись в `data/shop.db`
   (таблица orders), отчёт у `ADMIN_ID`.

### Возврат звёзд покупателю

`/refund <user_id> <telegram_payment_charge_id>` — ID платежа приходит
в `successful_payment.telegram_payment_charge_id` (логируется в консоль).

## Товары

Редактируйте `data/products.json` (нужен перезапуск бота). Цены — целые.

## Безопасность

- `.env` с токеном в git **не попадает** (см. `.gitignore`)
- Если токен «утёк» — отзовите его у @BotFather (`/revoke`)

## Эксплуатация (VPS)

**Мониторинг:** команда `/ping` — только для ADMIN_ID,
отвечает «🟢 Бот жив. Время работы: …».

**Автозапуск на Linux (systemd):** готовый юнит в `deploy/content-bot.service`
(Restart=always, RestartSec=10, логи в journald). Установка описана
в комментариях юнита: скопировать в `/etc/systemd/system/`,
`systemctl enable --now content-bot`, логи — `journalctl -u content-bot -f`.

**Устойчивость, встроенная в код:**
- FSM и снимки корзин — в SQLite, переживают перезапуск;
- `TelegramRetryAfter` / `TelegramNetworkError` — автоматические повторы;
- таймаут сессии 60 с, пул соединений 100;
- глобальный обработчик ошибок (лог + уведомление админу);
- graceful shutdown по SIGINT/SIGTERM.
