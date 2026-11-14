# Plainplan functionality (scope)

## Updates that override the text below (14 Nov, 20:15)
- Guest identity is an httpOnly cookie `hh_id`, not localStorage or a header.
- Single FastAPI app with Jinja + HTMX + Tailwind; no React, no Vercel.
- Home is the family (member tiles + Shared); "Something happened?" is a big button on top. See docs/screens.md (source of truth for UX).
- No payout / out-of-pocket calculation anywhere. Item 4.5 (spent/remaining) is cut from the main path.
- Emergency card (stretch, only if all P0 is done by 08:30): free, shareable revocable link, policy numbers masked to last 4 digits.
- Free tier: 2 own policies and 3 questions/situations; paywall "Plainplan Family — $59/year", Stripe test checkout.

---
# Функционал продукта (финальный скоуп, без расчёта выплат)


14 ноября, ~20:00 Алматы. Рабочее имя **Plainplan**. Тексты интерфейса на английском.

**Одной фразой (EN):** *Every policy your family has, in one place. Ask anything, see the exact line that answers it, and never miss a renewal.*

**Пользователь:** родитель 30–45 в США, у семьи 4–8 полисов у разных страховщиков (медицина, стоматология, авто, дом/аренда).
**Боль:** полисы никто не читает; когда что-то случилось, непонятно, какой полис сработает, что делать и в какой срок.

Приоритеты: **P0** — без этого нет демо (40% оценки), **P1** — делаем, если P0 готов к 02:30, **P2** — только в roadmap.

---

## Модуль 1. Семья и кошелёк полисов

| # | Функция | Что видит пользователь | Как работает | Приоритет |
|---|---|---|---|---|
| 1.1 | Гостевой вход | Без логина, сразу в продукт | UUID семьи в localStorage, шлётся заголовком | P0 |
| 1.2 | Демо-семья | Кнопка **Try the sample family**, бейдж *Demo · real public documents* | 4 реальных публичных документа проходят тот же пайплайн, что и загрузка | P0 |
| 1.3 | Члены семьи | Карточки: ник, роль (*Parent / Child*), какие полисы покрывают | Храним только ник и роль, без ДР и ID | P0 |
| 1.4 | Загрузка полиса | Drag & drop PDF, выбор типа (*Health / Dental / Auto / Home or Renters*) и кого покрывает | pdfplumber → текст по страницам → куски с номером страницы и раздела | P0 |
| 1.5 | Карточка полиса | Страховщик, тип, срок действия, 4–6 ключевых цифр, телефон для claims, у каждой цифры значок цитаты | LLM извлекает поля с дословной цитатой, код проверяет, что цитата есть в тексте | P0 |
| 1.6 | Ручная правка и дополнение | Можно поправить поле или вписать то, чего нет в документе (дата окончания, взнос) | Поле помечено *Entered by you* | P0 |
| 1.7 | «Show in document» | Текст страницы с подсвеченной строкой | Открывает сохранённый кусок | P1 |
| 1.8 | Удалить данные | **Delete my family data** | Стирает всё по household | P0 (это 15 минут, а снимает вопрос о приватности) |

**Ключевые поля по типам:**
- Health: deductible, out-of-pocket max, ER, urgent care, specialist, что не покрыто, plan year.
- Dental: annual maximum, deductible, preventive/basic/major %, orthodontia, waiting periods.
- Auto: policy period, liability limits, collision/comprehensive deductible, medical payments, rental, roadside, claims phone.
- Home/Renters: policy period, dwelling, personal property, deductible, water damage, loss of use, claims phone.

## Модуль 2. Вопросы по полисам (с цитатой)

| # | Функция | Что видит пользователь | Как работает | Приоритет |
|---|---|---|---|---|
| 2.1 | Вопрос свободным текстом | *Ask about any policy… e.g. "Are Ava's braces covered?"* | Код определяет человека и тип полиса (ники + словарь), BM25 находит 6 кусков, LLM отвечает только по ним | P0 |
| 2.2 | Ответ со статусом | **Covered / Not covered / Not clear from your documents** + 1–3 предложения простым языком | — | P0 |
| 2.3 | Цитаты | Под ответом 1–3 цитаты: *Dental plan · page 3 · "Orthodontia: 50%, lifetime max $1,500"* | Код проверяет каждую цитату дословно и каждое число в ответе | P0 |
| 2.4 | Честный отказ | *I couldn't find this in Ava's documents. Call Delta Dental: 1-800-…* | Нет проверенной цитаты → ответа нет | P0 |
| 2.5 | Подсказки вопросов | 3 чипа под полем ввода для каждого полиса | Шаблоны по типу полиса | P1 |

## Модуль 3. «Что-то случилось» (ядро демо)

