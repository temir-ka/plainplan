# План сборки Plainplan: Темирлан пишет весь код один
Версия 14 ноября, 20:15 Алматы. Заменяет `spec/build-plan.md`.
Сабмит в **11:00**, дедлайн **12:00, 15 ноября**. Сейчас до сабмита ≈ 14 ч 45 мин, из них ~3 ч сон.

## Честная оценка (как сказало бы жюри)
- Один человек, первый full-stack, 11 рабочих часов. Это реально **только для одного сквозного сценария**: Try the sample family → вопрос с цитатой → честный отказ → Something happened? → paywall. Всё остальное P1 и режется без сожаления.
- Главный риск не код, а **деплой и окружение** (Render, Neon, ключи). Поэтому деплой в первый час, а дальше пуш на прод после каждого блока.
- Второй риск: качество цитат на чужих PDF. Защита: проверка цитат кодом и честный отказ. Лучше «Not clear from your documents», чем выдуманная строка.

## Стек (зафиксирован)
Один сервис FastAPI: Jinja-шаблоны + HTMX + Tailwind (CDN) + `manifest.json` для PWA.
SQLModel поверх Postgres (Neon), локально SQLite. pdfplumber (куски по страницам), rank_bm25, Anthropic SDK (ключ только в env), stripe (test mode), `.ics` генерируем сами.
Гость: cookie `hh_id` (UUID, httpOnly) создаётся middleware при первом заходе. Логина нет.
Деплой: Render Web Service из GitHub `main`. **Возьми Starter ($7/мес) на эту ночь**: бесплатный засыпает через 15 минут и просыпается ~50 секунд, жюри решит, что сайт сломан.

## Правила на ночь
1. Деплой к 21:00, дальше каждый блок заканчивается `git push` и проверкой на проде.
2. Работаем в `main`, без веток: ты один, а Render деплоит `main`. Перед рискованной переделкой просто коммит.
3. Репо публичный. **Первый коммит: `.gitignore` с `.env`**. Ключи только в Environment на Render. На GitHub включи Settings → Code security → Push protection. Перед сабмитом: `git log -p | grep -iE "sk-ant|sk_test|sk_live|api_key="` должен быть пустым.
4. Claude Code получает задачи блоками (промпты ниже). После каждого блока смотри `git diff`, гоняй `pytest`, коммить.
5. P1 начинаем только если главный чекпоинт 02:00 пройден.

## До старта (20:15–20:30, 15 минут, без кода)
- Аккаунты: GitHub (новый **public** репо `plainplan`), Render, Neon (создать БД, скопировать connection string), Anthropic Console (API key, поставить лимит расходов $20), Stripe (test mode: secret key + создать Product «Plainplan Family» с Price $59/year, скопировать price_id).
- Скачать PDF в `samples/` (из прокси облака не качаются, у тебя должны):
  - Health: CMS Sample SBC — https://www.cms.gov/cciio/resources/forms-reports-and-other-resources/downloads/english-sample-completed-sbc-accessible-format-012825.pdf
  - Health: Aetna PPO SBC 2025 — https://aacounty.aetna.com/pdfs/PPO_Plan_SBC_2025_PlanYear_FINALIZED.pdf
  - Dental: https://www.aetna.com/fcps/assets/documents/2025AetnaDPPO.pdf (запасной: https://discover.pbc.gov/riskmanagement/Publications/2025/Solstice_Dental_Plan_Summary.pdf)
  - Auto: ISO PP 00 01 — https://appspre.scc.virginia.gov/boi/co/pc/auto/PP00010105.pdf
  - Home: ISO HO 00 03 — https://www.Maine.gov/pfr/insurance/sites/maine.gov.pfr.insurance/files/inline-files/ho00-03-05-11-homeowners3-special-form.pdf
  - Открой каждый: если это скан без текста, pdfplumber его не прочитает, бери запасной.
  - В `samples/SOURCES.md` по строке: файл, URL, «public document».
