# Components Research

## 1. Requirements Summary

- **Product type**: web-based личный кабинет с адаптивом (приоритет desktop > tablet > mobile).
- **Users**: существующие клиенты системы; учёт функционала и сохранение всех настроек.
- **Primary sections**:
  - Dashboard (стартовая страница, содержит заглушки под будущие виджеты).
  - Settings (выделенный раздел со всеми текущими настройками клиента: фильтры, Telegram бот, Avito аккаунты и пр.).
- **Stylistic direction**: современный "островной" интерфейс в эстетике iOS / Telegram (light glassmorphism, округлые карточки, мягкие градиенты, акцентные голубые/фиолетовые оттенки).
- **Technical constraints**: сохранить существующие API-вызовы и структуру данных; не ломать авторизацию; UI компоненты брать из реестра reui (через shadcn MCP), shadcn — только если в reui нет аналога.
- **Additional task**: унифицировать дизайн страницы логина под новый стиль.

## 2. Component Inventory (Current Implementation)

### Navigation
- Ранее отсутствовала явная структура навигации.

### Forms / Settings
- Фильтр Avito (textarea + toggle).
- Форма подключения Telegram-бота (token, chat id).
- Форма подключения Avito аккаунта (client id/secret, привязка к боту).

### Content & Data Display
- Таблицы со списками ботов и аккаунтов.
- Баннеры с успехом/ошибкой.
- Диалоги считались и выводились текстово.

### Feedback
- Переключатели через `button` + CSS.
- Удаление через `window.confirm`.

### Login Page
- Простая карточка с формой email/password.

## 3. Target Component Mapping

| Категория | Планируемые компоненты reui | Заметки |
| --- | --- | --- |
| Каркас кабинета | `@reui/accordion-menu`, `@reui/base-accordion` | Sidebar навигация с активными состояниями и группами, аккордеон для карточек настроек. |
| Карточки / плитка | `@reui/base-badge`, `@reui/base-preview-card` (использованы стилизованные панели с утилитой `glass-panel`) | Бейджи для статусов и лейблов. |
| Формы | `@reui/base-input`, `@reui/base-select`, `@reui/textarea`, `@reui/base-switch`, `@reui/base-label`, `@reui/button` | Закрывают все поля фильтра/бота/Avito, переключатели и кнопки. |
| Таблицы | `@reui/table` | Рендер списков ботов и аккаунтов. |
| Alerts / feedback | `@reui/alert`, `@reui/base-alert-dialog` | Для статуса операций и подтверждений удаления. |
| Навигация и shell | `@reui/accordion-menu`, `@reui/button`, `@reui/base-badge` | Боковое меню с группами, мобильный стэк кнопок, CTA блоки. |
| Логин | `@reui/base-input`, `@reui/base-label`, `@reui/button`, `@reui/alert`, `@reui/base-badge` | Карточка входа в новом стиле. |

## 4. Styling Plan

- Подключён Tailwind CSS 3.4.x, активирована схема Shadcn New York.
- В `globals.css` заданы светлые островные токены: `--app-gradient`, прозрачные поверхности (`--app-surface`) и вспомогательные утилиты `glass-panel`, `gradient-stroke`.
- Базовый слой `@layer base` синхронизирует Tailwind-переменные с кастомными цветами и назначает `body` фон/типографику.
- Визуальный язык: округлые контейнеры (`rounded-[26px]` и т.п.), мягкие тени (`shadow-blue-100`) и акцентные бейджи для ощущения iOS/Telegram.

## 5. Implementation Notes

- **Компоненты, добавленные через MCP / reui**: `accordion-menu`, `base-badge`, `base-accordion`, `base-preview-card`, `base-input`, `base-select`, `textarea`, `base-switch`, `base-label`, `button`, `table`, `alert`, `base-alert-dialog`.
- **ClientShell (`app/(dashboard)/client/_components/client-shell.tsx`)**: стек из `AccordionMenu` для бокового меню, CTA блоки и мобильный набор кнопок; всё оформлено в glassmorphism-стиле.
- **Dashboard (`app/(dashboard)/client/page.tsx`)**: показатели (боты/аккаунты/диалоги/фильтр) оформлены через `Badge` + `Button`; таблица последних диалогов на `Table`; дополнительные карточки roadmap.
- **Settings (`app/(dashboard)/client/settings/page.tsx`)**: `Accordion` группирует фильтр, Telegram и Avito; формы построены на `Input/Select/Textarea/Switch`; подтверждения — `AlertDialog`; табличные списки используют `Table` и `Badge`.
- **Новые разделы (analytics/reports/automations/integrations/billing/support)**: заглушки со статистикой, сценариями, таблицами и формами на основе `Badge`, `Button`, `Alert`, `Table`, `Switch` демонстрируют будущие возможности.
- **Login (`app/login/page.tsx`)**: экран авторизации с Telegram Login Widget и сворачиваемым fallback-блоком логин/пароль; первый вход автоматически создаёт пользователя/клиента и задаёт пароль `telegram_idtuberry1`.
- **Инфраструктура**: Tailwind настроен (`tailwind.config.js`, `postcss.config.js`), aliases добавлены в `tsconfig.json`, `ClientShell` реализует таб-навигацию и logout. Общие типы вынесены в `app/(dashboard)/client/types.ts`.
- **Особенности**: подтверждения удаления выполняются через `AlertDialog`; обновление данных централизовано в `load`; боковое меню синхронизировано с роутером, заглушки подчёркнуты бейджами и карточками.

## 6. Admin UI Refresh

- Страница входа администратора (`app/admin/login/page.tsx`) перенесена на стек `Badge`, `Label`, `Input`, `Button`, `Alert`; оформление повторяет карточку клиентского логина и использует тот же градиентный фон.
- Панель администратора (`app/(dashboard)/admin/page.tsx`) оформлена через `Badge`, `Button`, `Alert`, `Input`: метрики выводятся в glass-карточках, кнопки и уведомления унаследовали стили reui/shadcn, формы настроек используют базовые контролы библиотеки.
- Все изменения выдерживают существующую бизнес-логику (авторизация, загрузка сводки, сохранение настроек) и обеспечивают визуальную консистентность с личным кабинетом клиентов.
