# Шаблон самооценки для грейд-ревью

> Этот документ заполняется сотрудником перед подачей заявки на повышение грейда. После заполнения отправь ссылку своему тимлиду и в **#hr-requests** с пометкой «Заявка на грейд-ревью». Шаблон хранится в Confluence: `confluence.finbridge.io/display/HR/grade-review-template`.

## Общая информация

| Поле | Значение |
|---|---|
| ФИО | <span style="color:red">Иванов Иван Иванович</span> |
| Текущий грейд | <span style="color:red">G3 (Middle)</span> |
| Целевой грейд | <span style="color:red">G4 (Middle+)</span> |
| Направление | <span style="color:red">Backend-разработка (Go)</span> |
| Команда | <span style="color:red">Payments Core</span> |
| Тимлид | <span style="color:red">Алексей Морозов (@alexey.morozov)</span> |
| Дата выхода в компанию | <span style="color:red">12.03.2024</span> |
| Дата последнего повышения грейда | <span style="color:red">01.10.2024 (G2 → G3)</span> |
| Дата заполнения | <span style="color:red">08.04.2026</span> |

## 1. Завершённые задачи за период

Перечисли ключевые задачи, которые ты выполнил с момента последнего повышения. Укажи ссылки на Jira-тикеты и MR в GitLab.

| № | Задача (Jira) | Описание | Сложность | MR |
|---|---|---|---|---|
| 1 | <span style="color:red">PAY-1234567</span> | <span style="color:red">Реализовал новый endpoint для массовых выплат мерчантам с поддержкой идемпотентности</span> | <span style="color:red">XL</span> | <span style="color:red">!4521</span> |
| 2 | <span style="color:red">PAY-1234890</span> | <span style="color:red">Оптимизировал SQL-запросы в сервисе аналитики, ускорение отчётов с 12с до 1.8с</span> | <span style="color:red">L</span> | <span style="color:red">!4603</span> |
| 3 | <span style="color:red">PAY-1235100</span> | <span style="color:red">Интегрировал новый платёжный шлюз (MirPay) в процессинг</span> | <span style="color:red">XL</span> | <span style="color:red">!4712, !4715</span> |
| 4 | <span style="color:red">...</span> | <span style="color:red">...</span> | <span style="color:red">...</span> | <span style="color:red">...</span> |

Сложность задач: **S** (до 2 часов), **M** (до 1 дня), **L** (до 1 недели), **XL** (больше недели).

## 2. Архитектурные решения и RFC

Перечисли RFC или архитектурные решения, в которых ты участвовал как автор или ключевой ревьюер.

| RFC / решение | Роль | Ссылка на Confluence |
|---|---|---|
| <span style="color:red">RFC-042: Миграция процессинга на event-driven архитектуру</span> | <span style="color:red">Автор</span> | <span style="color:red">confluence.finbridge.io/display/ENG/RFC-042</span> |
| <span style="color:red">RFC-039: Переход на gRPC между внутренними сервисами</span> | <span style="color:red">Ревьюер</span> | <span style="color:red">confluence.finbridge.io/display/ENG/RFC-039</span> |
| <span style="color:red">...</span> | <span style="color:red">...</span> | <span style="color:red">...</span> |

Если RFC не писал — укажи «Нет» и опиши в свободной форме, какие технические решения принимал самостоятельно.

## 3. Код-ревью и менторство

| Метрика | Значение |
|---|---|
| Проведено код-ревью (MR) за период | <span style="color:red">87</span> |
| Менторил сотрудников (перечисли) | <span style="color:red">Дарья Кузнецова (G1, Backend), Олег Фёдоров (G1, Backend)</span> |
| Участие в онбординге новичков (да/нет, кого) | <span style="color:red">Да — был buddy для Олега Фёдорова (март 2026)</span> |

## 4. Выступления и публикации

| Событие | Дата | Тема | Формат |
|---|---|---|---|
| <span style="color:red">FinBridge Tech Talks #14</span> | <span style="color:red">15.02.2026</span> | <span style="color:red">«Как мы снизили latency процессинга на 40%»</span> | <span style="color:red">Внутренний доклад</span> |
| <span style="color:red">HighLoad++ 2025</span> | <span style="color:red">21.11.2025</span> | <span style="color:red">Слушатель (3 секции по процессингу)</span> | <span style="color:red">Конференция</span> |
| <span style="color:red">...</span> | <span style="color:red">...</span> | <span style="color:red">...</span> | <span style="color:red">...</span> |

Если выступлений не было — укажи «Нет» и опиши, какие обучающие активности проходил (курсы, сертификации).

## 5. Обратная связь от коллег

Необходимо минимум **3 отзыва**: один от коллеги из своей команды, один от коллеги из смежной команды, один от тимлида или senior+. Попроси коллег написать 3–5 предложений о твоей работе и вставь сюда.

| Кто | Грейд | Команда | Отзыв |
|---|---|---|---|
| <span style="color:red">Анна Волкова</span> | <span style="color:red">G5</span> | <span style="color:red">Payments Core</span> | <span style="color:red">«Иван за последние полгода вырос в самостоятельности — берёт XL-задачи и доводит до прода без напоминаний. Код-ревью делает качественно, всегда с конструктивными комментариями. Готов к G4.»</span> |
| <span style="color:red">Пётр Сидоров</span> | <span style="color:red">G4</span> | <span style="color:red">Merchant Portal</span> | <span style="color:red">«Работали вместе над интеграцией MirPay. Иван взял на себя backend-часть и сам предложил архитектуру. Общение конструктивное, сроки соблюдал.»</span> |
| <span style="color:red">Алексей Морозов</span> | <span style="color:red">G6</span> | <span style="color:red">Payments Core (TL)</span> | <span style="color:red">«Рекомендую к повышению. Иван стабильно перформит на уровне G4, менторит джунов, участвует в архитектурных обсуждениях.»</span> |

## 6. Зоны роста

Опиши честно, в чём ты видишь свои слабые стороны и что планируешь улучшить в ближайшие 6 месяцев.

<span style="color:red">1. Хочу прокачать навыки проектирования распределённых систем — планирую пройти курс «Designing Data-Intensive Applications» на корпоративном O'Reilly.</span>

<span style="color:red">2. Пока не выступал на внешних конференциях — цель: подать доклад на HighLoad++ 2026.</span>

<span style="color:red">3. Нужно улучшить навыки написания RFC — текущие документы слишком короткие, не хватает анализа альтернатив.</span>

---

**После заполнения:**
1. Сохрани документ в Confluence в пространстве `HR / Grade Reviews / 2026-Q2`.
2. Отправь ссылку тимлиду в личном сообщении Slack.
3. Напиши в **#hr-requests**: «Подал заявку на грейд-ревью G3 → G4, ссылка: <ссылка>».
4. Тимлид назначит встречу для обсуждения в течение 5 рабочих дней.