- Разложить стартовые файлы из `starter/` (CLAUDE.md, .gitignore, .env.example, requirements.txt, render.yaml, docs/functionality.md) в корень репо.

## Расписание (время Алматы)

| Время | Темирлан (весь код) | Напарница (дизайн, тексты, дек) | Чекпоинт |
|---|---|---|---|
| 20:30–21:00 | **Промпт 1**: скелет, `/health`, гостевая cookie, база, `render.yaml`. Пуш, деплой на Render, переменные окружения | Цвета, шрифт, лого-текст. Запустить опрос американцев (3 вопроса; Reddit r/Parenting, r/personalfinance, знакомые в США) | **21:00: живая ссылка `/health` = ok на Render, Neon подключён** |
| 21:00–23:00 | **Промпт 2**: загрузка PDF → куски по страницам → БД; извлечение ключевых полей с цитатами + проверка цитат кодом; тесты `test_citations.py`. Страница полиса без стиля | **22:00: 4 экрана в Figma** по `docs/screens.md` (главная-семья с кнопкой Something happened?, страница члена семьи с полисами и +, ответ с цитатой, paywall) + PNG-экспорт тебе. **22:30: JSON демо-семьи** (формат ниже). **23:00: `copy.md`** со всеми текстами интерфейса | **23:00: на проде загрузил CMS SBC → карточка полиса, у полей значок verified** |
| 23:00–00:30 | **Промпт 3**: `/ask` (BM25 → LLM → проверка цитат → статус Covered/Not covered/Not clear → отказ с телефоном). **Промпт 4**: «Try the sample family» из `samples/` + JSON напарницы через тот же пайплайн, кэш по SHA-256. Вёрстка по её PNG | Тексты для отказов, пустых состояний, дисклеймер, экран загрузки. Начать дек: структура 10 слайдов | **00:30: на проде демо-семья, вопрос «Are Ava's braces covered?» отвечает с цитатой и страницей; вопрос вне документов даёт честный отказ** |
| 00:30–02:00 | **Промпт 5**: Something happened? (классификация в enum, баннер 911 регулярками + флаг LLM, таблица маршрутизации в Python, шаги с цитатами по каждому полису, общий чеклист, кнопка `tel:`). Крупная кнопка на главной | Собрать ответы опроса, выписать 3–5 цитат. Слайды: проблема, пользователь, решение | **02:00: ГЛАВНЫЙ ЧЕКПОИНТ. Сценарий 1–4 работает на проде с телефона** |
| 02:00–02:30 | Пуш, прогон сценария на проде, список багов в `TODO.md`, ничего нового не начинать | Прогон сценария на проде с телефона, баги тебе одним списком | — |
| **02:30–06:00** | **Сон 3,5 часа.** Будильник на 06:00 | Сон до 07:00 | — |
| 06:00–07:30 | **Промпт 6**: лимиты free (2 полиса, 3 вопроса/ситуации) → paywall $59/year → Stripe Checkout test → проверка `session_id` на возврате → разблокировано. Delete my family data | (с 07:00) Слайды денег: цена, LTV/CAC, путь к $100M (цифры из `covered-deep-dive.md` с источниками) | **07:30: 4-й вопрос → paywall → карта 4242 → разблокировано, на проде** |
| 07:30–08:30 | **Промпт 7**: лента Next 90 days (даты окончания, взносы, сброс лимитов 1 января), итог взносов в месяц, `.ics`. Срок из цитаты в календарь (P1, если быстро) | Слайды: конкуренты (PolicyZen и др.), опрос, демо-скриншоты | 08:30: `.ics` открывается в Google/Apple Calendar |
| 08:30–09:30 | **Промпт 8**: полировка UI по Figma, мобильная версия, PWA manifest, дисклеймер и 911 на каждом экране, блок «For judges» на главной. README | Сценарий питча на 5 минут, репетиция | 09:30: всё выглядит как в Figma на телефоне |
| 09:30–10:00 | Багфикс. Прогнать 3 чужих PDF из интернета (любой SBC с healthcare.gov/работодателя). **Фриз кода в 10:00** | Финальный дек | **10:00: фриз** |
| 10:00–10:45 | Прогон как жюри в инкогнито (телефон + ноутбук), проверка репо на секреты, прогрев сервера | Запись резервного видео демо (2 мин), экспорт дека в PDF ≤ 10 слайдов | — |
| **10:45–11:00** | **Сабмит**: дек PDF, живая ссылка, репо. Открыть все три в инкогнито | | **11:00 сдано.** До 12:00 только пересабмит при критичном баге |

