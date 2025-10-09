# Запуск и перезапуск сервисов Tuberry

Этот документ агрегирует практические команды для запуска и обслуживания всех ключевых компонентов Tuberry: фронтенда, backend API, очередей, воркеров и Avito-поллера.

## Подготовка окружения
- Скопируйте конфигурации: `cp backend/.env.example backend/.env` и `cp frontend/.env.example frontend/.env`.
- Заполните обязательные переменные (токен мастер-бота, доменные URL, Telegram Bot ID, секреты JWT).

## Первый запуск / полный деплой
```bash
docker compose up --build
```
Сборка поднимает backend, фронтенд, Redis, Postgres, воркер и мастер-бот. После запуска выполните сидинг данных:
```bash
docker compose run --rm backend python -m app.scripts.seed
```

## Прокси и HTTPS
```bash
docker compose up -d proxy
```
Caddy выполняет TLS-терминацию и проксирует `/api/*` → backend, остальной трафик → фронтенд. Перед запуском проверьте DNS и email в `deploy/Caddyfile`.

## Регулярный перезапуск сервисов
- Пересборка и обновление всех контейнеров: `docker compose up -d --build`
- Перезапуск конкретных сервисов: `docker compose restart backend worker frontend masterbot poller`
- Проверка статуса: `docker compose ps`

## Логи и диагностика
- Backend: `docker compose logs -f backend`
- Frontend: `docker compose logs -f frontend`
- Worker: `docker compose logs -f worker`
- Poller: `docker compose logs -f poller`
- Masterbot: `docker compose logs -f masterbot`
- Proxy (TLS): `docker compose logs -f proxy`
- Postgres: `docker compose logs -f postgres`

Проверка здоровья API: `curl http://localhost:8080/health` (или `https://tuberry.ru/api/health` в продакшене).

## Avito poller
Сервис `poller` поднимается автоматически и каждые `AVITO_POLLER_INTERVAL` секунд читает непрочитанные чаты Avito для всех активных аккаунтов, привязанных к ботам. Проверить состояние можно командой:
```bash
docker compose logs -f poller
```

Для ручного разового прохода (ускорить доставку в тестах) выполните:
```bash
docker compose run --rm poller python -m app.workers.avito_poller --once
```
Команда использует те же переменные окружения, что и постоянный сервис. При необходимости отрегулируйте поведение через `AVITO_POLLER_INTERVAL` и `AVITO_POLLER_MARK_READ` в `backend/.env`.

Исходящие сообщения доставляются worker'ом автоматически: достаточно отвечать в Telegram-группе клиента (в идеале — в соответствующем топике). Если Telegram не прислал `message_thread_id`, система подхватит актуальный диалог по этому чату и отправит текст в Avito без дополнительных действий.

## Вспомогательные действия
- Повторная установка зависимостей фронтенда: `docker compose run --rm frontend npm install`
- Очистка очереди задач в Redis: `docker compose exec redis redis-cli DEL tuberry:tasks`
- Подключение к БД: `docker compose exec postgres psql -U tuberry -d tuberry`
- Резервное копирование БД: `docker compose exec postgres pg_dump -U tuberry tuberry > backup.sql`

Используйте этот файл как чек-лист при регламентных операциях и инцидентах.
