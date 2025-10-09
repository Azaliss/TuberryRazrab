# Запуск окружения

## Требования
- Docker + Docker Compose
- Telegram Bot API токен мастер-бота (используется и для авторизации, и для выдачи ссылок)
- Учётные данные Авито (client id/secret) при интеграции с их API

## Конфигурация переменных окружения

### Backend (`backend/.env`)
Создайте файл `.env` из примера и заполните ключевые значения:

- `MASTER_BOT_TOKEN` — токен мастер-бота для онбординга (можно оставить пустым и заполнить через админ-панель).
- `MASTER_BOT_NAME` — @username мастер-бота (используется как дефолт при инициализации настроек).
- `APP_SECRET`, `JWT_SECRET` — произвольные случайные строки.
- `WEBHOOK_BASE_URL` — публичный URL, куда Telegram будет слать вебхуки (например, `https://example.com`).
- `FRONTEND_BASE_URL` — адрес фронтенда, который бот отправляет пользователям (например, `http://localhost:3000`).
- `BACKEND_INTERNAL_URL` — внутренний адрес backend-сервиса для docker-compose (оставьте `http://backend:8000`, если не меняли сеть).
- `AVITO_POLLER_INTERVAL` — интервал опроса Avito API в секундах (по умолчанию 30).
- `AVITO_POLLER_MARK_READ` — помечать ли чаты прочитанными после успешной доставки (`true`/`false`).
- OAuth-креды Авито (`client_id`, `client_secret`) вводятся для каждого аккаунта в кабинете клиента; backend хранит access_token и срок его жизни.

Остальные значения можно оставить из примера либо скорректировать при необходимости.

### Frontend (`frontend/.env`)
Скопируйте пример и укажите параметры обращения к API и Telegram:

- `NEXT_PUBLIC_API_URL` — базовый URL API. Можно оставить пустым, тогда браузер будет обращаться на `http(s)://<host>:8080`.
- `NEXT_INTERNAL_API_URL` — адрес API для SSR (оставьте `http://backend:8000`).
- `NEXT_PUBLIC_TELEGRAM_BOT_ID` — числовой идентификатор бота (используется для других сценариев интеграции).
- `NEXT_PUBLIC_TELEGRAM_LOGIN_BOT` — username бота, включённого в Telegram Login Widget (например, `vishenka_play_bot`).

## Сборка и запуск
```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
# заполните параметры в обоих файлах

docker compose up --build
```

Сервисы backend, worker, Redis и Postgres стартуют автоматически. Фронтенд доступен по `http://localhost:3000`, API — по `http://localhost:8080`.

### Прокси и HTTPS
Для публичного домена (`tuberry.ru`) добавлен сервис `proxy` с Caddy.

- Проверьте `deploy/Caddyfile`: замените email в первой секции при необходимости.
- Убедитесь, что DNS‑записи `tuberry.ru`/`www` смотрят на ваш сервер и что порты `80` и `443` открыты.

Запустить прокси:
```bash
docker compose up -d proxy
```

Caddy автоматически выпустит сертификаты Let’s Encrypt и будет проксировать `/api/*` на `backend:8000`, а остальные запросы на `frontend:3000`.

Если домен уже закреплён, не забудьте в BotFather командой `/setdomain` указать `tuberry.ru` и `www.tuberry.ru`, иначе Telegram Login покажет «Bot domain invalid».

### Начальная инициализация данных
После первого старта создайте базовые записи (админ и демо-клиент):
```bash
docker compose run --rm backend python -m app.scripts.seed
```

## Авторизация пользователей

На странице `/login` и на главной (`/`) теперь используется Telegram Login Widget (доступен и fallback-блок с вводом логина/пароля). Процесс выглядит так:

1. Пользователь нажимает кнопку и подтверждает вход через Telegram.
2. Фронтенд отправляет данные Telegram Login на `POST /api/auth/telegram`.
3. Backend проверяет подпись с использованием `MASTER_BOT_TOKEN`. Если пользователь входит впервые, создаются запись клиента и пользователя, логин `telegram_id`, пароль `telegram_idtuberry1` (пароль сохраняется в хэшированном виде). Для повторных входов используется существующая запись.

Полученный токен сохраняется в `localStorage` (`tuberry_token`) и используется во всех запросах фронтенда.

