# Запросы на доступ в FinBridge

Управление доступами централизовано через **Okta** (Identity Provider). Большинство систем защищено SSO через Okta — достаточно одного логина.

## Стандартные доступы (выдаются автоматически при найме)

Перед первым рабочим днём IT-отдел создаёт учётные записи:

| Система | URL | Как войти |
|---|---|---|
| Okta (SSO) | `finbridge.okta.com` | Логин + пароль из письма + 2FA |
| GitLab | `gitlab.finbridge.io` | SSO через Okta |
| Jira | `jira.finbridge.io` | SSO через Okta |
| Confluence | `confluence.finbridge.io` | SSO через Okta |
| Slack | `finbridge.slack.com` | SSO через Okta |
| Grafana | `grafana.finbridge.io` | SSO через Okta |
| Kibana | `kibana.finbridge.io` | SSO через Okta |

Логин везде: `имя.фамилия@finbridge.io`. Пароль для Okta приходит на личную почту до первого рабочего дня.

## Настройка Okta и 2FA

**Первый вход в Okta — в первый рабочий день, до всего остального.**

1. Открой `finbridge.okta.com`.
2. Введи логин (`имя.фамилия@finbridge.io`) и временный пароль из письма.
3. Тебя попросят сменить пароль (минимум 14 символов, буквы+цифры+спецсимволы).
4. Настрой 2FA — обязательно:
   - Установи **Okta Verify** на телефон (App Store / Google Play).
   - Или используй **Google Authenticator** / **Authy** — при выборе «Setup» → «Use a different authenticator app».
   - Отсканируй QR-код.
5. Всё — теперь все SSO-сервисы доступны через Okta.

## Запрос дополнительных доступов

Часть систем доступна не всем по умолчанию — только по производственной необходимости.

### Через #it-support (быстрые запросы, < 1 рабочего дня)

Написать в Slack-канал **#it-support**:

```
Прошу выдать доступ к [система] для [имя.фамилия].
Обоснование: [1–2 предложения зачем нужен].
Согласовано с тимлидом: @имя_тимлида
```

Примеры систем через #it-support:
- ArgoCD (`argocd.finbridge.io`) — для деплоев
- Vault (`vault.finbridge.io`) — для работы с секретами
- Prometheus (`prometheus.finbridge.io`)
- LaunchDarkly (`flags.finbridge.io`)
- Smartway (командировки)

### Через Jira (доступы с повышенными правами, 1 рабочий день)

Создай тикет в Jira: проект **SEC**, тип задачи **«Запрос доступа»**.

Используется для:
- Read-only доступ к продакшн-базам данных
- Доступ к платёжным данным (PCI DSS scope)
- AWS Console (production account)
- Vault namespace для production secrets

Тикет должен содержать:
- Конкретная система и уровень доступа (read-only, read-write, admin)
- Срок необходимости (временный или постоянный)
- Согласование от тимлида (упомянуть в тикете)

Security-команда рассматривает тикет в течение 1 рабочего дня.

## Доступ к production БД

Прямого доступа к production PostgreSQL у разработчиков нет — только у DBA-команды и on-call инженеров во время инцидентов.

Если нужно посмотреть прод-данные для дебага:

1. Создай тикет в Jira (проект SEC, тип «Запрос доступа»).
2. Укажи: какая БД, какие таблицы, зачем, на какой срок.
3. DBA выдаёт временный read-only DSN с истечением через 8 часов.
4. Подключение только через VPN и через бастион-хост (`bastion.finbridge.io`).

```bash
# Подключение к prod через бастион
ssh -J имя.фамилия@bastion.finbridge.io postgres-primary-prod.internal

# Или через SSH-туннель (если есть TablePlus/DataGrip)
ssh -L 5433:postgres-primary-prod.internal:5432 имя.фамилия@bastion.finbridge.io -N
# Затем подключиться к localhost:5433
```

## VPN-сертификаты

VPN-сертификаты выдаются автоматически при создании учётной записи. Срок действия — 1 год. За 30 дней до истечения придёт уведомление на корпоративную почту.

Продление:
```bash
fb-security-check --renew-vpn-cert
# Или вручную через #it-support
```

Инструкция по настройке VPN — в документе `vpn_setup.md`.

## Матрица доступов по ролям

| Система | Junior | Middle | Senior | Lead |
|---|---|---|---|---|
| GitLab (read/write) | ✅ | ✅ | ✅ | ✅ |
| ArgoCD (staging sync) | ❌ | ✅ | ✅ | ✅ |
| ArgoCD (prod sync) | ❌ | ❌ | По запросу | ✅ |
| Vault (staging secrets) | ❌ | ✅ | ✅ | ✅ |
| Vault (prod secrets read) | ❌ | ❌ | По запросу | ✅ |
| Prod DB (read-only, временно) | ❌ | По тикету | По тикету | По тикету |
| AWS Console (prod) | ❌ | ❌ | По тикету + YubiKey | По тикету + YubiKey |
| LaunchDarkly | ❌ | ✅ | ✅ | ✅ |

По вопросам доступов — **#it-support** (IT-отдел) или **#security** (Security-команда).
