# Мониторинг и алертинг в FinBridge

Мониторинг в FinBridge построен на стеке **Prometheus + Grafana + Alertmanager + PagerDuty**. Каждый инженер должен уметь открыть нужный дашборд и прочитать метрики своего сервиса — это часть культуры Ownership.

## Доступ к инструментам

| Инструмент | URL | Доступ |
|---|---|---|
| Grafana | `grafana.finbridge.io` | Все сотрудники (SSO через Okta) |
| Prometheus | `prometheus.finbridge.io` | Все разработчики |
| Alertmanager | `alertmanager.finbridge.io` | On-call + Platform Team |
| PagerDuty | `finbridge.pagerduty.com` | On-call инженеры и тимлиды |
| Jaeger (трейсинг) | `jaeger.finbridge.io` | Все разработчики |

## Ключевые дашборды Grafana

| Дашборд | ID | Назначение |
|---|---|---|
| Payments Core — SLI Overview | `payments-sli` | Главный операционный дашборд: error rate, latency, throughput |
| Platform Overview | `platform-overview` | Состояние кластеров, нод, базовые ресурсы |
| PostgreSQL | `postgres-overview` | Запросы, блокировки, размеры таблиц |
| Redis | `redis-overview` | Hit rate, latency, memory |
| Business Metrics | `business-kpi` | Объём транзакций, успешность платежей, провайдеры |
| Service Map | `service-map` | Граф зависимостей сервисов с latency между ними |

Открыть дашборд напрямую: `grafana.finbridge.io/d/<ID>`.

## SLI / SLO

Service Level Indicators (SLI) — метрики, которые мы обещаем клиентам. Service Level Objectives (SLO) — целевые значения.

| Метрика | SLO | Измерение |
|---|---|---|
| Availability API (checkout) | 99.95% | Успешные HTTP 2xx / все запросы |
| Error rate (checkout) | < 0.1% | HTTP 5xx / все запросы |
| p99 latency (checkout) | < 800 мс | 99-й перцентиль времени ответа |
| p50 latency (checkout) | < 150 мс | Медиана |
| Payment success rate | > 87% | Подтверждённые / инициированные транзакции |

SLO рассчитывается за скользящее 30-дневное окно. Текущий статус — на дашборде `grafana.finbridge.io/d/slo-status`.

## Как добавить метрики в сервис (Go)

Используем библиотеку `github.com/prometheus/client_golang`.

```go
package metrics

import (
    "github.com/prometheus/client_golang/prometheus"
    "github.com/prometheus/client_golang/prometheus/promauto"
)

var (
    // Счётчик
    PaymentsTotal = promauto.NewCounterVec(
        prometheus.CounterOpts{
            Namespace: "finbridge",
            Subsystem: "payments",
            Name:      "processed_total",
            Help:      "Total number of payments processed",
        },
        []string{"status", "provider", "currency"},
    )

    // Гистограмма для latency
    PaymentDuration = promauto.NewHistogramVec(
        prometheus.HistogramOpts{
            Namespace: "finbridge",
            Subsystem: "payments",
            Name:      "processing_duration_seconds",
            Help:      "Payment processing duration in seconds",
            Buckets:   []float64{0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0},
        },
        []string{"provider"},
    )
)

// Использование в коде
func ProcessPayment(payment Payment) error {
    timer := prometheus.NewTimer(PaymentDuration.WithLabelValues(payment.Provider))
    defer timer.ObserveDuration()

    err := doProcess(payment)
    status := "success"
    if err != nil {
        status = "error"
    }
    PaymentsTotal.WithLabelValues(status, payment.Provider, payment.Currency).Inc()
    return err
}
```

Метрики автоматически подбирает Prometheus — эндпоинт `/metrics` уже зарегистрирован в базовом HTTP-сервере (`pkg/httpserver`).

## Алерты

Правила алертов — в репозитории `finbridge-gitops/monitoring/alerts/`. Формат — PrometheusRule (Kubernetes CRD).

Пример правила:

```yaml
# finbridge-gitops/monitoring/alerts/payments-core.yaml
groups:
  - name: payments-core
    rules:
      - alert: PaymentErrorRateHigh
        expr: |
          rate(finbridge_payments_processed_total{status="error"}[5m])
          / rate(finbridge_payments_processed_total[5m]) > 0.01
        for: 2m
        labels:
          severity: critical
          service: payments-core
          team: payments
        annotations:
          summary: "Payment error rate above 1%"
          description: "Error rate is {{ $value | humanizePercentage }} for the last 5 minutes. SLO threshold is 0.1%."
          runbook: "https://confluence.finbridge.io/display/ENG/Runbook+PaymentErrorRateHigh"
          dashboard: "https://grafana.finbridge.io/d/payments-sli"
```

Чтобы добавить алерт для своего сервиса:
1. Создай или отредактируй файл `finbridge-gitops/monitoring/alerts/<service-name>.yaml`.
2. Сделай MR в репозиторий `finbridge-gitops`.
3. После мержа Alertmanager подхватит правила автоматически через ~2 минуты.

## PagerDuty и эскалации

Алерты с `severity: critical` → PagerDuty → звонок дежурному инженеру.
Алерты с `severity: warning` → Slack-канал **#alerts-warning**.

Расписание дежурств в PagerDuty — `finbridge.pagerduty.com/schedules`. Дежурная смена длится неделю: понедельник 10:00 МСК → следующий понедельник 10:00 МСК.

Если алерт задействовал PagerDuty но это ложное срабатывание — нажми **Acknowledge** в PagerDuty и добавь комментарий. Не игнорируй: незакрытые алерты вызывают автоэскалацию через 30 минут.

## Трейсинг (Jaeger)

Все HTTP и gRPC запросы инструментированы **OpenTelemetry**. Трейс propagation — через заголовок `traceparent` (W3C Trace Context).

```go
// Контекст трейса передаётся автоматически через middleware.
// Для добавления span-а в своём коде:
ctx, span := tracer.Start(ctx, "fraud.check_payment")
defer span.End()

span.SetAttributes(
    attribute.String("payment.id", payment.ID),
    attribute.String("payment.provider", payment.Provider),
    attribute.Float64("payment.amount", payment.AmountDecimal()),
)
```

Найти трейс в Jaeger: `jaeger.finbridge.io/search?service=payments-core` — фильтр по `payment.id` или `request_id` из заголовка ответа.

## Логи

Логи агрегируются через **Vector** → **Elasticsearch** → **Kibana** (`kibana.finbridge.io`).

Стандарт логирования — в документе `logging_standards.md`.

По вопросам мониторинга — **#platform-support** или @pavel.orlov.
