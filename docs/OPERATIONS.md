# Операционное руководство

Публичная версия сервиса постоянно доступна по адресу [https://tuberry.ru](https://tuberry.ru).

## Доступы и учётные записи
- **Администратор**: создаётся скриптом `docker compose run --rm backend python -m app.scripts.seed`
  - email: `admin@tuberry.local`
  - пароль (по умолчанию): `30080724`
  - роль: `admin`
- **Demo владелец**: `owner@demo.local`, роль `owner`, без пароля. Для входа нужен Telegram (`telegram_user_id` прописывается в сидере).
- **Клиенты через Telegram Login**: при первом входе создаётся пользователь с логином `telegram_id` и паролем `telegram_idtuberry1`; учётка получает роль `owner` и собственный кабинет. Тот же логин/пароль можно использовать на странице входа в разворачиваемом блоке.
- **Telegram**: основной мастер-бот `@vishenka_play_bot`, токен хранится в настройках проекта (админ-панель), стартовое значение можно задать в `backend/.env` (`MASTER_BOT_TOKEN`).
- **JWT**: срок жизни задаётся `JWT_EXPIRES` (секунды). Токен выдаётся ручкой `/api/auth/telegram` и хранится в `localStorage` ключом `tuberry_token`.

## Конфигурация окружения
- Файлы `.env` лежат в `backend/.env` и `frontend/.env`. Значения из `.env.example` используются как дефолты, но не содержат секретов.
- Для прод-окружения дополнительно проверьте:
  - `WEBHOOK_BASE_URL` и `FRONTEND_BASE_URL` → `https://tuberry.ru`.
  - `MASTER_BOT_TOKEN`, `MASTER_BOT_NAME` (можно обновлять из админ-панели).
- Персональные OAuth-креды Авито заполняются пользователями в кабинете (`client_id` / `client_secret`).
  - `NEXT_PUBLIC_API_URL=https://tuberry.ru` и `NEXT_PUBLIC_TELEGRAM_BOT_ID=7851544091`.
  - `NEXT_PUBLIC_TELEGRAM_LOGIN_BOT=vishenka_play_bot` (username бота, который используется в Telegram Login).
  - Прокси-роут `/api/[...path]` на фронтенде перенаправляет запросы к `NEXT_INTERNAL_API_URL` (по умолчанию `http://backend:8000`). Поэтому даже при ошибках внешнего прокси авторизация и личный кабинет остаются доступными с того же origin.
- Изменили .env → перезапустите сервис (`docker compose restart <service>`).

## Деплой и перезапуск
```bash
docker compose pull                # обновить образы Caddy/Postgres/Redis
docker compose up -d --build        # пересобрать backend/frontend/masterbot/worker
```
- Перезапуск отдельных сервисов: `docker compose restart backend worker frontend masterbot poller`.
- Проверка состояния: `docker compose ps`.

## Логи и мониторинг
- Backend: `docker compose logs -f backend`
- Frontend (dev server): `docker compose logs -f frontend`
- Worker: `docker compose logs -f worker`
- Masterbot: `docker compose logs -f masterbot`
- Caddy/HTTPS: `docker compose logs -f proxy`
- Postgres: `docker compose logs -f postgres`

### Здоровье сервисов
- API health-check: `curl https://tuberry.ru/api/health` (или локально `http://localhost:8080/health`).
- Redis/очередь: `docker compose exec redis redis-cli LLEN tuberry:tasks`.
- Проверка токена: `curl -H "Authorization: Bearer <token>" https://tuberry.ru/api/clients/me`.

## База данных
- Подключение psql: `docker compose exec postgres psql -U tuberry -d tuberry`.
- Бэкап: `docker compose exec postgres pg_dump -U tuberry tuberry > backup.sql`.
- Восстановление: `docker compose exec -T postgres psql -U tuberry -d tuberry < backup.sql`.

## Очередь и воркер
- Очередь хранится в Redis ключом `tuberry:tasks`.
- Форс-очистка: `docker compose exec redis redis-cli DEL tuberry:tasks`.
- Если воркер не поднимается — проверьте логи и доступ к Redis (`REDIS_URL`).

## Автоответчик
- Включается в кабинете клиента (`/client/settings`) блоком «Автоответ». Можно выбрать круглосуточный режим или задать интервал и часовой пояс (только города РФ).
- После получения входящего сообщения `DialogService` планирует доставку автоответа через ~75 секунд. В логе `backend` появится `Auto-reply scheduled...`, позже — `Auto-reply sent...`.
- За один активный интервал автоответ отправляется единожды. При выключении и повторном включении (с сохранением) отметки сбрасываются, и автоответ сработает снова.
- Автоответ попадает в Telegram с префиксом «🤖 Автоответчик», в Avito уходит только пользовательский текст.
- Для отладки проверяйте `docker compose logs -f backend` и `docker compose logs -f worker`: если сообщение не дошло, ищите ошибки `Failed to execute scheduled auto-reply` или HTTP-ответы Avito.

## HTTPS и домен
- DNS: A- и CNAME-записи `tuberry.ru`/`www` должны указывать на сервер.
- Caddy (`deploy/Caddyfile`) автоматически запрашивает сертификаты Let’s Encrypt для доменов.
- Критично, чтобы порты 80/443 были открыты; при изменении email обновите файл и перезапустите `proxy`.

## Telegram Master Bot
- Работает через long polling (`getUpdates`). При падении — проверяйте токен и сетевой доступ к `https://api.telegram.org`.
- Принудительный перезапуск: `docker compose restart masterbot`.
- Для диагностики можно отправить команде `/start` — в логе должно появиться выдача токена.

## Telegram и Avito
- **Telegram webhook** — `https://tuberry.ru/api/webhooks/telegram/<BOT_ID>/<WEBHOOK_SECRET>`. `BOT_ID` — первичный ключ в таблице `bots`, `WEBHOOK_SECRET` автоматически генерируется при создании/обновлении бота и хранится там же.
- **Проверка секрета** — посмотреть значения можно командой `SELECT id, bot_username, webhook_secret FROM bots;`. При необходимости регенерируйте через UI (повторная установка вебхука) или отдельный скрипт.
- **Команда `/getid`** — работает во всех чатах, позволяет подтвердить `chat_id` и `message_thread_id` для topик-режима.
- **Avito входящие** — доставляются через polling (см. раздел ниже). Вебхук `/api/webhooks/avito` оставлен для совместимости, но в продакшене основной источник — poller.
- **Поддерживаемые вложения** — из Avito в Telegram прилетают текст, изображения и голосовые сообщения; в обратную сторону Avito API допускает только текст и изображения (voice-доставку платформа не предоставляет).
- **Локальная разработка** — без публичного адреса используйте `ngrok`/`localtunnel` и пропишите URL в `WEBHOOK_BASE_URL`.

### Поллер Avito (входящие сообщения)
Сервис `poller` запускается автоматически вместе с `docker compose up -d` и каждые `AVITO_POLLER_INTERVAL` секунд обходит все активные Avito-аккаунты, привязанные к ботам. Проверка и управление:
- Логи: `docker compose logs -f poller`
- Перезапуск: `docker compose restart poller`
- Изменение частоты/поведения: обновите `AVITO_POLLER_INTERVAL` и `AVITO_POLLER_MARK_READ` в `backend/.env`, затем `docker compose up -d poller`

Для ручного ускорения синхронизации можно выполнить одноразовый проход:
```bash
docker compose run --rm poller python -m app.workers.avito_poller --once
```

Каждый цикл делает следующее:
1. Получает токен по `client_credentials` из `avito_accounts`.
2. Выясняет `user_id` (`/core/v1/accounts/self`).
3. Забирает непрочитанные чаты `/messenger/v2/accounts/{user_id}/chats?unread_only=true`.
4. Для каждого чата вызывает `DialogService.handle_avito_message(...)`, создаёт/обновляет `Dialog` и отправляет сообщение в Telegram.
5. При включённом `AVITO_POLLER_MARK_READ` помечает чаты прочитанными (`POST /messenger/v1/accounts/{user_id}/chats/{chat_id}/read`).

### Worker и исходящие сообщения в Avito
- Вебхук Telegram складывает задачи (`avito.send_message`) в Redis (`tuberry:tasks`).
- Worker (`backend/app/worker.py`) забирает задачи: для текста вызывает `AvitoService.send_message` (`POST /messenger/v1/.../messages`), для изображений скачивает файл из Telegram, загружает через `/messenger/v1/accounts/{user_id}/uploadImages` и затем шлёт `POST /messenger/v1/.../messages/image`.
- Даже если Telegram не прислал `message_thread_id`, сервис берёт последний активный диалог по чату и всё равно ставит сообщение в очередь — главное отвечать в нужной группе/топике.
- После успешной отправки в логах появляется запись `Avito message sent`. Если возникла ошибка, worker пишет `Failed to send message to Avito`; повторный запуск задачи пока не автоматизирован.
- Диагностика:
  ```bash
  docker compose logs -f worker
  docker compose exec redis redis-cli LLEN tuberry:tasks
  docker compose exec postgres psql -U tuberry -d tuberry -c "SELECT direction, status, body FROM messages ORDER BY id DESC LIMIT 10;"
  ```
- Для ручного повторного запуска очистите очередь (`redis-cli DEL tuberry:tasks`) и отправьте сообщение в Telegram ещё раз.

## Обновление зависимостей
- Backend: правим `backend/requirements.txt`, затем `docker compose up -d --build backend worker masterbot`.
- Frontend: `npm install <pkg>`, `docker compose run --rm frontend npm run build`, перезапуск `frontend`.

## Отладка
- 404 на авторизации — убедитесь, что `NEXT_PUBLIC_API_URL` без двойного `/api` и прокси работает, проверьте `docker compose logs backend`.
- Ошибки Telegram Login (`Bot domain invalid`) — в BotFather командой `/setdomain` укажите `tuberry.ru` и `www.tuberry.ru`.
- Утечка токенов — очистите `localStorage` (`localStorage.removeItem('tuberry_token')`).
- Проблемы Redis/Очереди — проверьте, есть ли блокировка firewall, выбран ли верный `REDIS_URL`.

## Резервное копирование и восстановление
- Бэкапы БД — периодически сохраняйте `pg_dump`.
- Снимайте копию `.env` и `deploy/Caddyfile`, чтобы при аварии быстро восстановить окружение.
- Redis не содержит критичных данных (очередь), допускается очистка.

## Безопасность и доступы
- Не храните реальные токены в git. `.env` добавлены в `.gitignore`.
- Для продакшена включите refresh токены / ротацию JWT (см. `docs/ROADMAP.md`).
- Разграничение ролей уже используется: `admin` имеет доступ ко всем ручкам, `owner/manager` — только к клиентским операциям.

## Контакты и владельцы
- Техническая поддержка: команда разработки Tuberry (контакты TBD).
- Telegram мастер-бот отвечает за выдачу доступов. При проблемах обновите токен и перезапустите сервис.
