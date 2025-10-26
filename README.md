# Tuberry

Tuberry — сервис, который связывает диалоги Авито и Telegram. В проект входит веб-интерфейс для клиентов и администраторов, API на FastAPI, мастер-бот для онбординга клиентов и воркер для асинхронных задач.

Постоянно доступная прод-версия сервиса размещена по адресу [https://tuberry.ru](https://tuberry.ru).

- **frontend** — Next.js 14 (App Router), React 18, TypeScript; dev-сервер `http://localhost:3000`.
- **backend** — FastAPI + SQLModel + PostgreSQL, Redis используется как очередь задач и кэш Avito токенов.
- **worker** — асинхронный воркер, вытягивает задания `avito.send_message` из Redis и отправляет ответы в Avito.
- **masterbot** — long-polling бот, генерирует токены привязки Telegram ↔ аккаунт.
- **postgres** 15 — основная база данных.
- **redis** 7 — очередь задач (`tuberry:tasks`) и вспомогательные кэши.
- **proxy** — Caddy 2, терминатор TLS для `tuberry.ru`, проксирует `/api/*` → backend и остальное → frontend.
- **avito poller** — внешний скрипт (пример в `samples/poller.py`, аргументы `--account-id/--client-id`), который опрашивает Avito Messenger API и прокидывает непрочитанные чаты в backend.
- **projects** — новая сущность кабинета: объединяет Telegram-бота, рабочую группу и подключённые источники (Avito, Telegram и др.) в самостоятельное рабочее пространство.

Полный разбор архитектуры, схемы данных и потоков событий приведён в `docs/ARCHITECTURE.md`.

- Авторизация через Telegram Login с валидацией подписи и разграничением ролей (`admin` / `owner` / `manager`).
- Онбординг через мастер-бота (`/start` → выдача `link_token` → обмен на доступ).
- Кабинет клиента `/client`: управление проектами, каждый проект содержит бота, источники и собственные настройки.
- Кабинет администратора `/admin`: агрегированные метрики и технические настройки.
- Полная двусторонняя интеграция с Avito Messenger API: входящие сообщения доставляются в Telegram (текст, изображения, голосовые сообщения), исходящие из Telegram уходят в Avito (текст, изображения) через очередь + worker (фолбэк для сообщений без thread_id включён).
- Автоответ с расписанием и задержкой ~75 с: клиенты включают круглосуточный или интервальный режим, сообщение отправляется автоматически один раз за активный интервал и помечается в теме как «Автоответчик».
- Управление Telegram-ботами: генерация `webhook_secret`, установка вебхука прямо из UI.
- Поддержка личных Telegram-аккаунтов: подключение через QR-код, управление флагами доставки и зеркалирование диалогов в рабочие группы проектов.
- REST API (FastAPI) + очередь Redis + PostgreSQL + асинхронный воркер.
- Docker Compose окружение с Caddy/TLS, seed-скрипт, документация по запуску и эксплуатации.

## Логины и роли
- После запуска сидов (`docker compose run --rm backend python -m app.scripts.seed`) создаётся администратор: `admin@tuberry.local` / `30080724`.
- Создаётся клиент Demo и владелец `owner@demo.local` (роль owner) без пароля, вход через Telegram.
- Клиентский вход выполняется через Telegram Login: первый вход создаёт кабинет и учётку с логином `telegram_id` и паролем `telegram_idtuberry1`; дополнительно доступна ручная авторизация по этой паре.
- Связка Telegram выполняется через `/api/auth/master/link` → `/api/auth/master/exchange` или мастер-бота (`@vishenka_play_bot`).
- Полученный JWT хранится в `localStorage` ключом `tuberry_token`, фронтенд сам определяет редирект по claim `role`.

## Потоки и архитектура (кратко)
```
Telegram Login → frontend → POST /api/auth/telegram → FastAPI → JWT
Telegram /start → masterbot → /api/auth/master/link → выдача link_token → /api/auth/master/exchange → user
Avito inbound (poller) → DialogService.handle_avito_message → TelegramService → messages → планирование автоответа
Telegram webhook → DialogService.handle_telegram_message → Redis queue → worker → AvitoService.send_message → планирование автоответа (при необходимости)
```
Подробная диаграмма компонентов, описание схем данных и взаимодействий расположены в `docs/ARCHITECTURE.md`.

## Запуск и окружения
```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
# заполните токен бота, URL-адреса и креды Авито

docker compose up --build
```

Обязательные переменные:
- `backend/.env`: `MASTER_BOT_TOKEN`, `MASTER_BOT_NAME`, `WEBHOOK_BASE_URL`, `FRONTEND_BASE_URL`, `APP_SECRET`, `JWT_SECRET` (токен мастер-бота можно оставить пустым и задать через админ-панель).
- `frontend/.env`: `NEXT_PUBLIC_TELEGRAM_BOT_ID`, `NEXT_INTERNAL_API_URL` (`http://backend:8000`), при необходимости `NEXT_PUBLIC_API_URL`.
- Для прод-окружения `proxy` запрашивает TLS-сертификаты автоматически (см. `docs/SETUP.md`).

После первого старта выполните сиды, настройте вебхуки Telegram и добавьте регулярный запуск Avito-поллера — все команды и чеклисты собраны в `docs/SETUP.md` и `docs/OPERATIONS.md`.

## Документация
- `docs/SETUP.md` — пошаговый запуск, настройка переменных, прокси и вебхуков.
- `docs/ARCHITECTURE.md` — подробный разбор компонентов, схем данных и ключевых потоков.
- `docs/OPERATIONS.md` — эксплуатация, доступы, резервное копирование, команды, отладка, чеклисты.
- `docs/ROADMAP.md` — ближайшие задачи, технические долги и идеи развития.
- `docs/PERSONAL_TELEGRAM_ACCOUNTS.md` — архитектура и эксплуатация поддержки личных Telegram-аккаунтов.

## Roadmap (краткое резюме)
- Автоматизировать Avito polling (отдельный сервис/worker, retry, мониторинг).
- Добавить refresh-токены, logout и управление сессиями.
- Обогатить аудит и метрики (dashboards, уведомления, статусы диалогов).
- Внедрить Alembic и выстроить миграционную стратегию.

Детальный план с приоритетами и оценками — в `docs/ROADMAP.md`.

## Настройка домена
1. Пропишите DNS A-запись `tuberry.ru` (и CNAME `www`) на IP сервера.
2. Проверьте email в `deploy/Caddyfile` и откройте порты `80/443`.
3. Запустите `docker compose up -d proxy` — Caddy выпустит сертификат и начнёт проксировать запросы.
4. Обновите вебхуки Telegram/Авито на `https://tuberry.ru/api/...`.

Дополнительные операционные сценарии и команды приведены в `docs/OPERATIONS.md`.
