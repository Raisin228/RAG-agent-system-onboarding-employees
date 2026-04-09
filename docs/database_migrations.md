# Миграции баз данных в FinBridge

FinBridge использует **PostgreSQL 16** в качестве основного хранилища. Управление схемой — через **Flyway**. Все миграции версионируются в репозитории вместе с кодом: нет миграции в Git — нет изменения схемы в проде.

## Стек баз данных

| БД | Версия | Назначение | Хостинг |
|---|---|---|---|
| PostgreSQL | 16.3 | Основные транзакционные данные | Managed PostgreSQL в DataLine |
| PostgreSQL | 16.3 | Аналитика и отчёты (отдельный кластер) | DataLine, read replica ×3 |
| Redis | 7.2 | Кеш, сессии, rate limiting, очереди | Redis Cluster, 6 нод |
| ClickHouse | 24.3 | Audit log, аналитика транзакций | ClickHouse Cloud |

## Структура файлов миграций

```
finbridge-core/
└── migrations/
    ├── V1__initial_schema.sql
    ├── V2__add_merchant_accounts.sql
    ├── V3__payments_index_optimization.sql
    ├── V26100__add_payment_metadata_column.sql  ← номер = версия релиза
    └── R__recreate_views.sql  ← R = repeatable (пересоздаётся при изменении)
```

Формат именования: `V{номер}__{описание}.sql`. Номер монотонно возрастает. Для версий, привязанных к релизу, используем номер релиза: `V26100__...` для релиза `26.100`.

## Написание миграции

### Правила для безопасного DDL

**Добавление колонки:**

```sql
-- БЕЗОПАСНО: NOT NULL с DEFAULT
ALTER TABLE payments ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0;

-- ОПАСНО на больших таблицах: без DEFAULT PostgreSQL заблокирует таблицу
-- ALTER TABLE payments ADD COLUMN retry_count INTEGER NOT NULL;  -- ❌
```

**Индексы:**

```sql
-- ОПАСНО: CREATE INDEX блокирует запись
-- CREATE INDEX idx_payments_merchant_id ON payments (merchant_id);  -- ❌

-- БЕЗОПАСНО: CONCURRENTLY не блокирует
CREATE INDEX CONCURRENTLY idx_payments_merchant_id ON payments (merchant_id);
-- Важно: CONCURRENTLY нельзя запускать в транзакции, поэтому файл миграции
-- должен содержать только эту команду без BEGIN/COMMIT
```

**Удаление колонки:**

```sql
-- Шаг 1: в одном релизе — убрать из кода все обращения к колонке
-- Шаг 2: в следующем релизе — удалить колонку
ALTER TABLE payments DROP COLUMN IF EXISTS legacy_provider_code;
```

**Переименование колонки / таблицы — нельзя делать в одну миграцию с изменением кода.** Процесс:
1. Создать новую колонку.
2. Запустить дата-миграцию (скопировать данные) — через отдельный job, не в SQL-миграции.
3. Переключить код на новую колонку.
4. Удалить старую колонку в следующем релизе.

### Пример безопасной миграции

```sql
-- V26100__add_payment_metadata.sql
-- Добавляем JSONB колонку для хранения мета-данных транзакции.
-- Таблица payments содержит ~400M строк, поэтому используем DEFAULT.

ALTER TABLE payments
    ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}';

-- Индекс на часто используемое поле внутри JSONB
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_payments_metadata_provider
    ON payments ((metadata->>'provider_transaction_id'))
    WHERE metadata->>'provider_transaction_id' IS NOT NULL;

COMMENT ON COLUMN payments.metadata IS 'Arbitrary key-value metadata from payment providers. Added in release 26.100.';
```

## Как применить миграцию локально

```bash
# На dev-сервере, в корне проекта
make migrate  # запустит flyway migrate против локальной БД в Docker

# Проверить статус миграций
make migrate-info

# Откатить до конкретной версии (только в dev/staging!)
make migrate-undo TARGET=26099
```

## Процесс на стендах и проде

### Staging

Миграции применяются **автоматически** при деплое на staging. ArgoCD запускает init-контейнер с Flyway перед стартом основного приложения.

### Prod

1. DBA-команда проверяет миграцию: обязательно для изменений на таблицах > 10M строк.
2. Для крупных миграций (которые могут занять > 1 минуты) — согласуй время с дежурным инженером и объяви в **#releases**.
3. Продакшн миграция запускается отдельным job'ом **до** деплоя нового кода.

### Контакты DBA-команды

**#dba-support** в Slack. Для срочных вопросов — Дмитрий Харченко @dmitry.kharchenko (Lead DBA), рабочие часы 10:00–19:00 МСК.

## Частые ошибки

| Ошибка | Последствие | Как избежать |
|---|---|---|
| CREATE INDEX без CONCURRENTLY | Блокировка записи в таблицу на минуты | Всегда CONCURRENTLY |
| Удаление колонки, которую ещё читает код | Runtime error в проде | Двухшаговый процесс |
| Миграция внутри BEGIN/COMMIT с CONCURRENTLY | Ошибка Flyway | Repeatable или отдельная миграция |
| ALTER TABLE ADD COLUMN NOT NULL без DEFAULT на большой таблице | Полная блокировка таблицы | Добавлять DEFAULT '{}' или 0 |
| Хардкод schema-имени в SQL | Сломается на тестовых БД | Не писать `public.payments`, только `payments` |

## Дата-миграции (ETL)

Крупные переносы данных (> 1M строк) не делаются через Flyway-миграцию. Вместо этого:

1. Пишется отдельный Go-скрипт в `cmd/migrations/`.
2. Скрипт обрабатывает данные батчами по 10 000 записей с `LIMIT/OFFSET` или по курсору.
3. Скрипт запускается как Kubernetes Job в staging, потом в prod.
4. Прогресс логируется, скрипт идемпотентен (можно перезапустить).

Шаблон дата-миграции — в Confluence: `Engineering / Runbooks / Data Migration Template`.
