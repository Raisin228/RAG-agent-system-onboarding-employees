# CI/CD пайплайн FinBridge

Весь CI/CD построен на **GitLab CI** и **ArgoCD**. Концепция: «ты сделал MR → CI проверил → замержили → ArgoCD автоматически задеплоил на нужное окружение». Прямого доступа к kubectl apply на прод у разработчиков нет — всё через GitOps.

## Окружения

| Окружение | URL | Назначение | Деплой |
|---|---|---|---|
| `dev` | `dev.finbridge.io` | Личные стенды разработчиков | По команде `fb-stand` |
| `staging` | `staging.finbridge.io` | Тестирование релиза командой QA | Автоматически при мерже в релизную ветку |
| `prod` | `pay.finbridge.io` | Продакшн | Вручную через ArgoCD после approval |

## Шаги пайплайна

При каждом пуше в GitLab запускается пайплайн. Статус виден в MR и в разделе **CI/CD → Pipelines**.

### Стадия 1: `lint`

```yaml
# Проверяет стиль и типичные ошибки
go: golangci-lint run ./...
js: eslint src/ --max-warnings 0
proto: buf lint api/
```

Время: ~2 минуты. Если упало — смотри `golangci-lint` конфиг в `.golangci.yml` в корне репо.

### Стадия 2: `test`

```yaml
unit:
  script: go test ./... -race -coverprofile=coverage.out
  coverage: '/coverage: \d+\.\d+%/'
  artifacts:
    reports:
      coverage_report:
        coverage_format: cobertura
        path: coverage.xml

integration:
  services:
    - postgres:16-alpine
    - redis:7.2-alpine
  script: go test ./... -tags=integration -timeout=5m
```

Минимальное покрытие: **70%** для изменённых файлов. Ниже — пайплайн красный.

Время: ~8 минут.

### Стадия 3: `security`

```yaml
sast:
  image: semgrep/semgrep
  script: semgrep --config auto --error --json --output semgrep.json .

dependency_scan:
  image: aquasec/trivy
  script: trivy fs --exit-code 1 --severity HIGH,CRITICAL .

secret_scan:
  script: gitleaks detect --source . --exit-code 1
```

Если `trivy` нашёл CRITICAL CVE — пайплайн блокируется. HIGH — предупреждение, не блокирует.

### Стадия 4: `build`

```yaml
build_image:
  script:
    - docker build -t registry.finbridge.io/finbridge/$CI_PROJECT_NAME:$CI_COMMIT_SHA .
    - docker push registry.finbridge.io/finbridge/$CI_PROJECT_NAME:$CI_COMMIT_SHA
```

Образы хранятся в GitLab Container Registry (`registry.finbridge.io`). Тег — SHA коммита. После мержа в релизную ветку дополнительно тегируется версией: `rc-26.100`.

### Стадия 5: `deploy-staging`

Запускается автоматически только при мерже в `rc/*` ветки.

ArgoCD отслеживает репозиторий конфигурации `finbridge-gitops` (gitlab.finbridge.io/finbridge/finbridge-gitops). При обновлении образа в `manifests/staging/` ArgoCD применяет изменения.

```bash
# Ручное обновление образа на staging (если автодеплой не сработал)
cd finbridge-gitops
yq eval '.spec.template.spec.containers[0].image = "registry.finbridge.io/finbridge/payments-core:rc-26.100"' \
  -i manifests/staging/payments-core/deployment.yaml
git commit -m "staging: update payments-core to rc-26.100"
git push
```

ArgoCD подхватит изменение в течение **3 минут** (polling interval).

### Стадия 6: `deploy-prod`

Продакшн деплой **не автоматический**. Процесс:

1. Релиз-менеджер объявляет деплой-окно в **#releases** (обычно вторник/четверг 10:00–12:00 МСК).
2. Релиз-менеджер открывает ArgoCD (`argocd.finbridge.io`) и нажимает **Sync** для нужного приложения.
3. За деплоем наблюдают: релиз-менеджер + дежурный инженер.
4. После деплоя — 15 минут наблюдения за метриками в Grafana (`grafana.finbridge.io/d/payments-sli`).
5. Если метрики в норме — релиз-менеджер пишет в **#releases**: `✅ Релиз 26.100 задеплоен`.

## Откат

```bash
# Через ArgoCD UI: Applications → payments-core → History → выбрать предыдущую версию → Rollback

# Через CLI (быстрее при инциденте):
argocd app rollback payments-core --revision 1  # 1 = предыдущая ревизия
```

Или через утилиту FinBridge:

```bash
fb-deploy rollback --service payments-core --env prod
```

Откат занимает ~2 минуты.

## Feature Flags

Новая функциональность выкатывается под **feature flag** через систему **LaunchDarkly** (`flags.finbridge.io`). Это позволяет развернуть код в прод без активации фичи и включать её постепенно (1% → 10% → 50% → 100%).

```go
// Пример использования в Go-коде
if ldClient.BoolVariation("payments.new_fraud_check", ldUser, false) {
    // новый код
} else {
    // старый код
}
```

Добавить новый flag — в LaunchDarkly UI или через Terraform (`finbridge-gitops/launchdarkly/`). Флаги удаляются из кода после полного раскатывания — за этим следит Platform Team.

## Доступ к ArgoCD и CI

| Инструмент | URL | Доступ |
|---|---|---|
| GitLab CI | `gitlab.finbridge.io` | Все разработчики |
| ArgoCD | `argocd.finbridge.io` | Все разработчики (read), релиз-менеджеры (sync) |
| Container Registry | `registry.finbridge.io` | Только через CI (прямой push запрещён) |
| LaunchDarkly | `flags.finbridge.io` | Все разработчики |

По вопросам CI/CD — **#platform-support** или @pavel.orlov.