| # | Функция | Что видит пользователь | Как работает | Приоритет |
|---|---|---|---|---|
| 3.1 | Описание ситуации | *What happened? e.g. "Someone rear-ended our car and Dad's neck hurts"* | LLM относит к типу ситуации из списка | P0 |
| 3.2 | Баннер 911 | *If anyone is hurt or in danger, call 911 first.* | Регулярки красных флагов + флаг LLM | P0 |
| 3.3 | Какие полисы срабатывают | *2 of your policies apply: Auto (State Farm) · Dad's health plan (Aetna)* | **Таблица маршрутизации в коде**: car_accident → auto + health пострадавшего; water_damage → home; dental_pain → dental, затем health; theft → home + auto и т.д. | P0 |
| 3.4 | Шаги по каждому полису | 2–4 шага: кого уведомить, в какой срок, что собрать, каждый с цитатой | BM25 по шаблонным запросам («duties after an accident or loss», «notice», «proof of loss») + LLM формулирует + проверка цитат | P0 |
| 3.5 | Общий чеклист | *General checklist (not from your policy):* фото, данные второго водителя, полицейский отчёт | Шаблоны в коде по типу ситуации | P0 |
| 3.6 | Куда звонить | Телефон claims с карточки полиса, кнопка `tel:` | Из ключевых полей | P0 |
| 3.7 | Срок из полиса в календарь | *Your policy says "within 60 days" → Add deadline* | Регулярка вытаскивает срок из проверенной цитаты → .ics | P1 |
| 3.8 | Журнал случаев | *Incidents: Car accident · Nov 14 · 2 policies · 1 deadline* | Сохраняем тип, дату, полисы и сроки; текст описания не храним | P1 |

Граница: только страховые шаги. Никогда не говорим, куда идти лечиться, и не оцениваем, заплатит ли страховщик.

## Модуль 4. Сроки и деньги на страховки

| # | Функция | Что видит пользователь | Как работает | Приоритет |
|---|---|---|---|---|
| 4.1 | Лента «Next 90 days» | *Auto renews Mar 3 · Home premium due Dec 15 · Dental max resets Jan 1* | Движок сроков: даты из полисов и введённые вручную, статусы ок / скоро / просрочено | P0 |
| 4.2 | Взносы | На карточке полиса: взнос и день списания; итог *Your family pays $640/month for insurance ($7,680/year)* | Сумма по полисам | P0 |
| 4.3 | Календарь | **Add all to calendar (.ics)** | Генерация .ics | P0 |
| 4.4 | Пробелы в покрытии | *Ava has no dental plan · Home policy ends before renewal is on file* | Детерминированные правила по данным семьи | P1 |
| 4.5 | Потрачено / осталось | *Ava · Dental: $350 used of $1,500 annual max* | Пользователь записывает суммы из EOB/счёта, код вычитает из лимита из полиса. Только арифметика над его числами, пометка *Based on amounts you logged* | P1 |
| 4.6 | Email-напоминания | — | — | P2 |

## Модуль 5. Деньги (paywall)

| # | Функция | Что видит пользователь | Как работает | Приоритет |
|---|---|---|---|---|
| 5.1 | Free | Демо-семья или своя семья с 2 полисами, 3 вопроса или ситуации | Счётчики в household | P0 |
| 5.2 | Paywall | **Plainplan Family — $59/year** (или $7.99/month): unlimited policies and questions, all family members, renewal calendar, incident log | Срабатывает на 3-м полисе или 4-м вопросе | P0 |
| 5.3 | Stripe test checkout | Тестовая карта на экране: 4242 4242 4242 4242 | Checkout Session + проверка `session_id` на возврате | P0 |
| 5.4 | Сохранить семью по email | *Save your family vault* (необязательно, email собирает Stripe) | — | P2 |

## Модуль 6. Доверие и приватность (на каждом экране)

- Дисклеймер (EN): *Plainplan explains your own policy documents. It is not insurance, legal, or medical advice and does not sell insurance. Your insurer makes the final decision on any claim.*
- Экран загрузки (EN): *We read your PDF once, keep the text so we can quote it, and delete the file. Text is processed by an AI provider. Don't upload ID cards.*
- Маскируем VIN, номера полисов и личные телефоны до сохранения.
- Гостевые данные удаляются через 30 дней. Никаких рекламных пикселей.
- Ключи только на сервере. **Репо публичный, `.env` в `.gitignore` первым коммитом.**

---

## Что из этого не обёртка над ChatGPT (для Q32/Q36)

Кодом, без LLM: нарезка документов и BM25-поиск, проверка каждой цитаты и числа, отказ без цитаты, таблица «ситуация → полисы семьи», шаблоны чеклистов, движок сроков и .ics, пробелы в покрытии, трекер лимитов, состояние семьи между визитами. LLM только извлекает поля, относит ситуацию к типу и формулирует текст из найденных кусков.

## Сквозной сценарий для жюри (3 минуты)
1. **Try the sample family** → семья Parker, 4 полиса, лента сроков.
2. Вопрос *"Are Ava's braces covered?"* → ответ + цитата со страницей.
3. Вопрос, которого нет в документах → честный отказ с телефоном.
4. Ситуация *"Someone rear-ended our car and Dad's neck hurts"* → баннер 911, 2 полиса, шаги с цитатами, срок в календарь.
5. Пятый вопрос → paywall → Stripe 4242 → разблокировано.
6. Жюри загружает свой PDF → карточка с цитатами.

## Не делаем
Расчёт выплат и суммы из кармана, сравнение и покупку полисов, подачу claims за пользователя, OCR сканов и фото, логин, синхронизацию со страховщиками, пуши, нативное приложение.

---

**До дедлайна ≈ 16 часов.** Дальше: план по часам под этот скоуп. Темирлан начинает с 1.4 + 2.1–2.4 (нарезка, BM25, проверка цитат) на CMS SBC. Напарница с экранов «Семья» и «Что-то случилось» на мок-данных.
