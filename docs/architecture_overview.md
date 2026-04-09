# Архитектура системы FinBridge

FinBridge Pay — платёжная платформа на основе микросервисной архитектуры. Система обрабатывает ~12 миллионов транзакций в месяц (~4.6 TPS в среднем, пики до 1 200 TPS в распродажи).

## Общая схема

Трафик идёт по следующей цепочке:

```
Мерчант → API Gateway → Checkout API → Payment Router → Provider Adapter → Платёжный провайдер
                              ↓                ↓
                        Fraud Detector    Settlement Service
                              ↓
                        Risk Scorer
```

## Инфраструктура

| Компонент | Технология | Где работает |
|---|---|---|
| Kubernetes | K8s 1.29 | On-premise, DataLine M9, 3 мастер-ноды, 24 воркер-ноды |
| Сеть | Cilium CNI | — |
| Service Mesh | Istio 1.21 | mTLS между сервисами, circuit breaker |
| Ingress | Nginx Ingress Controller | — |
| CDN | CloudFlare | Для статики и DDoS-защиты |
| DNS | CloudFlare DNS + внутренний CoreDNS | — |

## Ключевые сервисы

### API Gateway

**Репозиторий:** `finbridge/api-gateway`
**Язык:** Go 1.22
**Функции:** аутентификация мерчантов (API key + HMAC), rate limiting, маршрутизация, логирование входящих запросов.
**SLA:** p99 latency < 50 мс, availability > 99.99%.

### Checkout API

**Репозиторий:** `finbridge/checkout-api`
**Язык:** Go 1.22
**Функции:** создание и управление платёжными сессиями, хранение платёжных форм, Idempotency-ключи.
**БД:** PostgreSQL (основная), Redis (сессии и идемпотентность).

### Payment Router

**Репозиторий:** `finbridge/payment-router`
**Язык:** Go 1.22
**Функции:** выбор оптимального провайдера на основе правил: доступность, тип карты, валюта, мерчантские настройки. Умеет переключаться на fallback-провайдер при ошибке основного.
**Конфигурация маршрутизации:** хранится в Redis, меняется через admin-API без рестарта.

### Fraud Detector

**Репозиторий:** `finbridge/fraud-detector`
**Язык:** Go 1.22 + Python 3.12 (ML-инференс)
**Функции:** проверка каждой транзакции по правилам и ML-моделям.
**Бюджет времени:** 80 мс максимум (иначе транзакция пропускается с флагом `fraud_check=skipped`).
**ML модели:** XGBoost, обновляются еженедельно, хранятся в MLflow (`mlflow.finbridge.io`).

### Provider Adapters

**Репозиторий:** `finbridge/provider-adapters`
**Язык:** Go 1.22
**Функции:** унификация API 45 провайдеров под единый внутренний интерфейс. Каждый провайдер — отдельный plugin, динамически подгружается.
**Паттерн:** Adapter + Circuit Breaker (через Istio + кастомная логика retry).

### Webhook Dispatcher

**Репозиторий:** `finbridge/webhook-dispatcher`
**Язык:** Go 1.22
**Функции:** доставка событий мерчантам (payment.completed, payment.failed, refund.created и др.). Гарантированная доставка через очередь с retry (3 попытки, exponential backoff: 1 мин, 5 мин, 30 мин).
**Очередь:** RabbitMQ 3.13 (кластер из 3 нод).

### Settlement Service

**Репозиторий:** `finbridge/settlement-service`
**Язык:** Go 1.22
**Функции:** расчёт и проведение выплат мерчантам. Работает с банковскими API (СБП, SWIFT). Запускается по расписанию (cron: каждый рабочий день в 14:00 МСК).

## Базы данных

### Основная PostgreSQL (OLTP)

- **Кластер:** 1 primary + 2 sync-реплики + 1 async-реплика (для аналитических запросов).
- **Размер:** ~2.3 TB данных.
- **Самая большая таблица:** `payments` — ~400M строк, партиционирована по месяцу создания.
- **Connection pooling:** PgBouncer перед каждым сервисом (transaction pooling mode).
- **Backup:** pg_dump каждые 6 часов, WAL-архивация в S3, retention 30 дней.

### Redis Cluster

- 6 нод (3 primary, 3 replica).
- Используется для: кеширования правил маршрутизации, хранения idempotency-ключей (TTL 24ч), rate limiting, кеширования merchant-конфигов.

### RabbitMQ

- 3-нодный кластер с quorum queues.
- Очереди: `payments.events`, `webhooks.outbound`, `notifications.email`.

### ClickHouse

- Аналитические данные: все транзакции, агрегации, audit log.
- Обновление: через Kafka (топик `payments.events`) в real-time.
- Размер: ~40 TB, хранение 2 года.

## Сервисная коммуникация

- **Синхронная:** gRPC (внутри кластера, mTLS через Istio). Таймаут по умолчанию — 3 секунды.
- **Асинхронная:** RabbitMQ для событий, которые не требуют синхронного ответа.
- **Service Discovery:** Kubernetes DNS (имена вида `payments-core.prod.svc.cluster.local`).

## Технологический стек

| Слой | Технологии |
|---|---|
| Бэкенд | Go 1.22 |
| Фронтенд (dashboard) | React 18, TypeScript, Vite |
| ML | Python 3.12, XGBoost, FastAPI |
| Хранение | PostgreSQL 16, Redis 7.2, RabbitMQ 3.13, ClickHouse 24.3 |
| Инфраструктура | Kubernetes 1.29, Istio 1.21, ArgoCD, Terraform |
| Observability | Prometheus, Grafana, Jaeger, Vector, Elasticsearch, Kibana |
| CI/CD | GitLab CI, ArgoCD |
| Feature Flags | LaunchDarkly |
| Secrets | HashiCorp Vault |

Более детальное описание каждого сервиса — в Confluence: `Engineering / Architecture / Services`.