## Что режем, если отстаём (по порядку)
1. **23:00 не готово** → ключевые поля: 4 на тип вместо 6–7, остальное вводится руками с пометкой *Entered by you*.
2. **00:30 не готово** → демо-семья из 3 полисов (health, dental, auto), без дома.
3. **02:00 не готово** → шаги ситуации только для двух типов (car_accident, dental_pain), остальные типы отвечают общим чеклистом + телефоном. Не спать меньше 3 часов.
4. **07:30 не готово** → вместо Stripe честный paywall-экран с ценой и кнопкой (минимум по Q37). Stripe не чинить дольше 30 минут.
5. **Экстренная карточка** (токен, номера до последних 4 цифр, отзыв ссылки) в этом плане **уже вне основного пути**: делаем только если к 08:30 всё зелёное, на неё 45 минут. Иначе в roadmap на слайде.
6. Тоже режется первым: журнал случаев, пробелы в покрытии, трекер «потрачено/осталось», «Show in document».
7. **Никогда не режем:** загрузку своего PDF, проверку цитат, честный отказ, баннер 911, дисклеймер, гостевой вход без логина.

## Что напарница отдаёт и в каком виде
- **22:00** PNG четырёх экранов (мобильная ширина 390px) + палитра HEX + шрифт из Google Fonts. Ты кладёшь PNG в `docs/design/` и говоришь Claude Code: «match docs/design/home.png».
- **22:30** `samples/demo_family.json`:
```json
{
  "household": "The Parkers",
  "members": [{"nickname": "Mom", "role": "parent"}, {"nickname": "Dad", "role": "parent"},
              {"nickname": "Leo", "role": "child"}, {"nickname": "Ava", "role": "child"}],
  "policies": [
    {"file": "aetna_ppo_sbc_2025.pdf", "type": "health", "insurer": "Aetna",
     "covers": ["Dad", "Leo", "Ava"], "period_start": "2026-01-01", "period_end": "2026-12-31",
     "premium_monthly": 410, "premium_due_day": 1, "claims_phone": "1-800-555-0100"}
  ]
}
```
  Даты, взносы и телефоны в демо вводятся «как пользователь» и в интерфейсе помечаются *Demo · entered by user*. Телефоны только вымышленные 555-01xx. Тексты полисов настоящие публичные документы.
- **23:00** `docs/copy.md`: все английские тексты по экранам (кнопки, заголовки, пустые состояния, отказ, paywall, дисклеймер).
- Опрос, дек, питч, видео: её зона, ты туда не лезешь.

---

## Структура репо
```
plainplan/
  CLAUDE.md               # правила для Claude Code
  README.md
  .gitignore              # .env, __pycache__, *.db, .venv
  .env.example            # имена переменных без значений
  requirements.txt
  render.yaml
  docs/
    functionality.md      # скоуп
    copy.md               # тексты от напарницы
    design/*.png          # экраны из Figma
  samples/                # публичные PDF + SOURCES.md + demo_family.json
  app/
    main.py               # FastAPI app, middleware гостя, подключение роутов
    config.py             # чтение env
    db.py, models.py      # SQLModel: Household, Member, Policy, Chunk, Field, Incident
    routes/               # pages.py, policies.py, ask.py, situation.py, billing.py, calendar.py
    services/
      pdf.py              # pdfplumber → куски {page, section, text}
      search.py           # BM25 по кускам семьи
      citations.py        # проверка цитат и чисел (без LLM)
      llm.py              # единственное место, где вызывается Anthropic
      routing.py          # таблица ситуация → типы полисов
      redflags.py         # регулярки 911
      deadlines.py, ics.py
    templates/            # base.html, home.html, family.html, policy.html, paywall.html, partials/*.html
    static/               # manifest.json, icon-192.png, icon-512.png
  tests/                  # test_citations.py, test_routing.py, test_redflags.py, test_deadlines.py
```

