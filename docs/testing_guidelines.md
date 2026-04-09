# Стандарты тестирования в FinBridge

Тесты — не опциональный бонус, а обязательная часть любой задачи. MR без тестов к новой логике не пройдёт code review. Исторический минимум покрытия по проекту — **70% для изменённых файлов**, измеряется автоматически в CI.

## Типы тестов

### Unit-тесты

Тестируют отдельную функцию или метод в изоляции от внешних зависимостей (БД, HTTP, файловая система).

**Расположение:** рядом с тестируемым файлом, суффикс `_test.go`:
```
payments/
├── processor.go
├── processor_test.go   ← unit-тесты
```

**Правила:**

- Каждый тест — одна ситуация. Не "тест ProcessPayment", а "тест ProcessPayment успешная транзакция" и "тест ProcessPayment нулевая сумма возвращает ошибку".
- Используй table-driven tests для похожих кейсов:

```go
func TestCalculateFee(t *testing.T) {
    tests := []struct {
        name     string
        amount   int64
        currency string
        provider string
        wantFee  int64
        wantErr  bool
    }{
        {
            name: "ruble payment tinkoff standard fee",
            amount: 100000, currency: "RUB", provider: "tinkoff",
            wantFee: 180, // 1.8%
        },
        {
            name: "zero amount returns error",
            amount: 0, currency: "RUB", provider: "tinkoff",
            wantErr: true,
        },
        {
            name: "unknown currency returns error",
            amount: 100000, currency: "XXX", provider: "tinkoff",
            wantErr: true,
        },
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            fee, err := CalculateFee(tt.amount, tt.currency, tt.provider)
            if tt.wantErr {
                require.Error(t, err)
                return
            }
            require.NoError(t, err)
            assert.Equal(t, tt.wantFee, fee)
        })
    }
}
```

- Используем `testify`: `github.com/stretchr/testify/assert` и `require`.
- Для моков — `github.com/stretchr/testify/mock` или `github.com/golang/mock/gomock`. Не пиши моки вручную.

### Интеграционные тесты

Тестируют взаимодействие с реальными зависимостями: PostgreSQL, Redis, внешние HTTP-сервисы (через testcontainers).

**Тег:** `//go:build integration` — чтобы unit-тесты не запускались с integration в обычном `go test ./...`.

**Расположение:** в директории `integration_test/` в корне сервиса или в пакете с суффиксом `_integration_test.go`.

```go
//go:build integration

package payments_test

import (
    "context"
    "testing"
    "github.com/testcontainers/testcontainers-go/modules/postgres"
)

func TestPaymentRepository_Save(t *testing.T) {
    ctx := context.Background()

    // Поднять реальный PostgreSQL в контейнере
    pgContainer, err := postgres.RunContainer(ctx,
        testcontainers.WithImage("postgres:16-alpine"),
        postgres.WithDatabase("finbridge_test"),
    )
    require.NoError(t, err)
    defer pgContainer.Terminate(ctx)

    connStr, _ := pgContainer.ConnectionString(ctx, "sslmode=disable")
    repo := NewPaymentRepository(connStr)

    // Тест
    payment := &Payment{Amount: 10000, Currency: "RUB"}
    err = repo.Save(ctx, payment)
    require.NoError(t, err)
    assert.NotEmpty(t, payment.ID)
}
```

Запуск:
```bash
go test ./... -tags=integration -timeout=5m
```

### End-to-End тесты

E2E тесты проверяют полный флоу через HTTP API, как это делает реальный мерчант. Живут в репозитории `finbridge-e2e`.

```
finbridge-e2e/
├── scenarios/
│   ├── checkout_flow_test.go    # полный сценарий оплаты
│   ├── refund_flow_test.go
│   └── webhook_delivery_test.go
├── fixtures/
└── Makefile
```

Запускаются против staging после деплоя:
```bash
cd finbridge-e2e
E2E_BASE_URL=https://staging.finbridge.io make run
```

E2E тесты НЕ запускаются в обычном CI на каждый push — только при деплое на staging (через CI/CD, см. `ci_cd_pipeline.md`).

### Нагрузочные тесты (Load Testing)

Инструмент: **k6** (`k6.io`). Скрипты — в репозитории `finbridge-load-tests`.

Запуск нагрузочного теста перед релизом (только для SEV-1 сценариев):
```bash
k6 run scenarios/checkout_peak_load.js \
  --env BASE_URL=https://staging.finbridge.io \
  --vus 500 \
  --duration 5m
```

Нагрузочные тесты согласовываются с Platform Team (**#platform-support**) — они требуют ресурсов staging-кластера.

## Что тестировать обязательно

| Тип изменения | Обязательные тесты |
|---|---|
| Новая бизнес-логика | Unit-тесты с позитивными и негативными кейсами |
| Новый SQL-запрос | Интеграционный тест с реальной БД |
| Новый HTTP-эндпоинт | Unit-тест handler + integration-тест repository |
| Изменение алгоритма расчёта (комиссия, конвертация) | Unit-тест со всеми граничными значениями |
| Миграция данных | Тест идемпотентности (запустить дважды — результат одинаковый) |

## Что НЕ нужно тестировать

- Getter/setter без логики.
- Сгенерированный код (proto, ORM).
- Конфигурационные структуры.
- Логирование.

## Локальный запуск тестов

```bash
# Все unit-тесты
go test ./... -race -count=1

# Unit-тесты конкретного пакета с verbose
go test ./payments/... -v -run TestCalculateFee

# Покрытие с HTML-отчётом
go test ./... -coverprofile=cover.out && go tool cover -html=cover.out -o cover.html
open cover.html

# Интеграционные тесты (нужен Docker)
go test ./... -tags=integration -timeout=10m
```

По вопросам тестирования — **#engineering** или тимлид.
