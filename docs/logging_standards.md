# Стандарты логирования в FinBridge

Логи — основной инструмент диагностики инцидентов. Плохо структурированный лог — это потеря времени при инциденте в 3 ночи. В FinBridge принят структурированный JSON-логинг через библиотеку `go.uber.org/zap`.

## Стек

| Компонент | Инструмент |
|---|---|
| Логирование в Go-сервисах | `go.uber.org/zap` (structured, JSON) |
| Логирование в Node.js-сервисах | `pino` |
| Сбор логов с подов | Vector (DaemonSet на каждой ноде) |
| Хранение и поиск | Elasticsearch 8.x |
| Визуализация | Kibana (`kibana.finbridge.io`) |
| Retention | 30 дней hot storage, 1 год cold (S3) |

## Уровни логирования

| Уровень | Когда использовать |
|---|---|
| `DEBUG` | Детальная трассировка для локальной разработки. В проде выключен. |
| `INFO` | Значимые бизнес-события: платёж принят, webhook отправлен, мерчант зарегистрирован. |
| `WARN` | Ситуация нестандартная, но приложение продолжает работу: retry, деградированный режим. |
| `ERROR` | Ошибка, которая не позволила выполнить операцию. Требует внимания. |
| `FATAL` | Приложение не может продолжать работу. Завершает процесс. Используй только в `main()`. |

**Правило:** если сомневаешься между INFO и WARN — используй WARN. INFO должен оставлять следы бизнес-процессов, не технические детали.

## Обязательные поля в каждом логе

Базовый логгер уже добавляет эти поля автоматически (настроен в `pkg/logger`):

| Поле | Пример | Откуда |
|---|---|---|
| `timestamp` | `2026-04-09T10:31:45.123Z` | zap |
| `level` | `info` | zap |
| `service` | `payments-core` | env var `SERVICE_NAME` |
| `version` | `rc-26.100` | env var `SERVICE_VERSION` |
| `env` | `prod` | env var `ENV` |
| `trace_id` | `4bf92f3577b34da6a3ce929d0e0e4736` | OpenTelemetry контекст |
| `span_id` | `00f067aa0ba902b7` | OpenTelemetry контекст |
| `request_id` | `req_01HX3K...` | HTTP middleware |

## Как логировать в Go

```go
// Инициализация (в main.go)
logger, _ := logger.New(cfg.LogLevel, cfg.ServiceName, cfg.Version)
defer logger.Sync()

// В handler или service — передаём logger через context
func (s *PaymentService) Process(ctx context.Context, req ProcessRequest) (*Payment, error) {
    log := logger.FromContext(ctx)

    // INFO: значимое бизнес-событие
    log.Info("processing payment",
        zap.String("payment_id", req.PaymentID),
        zap.String("merchant_id", req.MerchantID),
        zap.Int64("amount_minor", req.AmountMinor),
        zap.String("currency", req.Currency),
        zap.String("provider", req.Provider),
    )

    result, err := s.provider.Charge(ctx, req)
    if err != nil {
        // ERROR: не смогли выполнить операцию
        log.Error("payment charge failed",
            zap.String("payment_id", req.PaymentID),
            zap.String("provider", req.Provider),
            zap.Error(err),
        )
        return nil, fmt.Errorf("charge via %s: %w", req.Provider, err)
    }

    log.Info("payment processed successfully",
        zap.String("payment_id", req.PaymentID),
        zap.String("provider_tx_id", result.ProviderTransactionID),
        zap.Duration("processing_time", result.Duration),
    )
    return result.Payment, nil
}
```

## Что запрещено логировать

FinBridge работает с платёжными данными (PCI DSS Level 1). Следующие данные **никогда** не должны попадать в логи:

| Что запрещено | Примеры |
|---|---|
| Номер карты (PAN) | `4111111111111111`, `4111 **** **** 1111` |
| CVV / CVC | `123` |
| Полный номер счёта | `40817810099910004312` |
| Пароли и токены | `Bearer eyJ...`, `secret_key_live_...` |
| Персональные данные | ФИО, паспортные данные, дата рождения |

Логгер автоматически маскирует паттерны карт (регулярка `\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b`), но если логируешь struct с кастомными полями — проверь вручную.

**Безопасный способ логировать ID карты:**

```go
// НЕ ТАК:
log.Info("payment", zap.String("card", card.Number))  // ❌

// ТАК:
log.Info("payment", zap.String("card_last4", card.Number[len(card.Number)-4:]))  // ✅
// Выведет: "card_last4": "1234"
```

## Поиск логов в Kibana

URL: `kibana.finbridge.io`

Индексы: `finbridge-prod-*`, `finbridge-staging-*`

Полезные KQL-запросы:

```
# Все ошибки сервиса за последний час
level: "error" AND service: "payments-core"

# Логи конкретного запроса по request_id
request_id: "req_01HX3K2M9P4V8NQF6TYWZ5BCDE"

# Логи конкретного платежа (trace_id из ответа API)
payment_id: "pay_01HX3K2M9P4V8NQF6TYWZ5BCDE"

# Медленные запросы к БД
service: "payments-core" AND message: "slow query" AND duration_ms > 1000

# Ошибки конкретного провайдера
provider: "tinkoff" AND level: "error"
```

## Структурированный пример лога в production

```json
{
  "timestamp": "2026-04-09T10:31:45.123Z",
  "level": "error",
  "service": "payments-core",
  "version": "rc-26.100",
  "env": "prod",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "00f067aa0ba902b7",
  "request_id": "req_01HX3K2M9P4V8NQF6TYWZ5BCDE",
  "message": "payment charge failed",
  "payment_id": "pay_01HX3K2M9P4V8NQF6TYWZ5BCDE",
  "merchant_id": "merch_01HX3K2M9P4V8NQF6TYWZ5BCDE",
  "provider": "tinkoff",
  "error": "tinkoff: connection timeout after 3000ms",
  "retry_attempt": 2
}
```

По вопросам логирования — **#platform-support** или @pavel.orlov.
