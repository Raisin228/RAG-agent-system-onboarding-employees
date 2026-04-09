# Стандарты проектирования API в FinBridge

В FinBridge два типа API: **REST** (внешний, для мерчантов) и **gRPC** (внутренний, между микросервисами). Внешний API документируется в OpenAPI 3.1, внутренний — в Protobuf. Это разделение принципиально: менять внутренний API проще, внешний требует версионирования и deprecation-политики.

## REST API (внешний)

### URL-структура

```
https://api.finbridge.io/v{N}/{resource}/{id}/{sub-resource}
```

- Версия в пути: `/v1/`, `/v2/`. Версия меняется только при breaking changes.
- Ресурсы — существительные во множественном числе, kebab-case: `/payments`, `/merchant-accounts`.
- ID ресурса — UUID v4 (не автоинкремент, не угадываемые числа).
- Вложенность — не глубже двух уровней: `/payments/{id}/refunds` — ок, `/payments/{id}/refunds/{id}/events` — стоп, лучше `/payment-events?refund_id=`.

Примеры правильных URL:
```
GET  /v1/payments/{payment_id}
POST /v1/payments
GET  /v1/payments?merchant_id=xxx&status=completed&from=2026-01-01
POST /v1/payments/{payment_id}/refunds
GET  /v1/merchant-accounts/{account_id}/balance
```

### HTTP-методы

| Метод | Семантика | Идемпотентен? | Тело запроса |
|---|---|---|---|
| GET | Получить ресурс | Да | Нет |
| POST | Создать ресурс | Нет | Да |
| PUT | Полное обновление | Да | Да |
| PATCH | Частичное обновление | Нет | Да (RFC 7396 Merge Patch) |
| DELETE | Удалить ресурс | Да | Нет |

Создание платежа через `POST /v1/payments` должно принимать `Idempotency-Key` в заголовке — UUID, который клиент генерирует сам. Повторный запрос с тем же ключом вернёт исходный ответ без двойного списания.

### Коды ответов

| Код | Когда использовать |
|---|---|
| 200 OK | Успешное получение / обновление |
| 201 Created | Ресурс создан, в `Location` — URL нового ресурса |
| 202 Accepted | Запрос принят, обрабатывается асинхронно |
| 204 No Content | Успешное удаление |
| 400 Bad Request | Неверный формат запроса, бизнес-валидация |
| 401 Unauthorized | Не передан или невалидный токен |
| 403 Forbidden | Токен валидный, но нет прав |
| 404 Not Found | Ресурс не существует |
| 409 Conflict | Конфликт (например, дублирующий Idempotency-Key с другими параметрами) |
| 422 Unprocessable Entity | Синтаксически верный запрос, но бизнес-логика не позволяет |
| 429 Too Many Requests | Rate limit (заголовок `Retry-After` обязателен) |
| 500 Internal Server Error | Неожиданная ошибка сервера |
| 503 Service Unavailable | Сервис временно недоступен |

### Формат ошибок

Все ошибки возвращают единый формат:

```json
{
  "error": {
    "code": "INSUFFICIENT_FUNDS",
    "message": "Merchant account balance is insufficient to process this payment",
    "request_id": "req_01HX3K2M9P4V8NQF6TYWZ5BCDE",
    "details": {
      "available_balance": 150.00,
      "requested_amount": 500.00,
      "currency": "RUB"
    }
  }
}
```

- `code` — машиночитаемый код ошибки, UPPER_SNAKE_CASE. Полный список кодов — в Confluence: `API / Error Codes`.
- `message` — человекочитаемое сообщение на английском (не для конечного пользователя мерчанта — для разработчика мерчанта).
- `request_id` — уникальный ID запроса для трассировки. **Обязателен** во всех ответах, включая 200.

### Пагинация

Используем cursor-based пагинацию (не offset):

```json
{
  "data": [...],
  "pagination": {
    "cursor": "eyJpZCI6IjAxSFgzSzJNOVA0VjhOUUY2VFlXWjVCQ0RFIn0=",
    "has_more": true,
    "total_count": 1543
  }
}
```

Запрос следующей страницы: `GET /v1/payments?cursor=eyJpZC...&limit=50`. Максимальный `limit` — 100.

## gRPC API (внутренний)

Все внутренние сервисы общаются через gRPC. Protobuf-определения хранятся в репозитории `finbridge-proto` (`gitlab.finbridge.io/finbridge/finbridge-proto`).

### Структура репозитория proto

```
finbridge-proto/
├── finbridge/
│   ├── payments/
│   │   └── v1/
│   │       ├── payments.proto
│   │       └── types.proto
│   ├── fraud/
│   │   └── v1/
│   └── notifications/
│       └── v1/
```

### Правила именования

```protobuf
// Правильно
package finbridge.payments.v1;
option go_package = "gitlab.finbridge.io/finbridge/finbridge-proto/gen/go/payments/v1;paymentsv1";

message CreatePaymentRequest {
  string merchant_id = 1;       // snake_case для полей
  int64 amount_minor = 2;       // суммы в минорных единицах (копейки), не float!
  string currency = 3;          // ISO 4217
  google.protobuf.Timestamp created_at = 4;  // Timestamp, не string
}

// Неправильно
message createPaymentRequest {  // не PascalCase
  float amount = 1;             // float для денег — никогда
  string createdAt = 2;         // не camelCase
}
```

### Версионирование

- Версия в пакете: `v1`, `v2`. Breaking change → новая версия пакета.
- Не удалять и не менять номера полей в Protobuf — только добавлять новые. Удалённые поля резервируются: `reserved 3; reserved "old_field_name";`

## Документация

Каждый новый или изменённый API-эндпоинт должен быть задокументирован в OpenAPI (`api/openapi/v1.yaml` в репозитории). Мёржить MR без обновления OpenAPI — нельзя (CI проверяет через `openapi-diff`).

Генерация docs из OpenAPI:
```bash
make docs  # генерирует HTML в docs/api/ и публикует на developer.finbridge.io
```

По вопросам API Design — **#api-design** в Slack или Алексей Громов @alex.gromov (API Lead).
