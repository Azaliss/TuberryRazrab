# Архитектура Tuberry

Публичный сервис доступен на https://tuberry.ru. Ниже описаны все сервисы, их взаимодействие и ключевые технические решения.

## Композиция сервисов
```
+------------+        +-------------------+        +-------------------+
|  Telegram  | <----> |  masterbot (Py)   | -----> |  FastAPI backend  |
+------------+        +-------------------+        +-------------------+
       ^                          |                           |
       |                          v                           v
       |                   Redis task queue            PostgreSQL / Redis
       |                          |                           |
       |                          v                           |
       |                   worker (Py) <----------------------+------+
       |                          |                                  |
       v                          v                                  |
+------------+        +-------------------+        +-------------------+
|   Browser  | <----> |  Next.js frontend | <----> |   Caddy proxy     |
+------------+        +-------------------+        +-------------------+
       |
       v
+-----------------+
|  Avito REST API |
+-----------------+
```

### Состав
- **frontend** (`frontend/`) — Next.js 14 (App Router). Использует JWT из `localStorage`, SSR-часть ходит к API по `NEXT_INTERNAL_API_URL`.
  - Структура `app/(dashboard)/client/*`: общий `ClientShell` строит боковую навигацию на `@reui/accordion-menu`, добавляет CTA-блоки и logout.
  - Разделы кабинета (`/client`, `/client/settings`, `/client/analytics`, `/client/reports`, `/client/automations`, `/client/integrations`, `/client/billing`, `/client/support`) оформлены через reui-компоненты (таблицы, алерты, карточки) и служат заглушками для будущих возможностей.
  - Прокси-роут `app/api/[...path]/route.ts` прокидывает любой REST-запрос на FastAPI, благодаря чему фронт и API живут на одном origin и не зависят от доступности внешнего прокси.
- **backend** (`backend/app/`) — FastAPI + SQLModel. Экспонирует REST, Telegram/Avito вебхуки, фоновые сценарии и инициализацию БД.
- **worker** (`backend/app/worker.py`) — асинхронный обработчик очереди (`tuberry:tasks` в Redis). Сейчас обслуживает задачи `avito.send_message`.
- **masterbot** (`backend/app/workers/master_bot.py`) — Telegram-бот на aiogram, слушает `/start` через long polling и выдаёт `link_token`.
- **postgres** — основная БД (данные клиентов, боты, Avito-аккаунты, диалоги, сообщения).
- **redis** — хранит задания очереди и кэши AvitoService.
- **proxy** (`deploy/Caddyfile`) — Caddy 2, выполняет TLS-терминацию и маршрутизацию `/api/*` → backend, остального трафика → frontend.
- **Avito polling** — внешний процесс (см. `samples/poller.py` и пример скрипта в документации), который периодически обращается к Avito API и доставляет сообщения в backend.

## Backend: структура модулей
- `app/main.py` — точка входа FastAPI: подключает роутеры (`auth`, `clients`, `bots`, `dialogs`, `avito`, `admin`, `webhooks`), на старте вызывает `init_db()` (создание таблиц SQLModel).
- `app/routes/*` — HTTP-эндпоинты. Ключевые:
  - `auth` — Telegram Login, админская авторизация, обмен `link_token`.
  - `bots` — CRUD, автогенерация `webhook_secret`, установка вебхуков Telegram.
  - `avito` — управление учётками Avito (client_id/client_secret, связь с ботом).
  - `webhooks` — входящие запросы из Telegram (`/telegram/{bot_id}/{secret}`) и из Avito (`/avito`).
  - `dialogs` — получение истории диалогов, ручные действия.
  - `admin` — агрегированные метрики и техническая информация.
- `app/services/*` — доменная логика:
  - `AuthService` проверяет подпись Telegram Login, решает какие роли выдавать.
- `DialogService` синхронизирует сообщения между площадками, создаёт Telegram topics, пишет историю в БД, конвертирует вложения (текст, изображения, голосовые) из Avito в Telegram и обратно (из Telegram в Avito — текст и изображения) и управляет автоответчиком (планирование задач, задержка ~75 с, ограничение «один раз за интервал»).
  - `TelegramService` — thin-клиент к Bot API (sendMessage, createForumTopic, setWebhook и т.д.).
  - `AvitoService` — полностью рабочий клиент к Avito Messenger API: получает access_token по client_credentials, кэширует `user_id`, отправляет сообщения (`/messenger/v1/.../messages`) и помечает их прочитанными (`/read`).
  - `TaskQueue` — обёртка над Redis (`rpush`/`blpop`) для очереди задач.
- `app/repositories/*` — доступ к БД через SQLModel (боты, диалоги, сообщения, Avito-аккаунты, пользователи).
- `app/models/*` — схемы SQLModel (включая `Bot.webhook_secret`, `Dialog.telegram_topic_id`, `Message.direction`/`status`).
- `app/scripts/seed.py` — создание администратора, демо-клиента и владельца.

## Frontend
- `app/login/page.tsx` — вход через Telegram. После удачи сохраняет JWT в `localStorage` и редиректит в профиль.
- `app/(dashboard)/client/*` — интерфейс клиента: подключение ботов, Avito-аккаунтов, список диалогов.
- `app/(dashboard)/admin/*` — административная панель (метрики, список сущностей).
- `app/lib/api.ts` — универсальный fetch-хелпер (автоматически подставляет базовый URL и JWT).
- UI стилизован Tailwind-классами (через глобальные стили) и использует Server Components Next.js.

## Потоки данных

### Telegram Login
1. Пользователь нажимает кнопку входа.
2. JS-SDK Telegram возвращает подпись и пользовательские данные.
3. Фронтенд вызывает `POST /api/auth/telegram`.
4. `AuthService` пересчитывает HMAC (`sha256(MASTER_BOT_TOKEN)`), ищет пользователя по `telegram_user_id`.
5. В ответ приходит JWT (`expires` = `JWT_EXPIRES` секунд). Фронтенд сохраняет в `localStorage` и использует во всех запросах.

