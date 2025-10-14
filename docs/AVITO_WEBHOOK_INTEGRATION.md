# Интеграция Avito Messenger Webhook (2025‑10)

Документ описывает текущую реализацию доставки входящих сообщений с Avito через вебхуки, изменения в кодовой базе, ключевые файлы и логику, а также возможные «грабли», на которые может наткнуться следующий разработчик.

## 1. Общая архитектура

```
Avito API ──(webhook POST)──▶ backend /api/webhooks/avito/messages/{account_id}/{secret}
                                 │
                                 ├─ проверка секрета + сериализация payload
                                 └─ очередь Redis (tuberry:tasks, тип avito.webhook_message)

Redis очередь ──▶ worker (app/worker.py)
                     │
                     └─ DialogService.handle_avito_message → Telegram API + SQLModel
```

* Основной вход — HTTPS webhook на домене `WEBHOOK_BASE_URL`. В prod это `https://tgmcrm.ru` (см. `backend/.env`).
* После successful обработки сообщение уходит в привязанный Telegram-топик, а в таблице `messages` появляется запись с направлением `avito`.
* Резервный механизм (`app/workers/avito_poller.py`) продолжает опрашивать Avito API. Даже если webhook временно недоступен, poller обслуживает непрочитанные чаты.

## 2. От какого endpoint-а регистрируемся

В оригинальной документации Avito встречаются разные версии `/messenger/v1/webhooks`, однако сейчас рабочий endpoint — `POST https://api.avito.ru/messenger/v3/webhook`. При регистрации достаточно передать JSON:

```json
{
  "url": "https://tgmcrm.ru/api/webhooks/avito/messages/{account_id}/{secret}",
  "events": ["message"]
}
```

`AvitoService.ensure_webhook_for_account` регистрирует вебхук автоматически при создании/обновлении аккаунта. В коде предусмотрен fallback на старые версии API (v1/v2) с игнорированием 404/410.

## 3. Изменённые файлы и ключевая логика

### 3.1 backend/app/models/avito.py
Добавлены поля:
- `webhook_secret` — сгенерированный секрет (token_urlsafe(16)).
- `webhook_url` — зарегистрированный URL.
- `webhook_enabled` — признак успеха регистрации.
- `webhook_last_error` — последнее сообщение об ошибке (строка).

t → PR уже в `SQLModel`.

### 3.2 backend/app/db/session.py
При инициализации БД (`init_db`) выполняем `ALTER TABLE avito_accounts ADD COLUMN ...`, чтобы протащить новые поля в существующих инсталляциях (см. блок с `if "postgresql" in settings.database_url`).

### 3.3 backend/app/repositories/avito_repository.py
* `create()` генерирует `webhook_secret` при создании записи.
* `ensure_secret()` гарантирует, что секрет существует.
* `set_webhook_status()` обновляет `webhook_enabled`, `webhook_url`, `webhook_last_error`.

### 3.4 backend/app/services/avito.py
* В конструктор добавлены `self._webhook_events` (вытягиваются из `setting` `AVITO_WEBHOOK_EVENTS`).
* `compose_webhook_url(account_id, secret)` формирует финальный путь.
* `ensure_webhook_for_account()`:
  - Проверяет/обновляет секрет.
  - Берёт access_token, вызывает `POST /messenger/v3/webhook` c fallback на устаревшие версии (v1/v2).
  - В случае 409 (уже зарегистрирован) просто пишет `already_registered` в ответ.
  - Записывает `webhook_enabled = true/false`, URL и описание ошибки через репозиторий.

### 3.5 backend/app/routes/avito.py
После `repo.create()` и `repo.update()` вызываем `AvitoService.ensure_webhook_for_account`. Ошибки логируются через `loguru`, но пользователю возвращается 201/200.

### 3.6 backend/app/routes/webhooks.py
* Добавлен маршрут `POST /api/webhooks/avito/messages/{account_id}/{secret}`.
* Логика:
  1. Получаем аккаунт по `account_id` и сравниваем `secret`.
  2. Читаем JSON (если плохой, возвращаем 400).
  3. Логируем первые 500 символов payload (для диагностики формата).
  4. Ставим задачу в Redis с типом `avito.webhook_message`.

### 3.7 backend/app/services/queue.py
Без изменений — `TaskQueue.enqueue()` и `dequeue()` уже существовали.

### 3.8 backend/app/worker.py
Наиболее объёмные правки:
* Реализован парсер Avito payload (`parse_avito_webhook_payload` и вспомогательные `_build_message_from_value`). Поддерживаются две структуры:
  - Новая (`version = v3.0.0`): payload вида `{ "type": "message", "value": {...}}`.
  - Используем fallback на старые поля (`messages`, `message`, `context` и т.д.).
