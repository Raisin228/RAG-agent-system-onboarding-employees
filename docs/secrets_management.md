# Управление секретами в FinBridge

Все секреты (API-ключи, пароли БД, сертификаты, токены) хранятся централизованно в **HashiCorp Vault**. Никакой другой способ хранения секретов в проде не разрешён — ни Kubernetes Secrets в открытом виде, ни переменные среды, прописанные в манифестах, ни файлы конфигурации в Git.

## Доступ к Vault

| Окружение | URL |
|---|---|
| Production | `https://vault.finbridge.io` |
| Staging | `https://vault-staging.finbridge.io` |
| Dev (локально) | `http://localhost:8200` (Vault в Docker Compose) |

Аутентификация в Vault:

- **Разработчики** (ручной доступ): через Okta SSO — `vault login -method=oidc`
- **Сервисы в Kubernetes**: через Vault Agent Injector (Kubernetes Auth Method) — автоматически, без участия разработчика

## Структура секретов в Vault

Namespace Vault: `finbridge/`. Секреты организованы по окружениям и сервисам:

```
secret/
├── finbridge/
│   ├── prod/
│   │   ├── payments-core/
│   │   │   ├── database         # DSN для PostgreSQL
│   │   │   ├── tinkoff-adapter  # API ключи провайдера
│   │   │   └── encryption-key   # Ключ шифрования PAN
│   │   ├── fraud-detector/
│   │   │   └── redis-password
│   │   └── global/
│   │       ├── rabbitmq-creds   # Общий RabbitMQ
│   │       └── internal-jwt-key # Для межсервисного JWT
│   ├── staging/
│   │   └── ... (зеркальная структура)
│   └── dev/
│       └── ... (зеркальная структура)
```

## Как добавить новый секрет

### 1. Через Vault UI (для разработчика)

```bash
# Авторизоваться в Vault
vault login -method=oidc -address=https://vault.finbridge.io

# Добавить секрет
vault kv put secret/finbridge/staging/payments-core/new-provider \
  api_key="sk_live_abc123" \
  api_secret="secret_xyz789" \
  base_url="https://api.provider.io/v1"

# Проверить
vault kv get secret/finbridge/staging/payments-core/new-provider
```

### 2. Через Terraform (для инфраструктурных секретов)

Секреты, которые не меняются часто (например, SSL-сертификаты, конфигурация), управляются через Terraform в репозитории `finbridge-gitops/vault/`. Создай MR туда.

## Как сервис получает секреты в Kubernetes

Используется **Vault Agent Injector** — он автоматически монтирует секреты как файлы внутрь пода.

Аннотации в Deployment:

```yaml
# finbridge-gitops/manifests/prod/payments-core/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: payments-core
  namespace: prod
spec:
  template:
    metadata:
      annotations:
        vault.hashicorp.com/agent-inject: "true"
        vault.hashicorp.com/role: "payments-core-prod"
        vault.hashicorp.com/agent-inject-secret-database: "secret/finbridge/prod/payments-core/database"
        vault.hashicorp.com/agent-inject-template-database: |
          {{- with secret "secret/finbridge/prod/payments-core/database" -}}
          DATABASE_URL="{{ .Data.data.dsn }}"
          {{- end }}
```

В результате внутри пода появляется файл `/vault/secrets/database`:
```
DATABASE_URL="postgres://payments:password@postgres-primary:5432/finbridge_prod?sslmode=require"
```

Приложение читает его через `godotenv` или вручную.

## Как использовать секреты в Go-коде

```go
// pkg/config/config.go — загрузка конфигурации
package config

import (
    "github.com/joho/godotenv"
    "github.com/kelseyhightower/envconfig"
)

type Config struct {
    DatabaseURL    string `envconfig:"DATABASE_URL" required:"true"`
    TinkoffAPIKey  string `envconfig:"TINKOFF_API_KEY" required:"true"`
    EncryptionKey  string `envconfig:"ENCRYPTION_KEY" required:"true"`
}

func Load() (*Config, error) {
    // В проде файлы монтирует Vault Agent Injector
    // Локально — файл .env.local (не коммитить в Git!)
    _ = godotenv.Load("/vault/secrets/database", "/vault/secrets/tinkoff-adapter")
    _ = godotenv.Load(".env.local") // fallback для разработки

    var cfg Config
    if err := envconfig.Process("", &cfg); err != nil {
        return nil, fmt.Errorf("config: %w", err)
    }
    return &cfg, nil
}
```

## Локальная разработка

На dev-сервере секреты хранятся в `.env.local` в корне проекта. Этот файл **не коммитится в Git** (добавлен в `.gitignore`).

Шаблон для заполнения:

```bash
# Скачать актуальные секреты для разработки
vault kv get -format=json secret/finbridge/dev/payments-core/database | \
  jq -r '.data.data | to_entries[] | "\(.key | ascii_upcase)=\(.value)"' >> .env.local
```

Или запросить готовый `.env.local` у коллеги из команды через зашифрованный канал (не через Slack — только через 1Password shared vault `FinBridge Dev Secrets`).

## Ротация секретов

| Тип секрета | Частота ротации | Кто ротирует |
|---|---|---|
| Пароли БД | Каждые 90 дней (автоматически, Vault Dynamic Secrets) | Vault автоматически |
| API-ключи провайдеров | По требованию провайдера или при подозрении на утечку | Integrations Team |
| Internal JWT ключ | Раз в год | Platform Engineering |
| SSL-сертификаты | Каждые 90 дней (Let's Encrypt автоматически) | Автоматически |
| Ключи шифрования PAN | Раз в год, с key rotation (старые ключи остаются для расшифровки исторических данных) | Security + DBA совместно |

## Что делать если секрет утёк

1. Немедленно напиши в **#security** с описанием: какой секрет, где был обнаружен, возможный период компрометации.
2. Отзови/заротируй секрет **немедленно**:
   ```bash
   vault kv delete secret/finbridge/prod/payments-core/tinkoff-adapter
   vault kv put secret/finbridge/prod/payments-core/tinkoff-adapter api_key="новый_ключ"
   ```
3. Уведомь провайдера / владельца сервиса если утёк внешний ключ.
4. Не пытайся переписать историю Git — это не уберёт ключ из системы, а только создаст путаницу.

Контакт: Игорь Савченко @igor.savchenko, телефон +7 (926) 555-98-76.
