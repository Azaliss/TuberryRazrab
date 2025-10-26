# Личные Telegram-аккаунты в Tuberry

Документ описывает архитектуру, настройку и эксплуатацию поддержки личных Telegram-аккаунтов в Tuberry. Функциональность позволяет подключать аккаунты сотрудников через QR-код, получать входящие сообщения в рабочей группе проекта и отправлять ответы из Telegram обратно в личные чаты и группы клиентов.

## 1. Конфигурация и подготовка

### 1.1 Переменные окружения

В `backend/.env` добавлены новые параметры:

- `PERSONAL_TELEGRAM_API_ID` — идентификатор приложения Telegram (My Telegram → API development tools). Можно оставить пустым — тогда будет использован встроенный ID официального клиента Telegram (Android).
- `PERSONAL_TELEGRAM_API_HASH` — соответствующий API hash. При пустом значении используется встроенный hash Telegram (Android).
- `PERSONAL_TELEGRAM_SESSION_SECRET` — произвольная строка для шифрования MTProto-сессий (по умолчанию используется `APP_SECRET`).
- `PERSONAL_TELEGRAM_QR_TIMEOUT` — время жизни QR-кода для авторизации, сек. (по умолчанию 180).
- `PERSONAL_TELEGRAM_DEVICE_MODEL`, `PERSONAL_TELEGRAM_SYSTEM_VERSION`, `PERSONAL_TELEGRAM_APP_VERSION`, `PERSONAL_TELEGRAM_LANG_CODE`, `PERSONAL_TELEGRAM_SYSTEM_LANG_CODE` — параметры эмуляции устройства при MTProto-авторизации. По умолчанию выставлены значения реального Android-смартфона (Samsung Galaxy S24 Ultra) и русского языка интерфейса.

Если оставить значения пустыми, авторизация будет использовать встроенный набор идентификаторов; при необходимости вы можете заменить их на собственные креды.

### 1.2 Сервисы

`docker-compose.yml` содержит дополнительный сервис:

```yaml
personal-worker:
  build:
    context: ./backend
    dockerfile: Dockerfile
  command: python -m app.workers.personal_telegram_worker
  env_file:
    - backend/.env.example
    - backend/.env
  depends_on:
    postgres:
      condition: service_healthy
    redis:
      condition: service_started
  restart: unless-stopped
```

Worker необходимо запускать вместе с backend, worker и masterbot.

## 2. Архитектура решения

### 2.1 Данные

Создана таблица `personal_telegram_accounts`:

| поле                  | описание                                               |
|-----------------------|--------------------------------------------------------|
| `id`                  | первичный ключ                                         |
| `client_id`, `project_id` | принадлежность клиенту и проекту                |
| `display_name`, `username`, `phone` | данные о владельце аккаунта          |
| `telegram_user_id`    | идентификатор пользователя в Telegram                  |
| `status`              | `pending`, `active`, `error`                           |
| `session_payload`     | зашифрованная строка `StringSession`                   |
| `accepts_private/groups/channels` | флаги допустимых типов чатов           |
| `last_connected_at`, `last_error` | телеметрия                                |

В `dialogs` добавлена колонка `personal_account_id`, а перечисления `DialogSource` и `MessageDirection` расширены значениями `personal_telegram`/`personal_telegram_in/out`.

### 2.2 Backend

- `PersonalTelegramAccountService`:
  - инициирует QR-авторизацию, шифрует MTProto-сессии и создаёт записи в БД;
  - предоставляет REST-методы для списка, обновления флагов и удаления аккаунтов;
  - управляет двухфакторной авторизацией: при требовании пароля переводит сессию в статус `password_required`, удерживает MTProto-клиент и завершает логин после успешного `sign_in`;
  - обрабатывает входящие сообщения (создаёт диалог или находит существующий, зеркалирует сообщение в рабочий чат, создаёт записи `messages`);
  - помещает исходящие ответы операторов в персональную очередь Redis.