### Привязка Telegram к пользователю
Чтобы пользователь смог войти через Telegram, в базе должен быть заполнен `telegram_user_id`.

Варианты привязки:
- Запустите сервис `masterbot` (`docker compose up masterbot`) и попросите пользователя отправить `/start`. Бот сгенерирует ссылку с токеном, который можно обменять на доступ через endpoint `POST /api/auth/master/exchange` (нужно указать email и ФИО).
- Либо привяжите идентификатор вручную через админский скрипт/SQL (например, для существующего пользователя).

Пример обмена токена на доступ:
```bash
curl -X POST http://localhost:8080/api/auth/master/exchange \
  -H 'Content-Type: application/json' \
  -d '{
        "token": "<link_token_from_bot>",
        "email": "user@example.com",
        "full_name": "Имя Фамилия"
      }'
```
В ответе придёт `access_token`, который можно сразу использовать в UI.

## Доступ в админ-панель

- Админская панель развёрнута на том же домене по пути `/admin` (в продакшене `https://tuberry.ru/admin`).
- На время разработки используется пара `admin` / `30080724`; параметры можно переопределить через `ADMIN_BASIC_USERNAME` / `ADMIN_BASIC_PASSWORD`.
- Учётка администратора создаётся автоматически (email `admin@tuberry.local`) и при входе получает JWT с ролью `admin`.

## Полезные команды
- Просмотр логов конкретного сервиса: `docker compose logs -f frontend`
- Пересборка фронтенда после изменения зависимостей: `docker compose run --rm frontend npm install`
- Применение миграций/инициализация: `docker compose run --rm backend alembic upgrade head` (если миграции добавятся)

С предупреждением Redis о `vm.overcommit_memory` можно работать в дев-режиме, но для продакшена настройте параметр на хостовой машине.

## Настройка клиентских ботов
1. В кабинете клиента создайте запись бота и укажите токен BotFather.
2. После сохранения backend сгенерирует `webhook_secret` и попытается выставить вебхук на URL `WEBHOOK_BASE_URL/api/webhooks/telegram/{bot_id}/{webhook_secret}`.
3. Проверить значения можно запросом:
   ```bash
   docker compose exec -T postgres psql -U tuberry -d tuberry -c "SELECT id, bot_username, webhook_secret, group_chat_id FROM bots;"
   ```
4. Команда `/getid` в привязанной группе поможет определить `chat_id` и `Thread ID` (если используется форумы).

## Настройка Avito аккаунтов
1. Создайте Avito-аккаунт в UI, указав `client_id`, `client_secret` и привязанный бот.
2. После сохранения backend будет автоматически получать `access_token` и сохранять его в таблицу `avito_accounts`.
3. Для входящих сообщений используется отдельный сервис `poller`, который стартует автоматически вместе с `docker compose up -d`. Он опрашивает все активные Avito-аккаунты, привязанные к ботам, с интервалом `AVITO_POLLER_INTERVAL` секунд и по умолчанию помечает чаты прочитанными.

   Для ускорения теста можно выполнить разовый проход вручную:
   ```bash
   docker compose run --rm poller python -m app.workers.avito_poller --once
   ```
   Команда подхватит те же переменные окружения, что и штатный сервис.
4. Для проверки работы вручную воспользуйтесь примером из `docs/OPERATIONS.md` — пришлите сообщение с Avito и убедитесь, что в Telegram создался новый топик.

## Проверка сквозной интеграции
1. Отправьте тестовое сообщение из Avito (со стороны клиента).
2. Подождите до `AVITO_POLLER_INTERVAL` секунд — входящее сообщение автоматически появится в Telegram (poller дёргается непрерывно).
3. Ответьте в Telegram-топике (можно без явного Reply — сервис сопоставит сообщение с последним диалогом и поставит его в очередь). Worker мгновенно отправит текст обратно в Avito; проверить можно в интерфейсе Avito или повторной выборкой через API.
4. Убедитесь, что чат отмечен прочитанным (`SELECT direction, status FROM messages ORDER BY id DESC;` показывает оба направления).

Дополнительные эксплуатационные сценарии (резервное копирование, мониторинг, отладка) описаны в `docs/OPERATIONS.md`.