## Как работает проверка цитат (объяснить жюри и Claude Code одинаково)
1. LLM получает только найденные BM25 куски с их `chunk_id` и возвращает JSON: `status`, `answer`, `citations: [{chunk_id, quote}]`.
2. Код нормализует текст (регистр, пробелы, кавычки, тире) и проверяет, что `quote` дословно есть в куске `chunk_id`. Нет → цитата выброшена.
3. Каждое число в `answer` ($, %, цифры) должно встречаться в одной из оставшихся цитат. Нет → ответ заменяется на отказ.
4. Ни одной проверенной цитаты → *Not clear from your documents* + телефон страховщика.
Это и есть ответ на «это обёртка над ChatGPT?»: LLM только формулирует, решает код.

---

## Промпты для Claude Code (вставлять по одному)

**Промпт 1 (20:30)**
```
Read CLAUDE.md, docs/screens.md and docs/functionality.md. Create the project skeleton from the "Repo layout" in CLAUDE.md:
FastAPI app serving Jinja templates, base.html with Tailwind CDN and HTMX CDN, a placeholder home page,
GET /health returning {"ok": true}. Add middleware that sets an httpOnly cookie hh_id (uuid4) if missing
and creates a Household row. Models: Household, Member (nickname, role), Policy (member_id nullable = Shared),
Chunk, Field. SQLModel with DATABASE_URL from env (fallback sqlite:///local.db),
create tables on startup. Add render.yaml, requirements.txt, .env.example (names only), README with
run instructions. Add tests/test_health.py. Run pytest and the server locally, then show me git status.
Do not put any secrets in files.
```

**Промпт 2 (21:00)**
```
Implement the family structure and policy upload (see docs/screens.md). Home shows member tiles + a Shared tile.
/start creates an empty household where the guest adds members (nickname + role). Member page and Shared page list
policy cards and a "+ Add policy" card that uploads a PDF with type (health|dental|auto|home) attached to that member
or to Shared. services/pdf.py: extract text per page with
pdfplumber, split into chunks (~800 chars, keep page number and nearest heading as section), store
Chunk rows, delete the file after extraction, mask VIN-like and long policy numbers before storing.
If a PDF has no extractable text, show a clear error ("This looks like a scan; please upload a text PDF").
services/llm.py: extract key fields for the policy type (see CLAUDE.md) as JSON with a verbatim quote
and chunk_id per field. services/citations.py: verify each quote exists in its chunk after normalization;
unverified fields are shown as "Not found — enter manually". Policy page shows fields with a verified badge,
lets the user edit a field (marks it entered_by_user). Write tests/test_citations.py with real snippets
from samples/cms_sample_sbc.pdf. Keep templates plain for now.
```

**Промпт 3 (23:00)**
```
Implement /ask with HTMX and a scope parameter: household | member:{id} | policy:{id}. Put the ask box on home
("Ask about your family's policies"), member pages ("Ask about {nickname}'s policies") and policy pages
("Ask about this policy"). services/search.py: BM25 (rank_bm25) over the chunks allowed by the scope; in household
scope also narrow by member nickname and policy type keywords found in the question; take top 6.
llm.py: answer only from those chunks, return JSON {status: covered|not_covered|unclear, answer, citations}.
citations.py: drop unverified quotes; every number in the answer must appear in a verified quote;
if nothing verifies, return the refusal with the insurer's claims phone. Render partials/answer.html
(status pill, 1-3 sentences, quotes with policy name and page). Add tests for the refusal path and
the number check. Match docs/design/answer.png.
```