### Онбординг через мастер-бота
1. Клиент пишет `/start` боту `@vishenka_play_bot`.
2. Бот запрашивает `/api/auth/master/link`, получает одноразовый `link_token` и формирует ссылку `https://tuberry.ru/login?token=<...>`.
3. Пользователь открывает ссылку, фронтенд отправляет `POST /api/auth/master/exchange` с email/именем.
4. Backend создаёт пользователя с ролью `owner` и связывает `telegram_user_id`, выдаёт JWT.

### Входящие сообщения Avito → Telegram
1. Внешний процесс (poller) обращается к Avito API (`/messenger/v2/accounts/{user_id}/chats?unread_only=true`).
2. Для каждой непрочитанной записи вызывается `DialogService.handle_avito_message(...)`:
   - ищем Avito-аккаунт (`avito_accounts`), проверяем связь с ботом;
   - при первом сообщении создаём `Dialog`, по необходимости создаём новый Telegram topic и пин с данными объявления;
   - разбираем содержимое сообщения: текст, изображения, голосовые сообщения; отправляем их в Telegram (`sendMessage`/`sendPhoto`/`sendVoice` с `message_thread_id`);
    - фиксируем событие в таблице `messages` (direction=`avito`) с метаданными вложений;
    - если у клиента включён автоответ, планируем отложенную задачу (по умолчанию ~75 с) и сохраняем отметку, чтобы отвечать один раз за активный интервал.
3. После успешной доставки poller вызывает `POST /messenger/v1/.../read`, чтобы убрать чат из непрочитанных.
4. Вся логика Avito/Telegram сосредоточена в `DialogService`, благодаря чему poller может быть реализован как скрипт (`samples/poller.py`) или фоновой задачей.

### Исходящие сообщения Telegram → Avito
1. Клиент отвечает в Telegram-топике. Вебхук `POST /api/webhooks/telegram/{bot_id}/{secret}` принимает апдейт, валидирует `webhook_secret` и вызывает `DialogService.handle_telegram_message(...)`.
2. Сервис находит `Dialog` по `message_thread_id`, сохраняет сообщение и вложения в `messages` (direction=`telegram`) и ставит задачи в Redis `avito.send_message` (отдельно для текста и изображений).
3. Worker извлекает задачу: для текста вызывает `AvitoService.send_message(...)`, для изображений скачивает файл из Telegram, загружает в `/messenger/v1/accounts/{user_id}/uploadImages` и отправляет `POST /messages/image`.
4. После успешной отправки в логи пишется результат, Avito-платформа отображает ответ; идентификаторы исходящих сообщений кешируются для дедупликации. Если включён автоответ и активен рабочий интервал, задача повторно планируется (для ручного сообщения это «ответ уже дан», поэтому новый автоответ не ставится).

### Обработка вебхуков Telegram
- Путь: `/api/webhooks/telegram/{bot_id}/{webhook_secret}`. `bot_id` — первичный ключ в таблице `bots`, `webhook_secret` хранится там же.
- `Bots` при создании автоматически получают секрет (`token_urlsafe(16)`), при повторной установке webhook секрет пересоздаётся.
- Если секрет не совпадает, backend возвращает 404 и пишет предупреждение в лог.
- Команда `/getid` в любом чате отвечает сообщением с `chat_id` и, при наличии, `Thread ID`.

## Модель данных
- **clients** — юрлица/организации. Используются для сегментации доступа; добавлены поля `auto_reply_enabled`, `auto_reply_always`, `auto_reply_start_time`, `auto_reply_end_time`, `auto_reply_timezone`, `auto_reply_text`.
- **users** — сотрудники; содержат `role`, `telegram_user_id`, опциональный `client_id`.
- **bots** — Telegram-боты клиентов: `token`, `bot_username`, `group_chat_id`, `topic_mode`, `webhook_secret`, `status`.
- **avito_accounts** — свзяь между клиентом и Avito, хранит `api_client_id`, `api_client_secret`, `access_token`, `token_expires_at`, `bot_id`.
- **dialogs** — отображения Avito-чат ↔ Telegram topic. Поля `telegram_topic_id`, `telegram_chat_id`, `last_message_at`, `auto_reply_last_sent_at`.
- **messages** — история переписки. Поля `direction` (`avito` / `telegram`), `status` (`delivered` / `sent`), исходные идентификаторы сообщений, флаг `is_auto_reply`.
- **events/audit** — зарезервированы для дальнейшего расширения.

## Интеграции и зависимости
- **Telegram Bot API** — используется для webhook, отправки сообщений и управления топиками. Базовый URL задаётся `TELEGRAM_API_BASE`.
- **Avito API** — клиентские учётные данные хранятся в `avito_accounts`. Запрос access_token происходит по `client_credentials`. Базовый URL читается из `AVITO_API_BASE`.
- **Redis** — канал обмена между вебхуками и воркером, а также источник кэшей в `AvitoService`.
- **Let’s Encrypt / Caddy** — обеспечивает автоматический TLS для `tuberry.ru`.

## Ограничения и известные риски
- Поллер Avito сейчас запускается вручную (см. `docs/OPERATIONS.md`). Для прод-окружения нужно оформить его как постоянно работающий сервис.
- Миграций схемы (Alembic) нет — любые изменения структуры таблиц требуют ручной синхронизации.
- Аутентификация использует только JWT без refresh-токенов и без ограничения числа устройств.
- Централизованный мониторинг отсутствует: состояние сервисов отслеживается через `docker compose logs` и здравие контейнеров.