* В сообщение добавляется `author_id` (из `value.author_id`/`user_id`).
* Перед вызовом `DialogService.handle_avito_message` worker запрашивает у `AvitoService` ID аккаунта (`_get_account_user_id`) и фильтрует сообщения, где `author_id` == `account_user_id` (во избежание эхо-событий — ответ менеджера не дублируется как входящий).

### 3.9 docs/SETUP.md и docs/OPERATIONS.md
Дополнены разделы о вебхуках (`AVITO_WEBHOOK_EVENTS`, проверка `webhook_enabled` и `webhook_last_error`, описание fallback на poller).

### 3.10 frontend/Dockerfile и docker-compose.yml
Мелкие изменения: `npm ci --omit=dev` в этапе `runner`; убраны volume/порт 3000 наружу, чтобы исключить конфликт с существующим node-процессом.

## 4. Взаимодействие с Telegram
Всё остаётся прежним: `DialogService.handle_avito_message` создаёт/обновляет диалог, отправляет текст/вложения в Telegram (группы или топики). Примечание: для корректной доставки нужна привязка Avito-аккаунта к конкретному Telegram-боту (`bot_id`), иначе `_ensure_dialog_context` упадёт с `ValueError("Avito account not linked to bot")`.

## 5. Проверка рабочей цепочки
1. **Регистрация аккаунта**: `POST /api/avito/accounts` с `api_client_id`, `api_client_secret`, `bot_id`. В ответе `webhook_enabled` должен стать `true` (колонки можно просмотреть: `SELECT id, webhook_enabled, webhook_last_error FROM avito_accounts;`).
2. **Передача сообщения**: Отправить сообщение с Avito → should trigger webhook (`docker compose logs backend | grep "/api/webhooks/avito"`).
3. **Worker**: `docker compose logs worker` — должно быть видно `Processing task avito.webhook_message` и отсутствие ошибки «did not contain parsable messages».
4. **Telegram**: сообщение появляется в нужном топике.
5. **Echo-фильтр**: когда менеджер отвечает из Telegram, worker сравнивает `author_id` с `account_user_id` и не обрабатывает webhook с собственными ответами (нг нет двойных сообщений).

## 6. Возможные «грабли»
- **404 на /messenger/v1/webhooks**: устаревший endpoint; если Avito отключит v3, нужно будет проверить документацию (на момент интеграции v3 работает).
- **webhook_last_error**: если в БД значение не пустое — регистрация не прошла. Обычно это сетевые ошибки или 404. Перезапись через `PATCH /api/avito/accounts/{id}` повторит попытку.
- **Avito poller** регулярно пытается дергать `/order-management/1/orders`. Если нет прав на просмотр заказов, в логах появляется `403 Forbidden`. Это не влияет на webhook, но шумит — можно или отключить order-поллинг, или ограничить список статусов.
- **Секрет**: хранится в базе, используется в URL. Для замены — вызвать `PATCH /api/avito/accounts/{id}`, метод `ensure_secret()` сгенерирует новый токен и переустановит вебхук.
- **Redis / Event loop closed**: при запуске синхронного скрипта в `docker compose exec backend python - <<'PY'...` может закрываться event loop и всплывать warning `RuntimeError: Event loop is closed`. Это побочный эффект — Pyth – не страшно.

## 7. Файлы, затронутые в кодовой базе
```
backend/app/core/config.py
backend/app/db/session.py
backend/app/models/avito.py
backend/app/repositories/avito_repository.py
backend/app/routes/avito.py
backend/app/routes/webhooks.py
backend/app/schemas/avito.py
backend/app/services/avito.py
backend/app/worker.py
backend/app/services/queue.py (используется без изменений)
docs/SETUP.md
docs/OPERATIONS.md
frontend/Dockerfile
docker-compose.yml
```

## 8. Тестовые команды
* Проверить статус аккаунта:
  ```bash
  docker compose exec postgres \
    psql -U tuberry -d tuberry \
    -c "SELECT id, webhook_enabled, webhook_last_error FROM avito_accounts;"
  ```
* Отправить тестовый webhook:
  ```bash
  curl -X POST https://tgmcrm.ru/api/webhooks/avito/messages/<id>/<secret> \
       -H 'Content-Type: application/json' \
       -d '{"test":"payload"}'
  ```
* Логи worker’а:
  ```bash
  docker compose logs -f worker
  ```
* Проверить очередь:
  ```bash
  docker compose exec redis redis-cli LLEN tuberry:tasks
  ```

## 9. Резюме
- Вебхук зарегистрирован автоматически на `messenger/v3/webhook`.
- Secrets и статус хранятся в `avito_accounts`.
- Worker парсит payload `v3.0.0`, фильтрует «эхо» и отдаёт сообщение в `DialogService`.
- В случае падения вебхука можно полагаться на poller (но он не обслужит мгновенно).
- Документация (`SETUP`, `OPERATIONS`) отражает новые переменные и команды.

Любые изменения по Avito API, отличающиеся payload, должны быть внесены в `parse_avito_webhook_payload` и `_build_message_from_value`.