**Промпт 4 (23:45)**
```
The first visit opens the demo family (no extra click); keep a "Try the sample family" button on /start too.
The header shows "The Parkers · Demo" and "Start my own family". It creates a demo household from samples/demo_family.json
and runs each PDF through the same upload pipeline. Cache extracted chunks and fields by file SHA-256
in the DB so the demo loads in under 3 seconds after the first run. Demo values that come from the JSON
are marked "Demo · entered by user". Show a "Demo · real public documents" badge.
```

**Промпт 5 (00:30)**
```
Build "Something happened?" (/situation), opened by the big button at the top of home (see docs/screens.md). Text input -> llm.py classifies
into a fixed enum: car_accident, dental_pain, injury_or_illness, water_damage, theft, other, plus
an emergency flag. services/redflags.py: regex red flags (bleeding, unconscious, can't breathe, chest pain,
fire, etc.); if regex or LLM flag -> red banner "If anyone is hurt or in danger, call 911 first." on top.
services/routing.py: a plain Python dict from situation type to policy types (car_accident -> shared auto +
health of the injured member; detect the member by nickname, and if someone is hurt but no member is named, return
a "Who was hurt?" partial with member buttons; dental_pain -> dental, then health; water_damage -> home; theft -> home + auto).
For each applicable family policy, run BM25 with template queries ("duties after an accident or loss",
"notice of claim", "proof of loss", "emergency dental") and ask the LLM for 2-4 steps, each with a citation;
verify citations; drop steps that don't verify. Add a templated "General checklist (not from your policy)"
per situation and a tel: button with the claims phone. Never give medical advice.
Tests: test_routing.py, test_redflags.py.
```

**Промпт 6 (06:00)**
```
Add free limits on Household (2 own policies, 3 questions or situations total; the sample family counts
toward questions). When exceeded, show paywall.html: "Plainplan Family — $59/year" with features.
Stripe Checkout in test mode (STRIPE_SECRET_KEY, STRIPE_PRICE_ID from env), success_url with
{CHECKOUT_SESSION_ID}; on return retrieve the session server-side, check payment_status == "paid",
then set household.plan = "family". Show test card 4242 4242 4242 4242 on the paywall. Add
"Delete my family data" that removes all rows for the household and clears the cookie.
```

**Промпт 7 (07:30)**
```
Add the "Next 90 days" feed on /family: policy end dates, premium due dates, Jan 1 dental max reset,
with ok/soon/overdue status; total premiums per month and per year. GET /calendar.ics exports all of
them (write the .ics by hand, no extra library). If a verified quote in a situation step contains a
deadline like "within 60 days", add an "Add deadline" link that downloads a single-event .ics.
If time allows (P1): spent/remaining tracker per member and policy: the user logs amounts from EOBs/bills,
code subtracts from the verified annual limit, labeled "Based on amounts you logged". No payout estimates.
Tests: test_deadlines.py.
```

**Промпт 8 (08:30)**
```
Polish the UI to match docs/design/*.png and docs/copy.md: palette, font, spacing, mobile first at 390px.
Add static/manifest.json and icons for PWA. Footer on every page with the disclaimer from CLAUDE.md.
Home page block "For judges": "1. Tap Try a sample family. 2. Ask anything or tap Something happened?
3. Or upload your own policy PDF, it works the same." plus test card 4242 4242 4242 4242.
"Demo data" label: names and dates are made up, the policies are real public documents (link each source).
Under each answer "Verified quote, p. N" that opens the stored page text with the line highlighted.
"How it works" block: AI reads your policy -> our code checks every quote -> no quote, no answer. Update README (what it is, stack, how to run, data sources,
what is LLM vs code). Run all tests.
```

## Время
До сабмита (11:00) ≈ 14 ч 45 мин, до дедлайна ≈ 15 ч 45 мин.
**Сейчас:** аккаунты и PDF (15 минут), затем Промпт 1 и деплой до 21:00. Напарнице: палитра и опрос сейчас, 4 экрана к 22:00.