- `PersonalTelegramAccountRepository` и расширенный `DialogRepository` обеспечивают доступ к новым сущностям.
- Роутер `/api/personal-telegram-accounts/*`:
  - `GET /` — список аккаунтов клиента (с фильтрацией по `project_id`);
  - `POST /login` — запуск QR-авторизации (owner/admin);
  - `GET /login/{login_id}` — опрос статуса (`ready` → `pending` → `completed` / `password_required`);
  - `POST /login/{login_id}/password` — ввод пароля 2FA;
  - `PATCH /{id}` — переключение флагов доставки;
  - `DELETE /{id}` — отзыв сессии и удаление аккаунта.
- `DialogService.handle_telegram_message` маршрутизирует ответы менеджеров: для диалогов `personal_telegram` создаётся запись `messages` и задача в персональной очереди.

### 2.3 MTProto-клиент

Для MTProto используется Telethon. Клиент и воркер создаются с паспортными характеристиками устройства:

```python
TelegramClient(
    session,
    api_id,
    api_hash,
    device_model=settings.personal_telegram_device_model,
    system_version=settings.personal_telegram_system_version,
    app_version=settings.personal_telegram_app_version,
    lang_code=settings.personal_telegram_lang_code,
    system_lang_code=settings.personal_telegram_system_lang_code,
)
```

По умолчанию эмулируется **Samsung Galaxy S24 Ultra / Android 14 (API 34)**. Параметры можно изменять через `.env`.

## 3. REST API

| Метод | Маршрут | Описание |
|-------|---------|----------|
| `GET` | `/api/personal-telegram-accounts` | Список аккаунтов клиента. Поддерживает фильтр `project_id`. |
| `POST` | `/api/personal-telegram-accounts/login` | Запуск QR-логина, ответ содержит `login_id`, `qr_url`, `expires_at`. |
| `GET` | `/api/personal-telegram-accounts/login/{login_id}` | Статус авторизации (`ready`, `pending`, `password_required`, `completed`, `error`, `expired`). |
| `POST` | `/api/personal-telegram-accounts/login/{login_id}/password` | Передача пароля 2FA при статусе `password_required`. |
| `PATCH` | `/api/personal-telegram-accounts/{id}` | Обновление флагов доставки и/или отображаемого имени. |
| `DELETE` | `/api/personal-telegram-accounts/{id}` | Отзыв MTProto-сессии и удаление аккаунта. |

## 4. Frontend / UX

### 4.1 Кабинет проекта (`/client/projects/[projectId]`)

- Раздел «Личные Telegram-аккаунты» показывает статусы подключений, Telegram ID и последнюю активность.
- Кнопка «Добавить персональный аккаунт» запускает модалку с QR-кодом. Без управляющего бота и рабочей группы кнопка заблокирована.
- Модалка опрашивает статус каждые 3 секунды. Если API возвращает `password_required`, появляется поле для ввода пароля двухфакторной аутентификации.
- После успешного подключения (`completed`) модалка закрывается автоматически, список аккаунтов обновляется.

### 4.2 Настройки (`/client/settings`)

- Позволяет управлять аккаунтами сразу по всем проектам. QR-модалка и сценарий 2FA идентичны странице проекта.
- Форма ввода пароля отображает ошибки (например, «Неверный пароль») и даёт повторить попытку без перезапуска QR.

### 2.3 Personal Telegram Worker

Модуль `app.workers.personal_telegram_worker`:

- синхронизирует список активных аккаунтов каждые 15 секунд;
- поднимает/останавливает клиентов Telethon (`StringSession` из БД);
- подписывается на `events.NewMessage(incoming=True)`, фильтрует сообщения по флагам `accepts_*` и передаёт их в `PersonalTelegramAccountService`;
- обрабатывает очередь `tuberry:personal:tasks` (тип `personal.send_message`) — отправляет ответы в Telegram и обновляет статусы сообщений;
- при ошибках помечает аккаунт статусом `error` и логирует детали.

Очередь обслуживается тем же Redis, что и Avito worker (`TaskQueue.enqueue_personal / dequeue_personal`).

### 2.4 Frontend

- Страница `Клиент → Настройки` получила новый раздел «Личные Telegram-аккаунты»:
  - список проектов с привязанным управляющим ботом;
  - кнопка «Добавить аккаунт» открывает модал с QR-кодом (генерируется библиотекой `qrcode`);
  - live-polling статуса авторизации (`ready`, `completed`, `error`, `expired`);
  - переключатели «Личные чаты», «Группы», «Каналы», поддержка удаления;
  - статусы и последние подключения отображаются в карточках аккаунтов.
- На странице проектов показывается количество личных аккаунтов в статистике.
- В интерфейсе диалогов тип `personal_telegram` отображается в списке и блокирует отправку сообщений через портал (ответы даются из Telegram).

## 3. Потоки

1. **Подключение аккаунта**
   - Владелец выбирает проект → фронтенд вызывает `POST /api/personal-telegram-accounts/login`.
   - Backend создаёт MTProto-клиент, инициирует `qr_login` и отдаёт `login_id` + `qr_url`.
   - Пользователь сканирует QR → worker устанавливает сессию, сервис сохраняет `StringSession` и обновляет статус `active`.
   - Фронтенд опрашивает `GET /api/personal-telegram-accounts/login/{login_id}` и закрывает модал после `completed`.

2. **Входящее сообщение**
   - Telethon worker получает `NewMessage` → фильтрует по флагам `accepts_*`.
   - `PersonalTelegramAccountService.handle_incoming_message` находит/создаёт диалог, создаёт запись `messages` и зеркалирует сообщение в рабочую группу проекта.

3. **Ответ оператора**
   - Оператор отвечает в рабочем топике управляющего бота → webhook `handle_telegram_message` определяет диалог `personal_telegram`.
   - Создаётся запись `messages` со статусом `pending`, задача отправляется в очередь `personal.send_message`.
   - Worker отправляет текст через MTProto, помечает сообщение `delivered`, обновляет статус темы.

## 4. Эксплуатация

- Перед запуском:
  1. Получите `API_ID`/`API_HASH` и пропишите их в `backend/.env`.
  2. Убедитесь, что у проекта есть управляющий бот с настроенной рабочей группой (`group_chat_id`).
  3. Запустите `personal-worker` вместе с остальными сервисами.
- Мониторинг:
  - Логи: `docker compose logs -f personal-worker`.
  - Очередь: `docker compose exec redis redis-cli LLEN tuberry:personal:tasks`.
  - Статус аккаунта: поле `status` (`active`/`error`) и `last_connected_at` в админке.
- Ротация:
  - При удалении аккаунта из UI worker остановит клиент на ближайшей синхронизации.
  - Для полной очистки можно вручную удалить связанные диалоги (при необходимости).

## 5. Отладка и типовые ошибки

- `PERSONAL_TELEGRAM_API_ID/HASH` не заданы — используется встроенный набор от Telegram (Android); при необходимости замените на собственные креды.
- QR не был подтверждён в течение таймаута (`PERSONAL_TELEGRAM_QR_TIMEOUT`) — статус `expired`, повторите авторизацию.
- Двухфакторная аутентификация включена — после сканирования QR статус становится `password_required`, в модалке появляется форма ввода пароля. При неверном пароле пользователь увидит сообщение «Неверный пароль» и может повторить попытку.
- Управляющий бот без `group_chat_id` — UI не позволит запустить авторизацию, worker не сможет доставлять сообщения.
- При некорректных токенах или сетевых сбоях worker помечает аккаунт `error` и логирует причину.

## 6. Ссылки

- Backend: `app/services/personal_telegram_account.py`, `app/workers/personal_telegram_worker.py`.
- REST: `app/routes/personal_telegram_accounts.py`.
- Frontend: `app/(dashboard)/client/settings/page.tsx`.
- Точки интеграции: `DialogService.handle_telegram_message`, `TaskQueue.enqueue_personal`.

Поддержка личных аккаунтов полностью интегрирована в существующие процессы Tuberry и готова к эксплуатации.
