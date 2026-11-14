# Plainplan

Every policy your family has, in one place. Ask anything, see the exact line that answers it, and know
what to do when something happens.

**Live demo: https://206-81-28-155.sslip.io** (no sign-up: it opens straight into a demo family)

## What it does

For US parents whose family has several policies (health, dental, auto, home) from different insurers.

- **Upload a policy PDF.** Key facts (deductible, limits, orthodontia, deadlines) are pulled out, each with
  "✓ Verified · p. N" and the exact quote. Anything not in the document says "Not found — enter manually".
- **Ask a question.** "Are Ava's braces covered?" → **Covered**, 1–3 plain sentences and a word-for-word
  quote with the page. If the documents don't say, you get an honest "I couldn't find this" and the
  insurer's phone number.
- **Something happened?** Describe it in your own words ("Our car was rear-ended and Dad's neck hurts").
  You get a "call 911 first" banner when needed, which of the family's policies apply, 2–4 steps for each
  quoted from that policy, deadlines from the policy ("within 60 days") as a calendar event, and the
  claims phone.
- **Next 90 days.** Renewals, premium due dates and the dental-maximum reset, with one `.ics` file for
  your calendar.

## Why you can trust the answers

The AI does three narrow jobs. Our code checks everything it says.

| The AI (Claude) | Our code (no AI) |
|---|---|
| Pulls key fields from a document, with a quote | Finds the right pages (BM25 search over page chunks) |
| Sorts a situation into one of 9 types | **Checks every quote is word for word in the document**, and every number in the answer appears in a checked quote. If not, it asks the AI once more, saying what failed. If it still fails, the user gets an honest refusal |
| Writes the answer or steps from the given text only | Decides which policies apply to a situation (a fixed table) |
| | Shows the 911 banner (rules, plus the AI's flag as a backup) |
| | Dates, deadlines, calendar files, totals |

No quote, no answer. Plainplan never calculates payouts or what you will pay, and never gives medical
advice.

## Demo in 1 minute

1. Open the link. You are in **The Parkers** (Mom, Dad, Leo, Ava + Shared house and car).
2. Tap **Are Ava's braces covered?** → Covered, with a Delta Dental quote from page 1.
3. Tap **Are Mom's braces covered?** → Not covered (the parents have a different dental plan).
4. Tap **Is teeth whitening covered?** → honest refusal and a call button.
5. **Something happened?** → tap the first example → 911 banner, auto + Dad's health plan, quoted steps.
6. **Start my own family** → add someone → upload any text PDF policy.

## Privacy

- No accounts. A guest gets an httpOnly cookie that points to their household.
- Family members are a nickname and a role only.
- The PDF is deleted right after its text is read. Policy numbers, VINs and license numbers are masked
  to the last 4 characters **before** anything is stored.
- "Delete my family data" erases everything.

## Demo documents

All six policy texts in the demo are real public documents (CMS sample SBC, Pinellas County SBC,
two Delta Dental plans, ISO Homeowners 3, an AAA sample auto policy). Sources: [samples/SOURCES.md](samples/SOURCES.md).
Family names, dates, premiums and 555 phone numbers are made up and marked "Demo" in the app.

## Stack

Python 3.12 · FastAPI · Jinja2 + HTMX (no separate frontend) · SQLModel + SQLite · pdfplumber ·
rank-bm25 · Anthropic SDK · Docker + Caddy. 103 automated tests; tests never call the real AI.

```
app/
  main.py             app, guest-cookie middleware, demo seeding
  routes/             pages, policies (upload, fields), ask, situation, calendar
  services/
    pdf.py            PDF -> masked page chunks
    llm.py            the only place that calls the AI
    citations.py      quote and number checks
    search.py         BM25 search
    routing.py        situation -> policies table, checklists
    redflags.py       911 banner rules
    deadlines.py      next 90 days, deadlines
    ics.py            calendar files
    ingest.py, demo.py
  templates/, static/
samples/              demo PDFs, demo_family.json, SOURCES.md
tests/
```

## Run locally

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # put your ANTHROPIC_API_KEY here; .env is git-ignored
uvicorn app.main:app --reload # http://localhost:8000
pytest
```

Without `DATABASE_URL` the app uses `sqlite:///local.db`. Tables are created on startup. On the first
start the demo documents are read once in the background (about $0.30 of AI calls) and cached.

## Deploy (own server)

```bash
git clone https://github.com/temir-ka/plainplan.git && cd plainplan
cp .env.example .env && nano .env   # ANTHROPIC_API_KEY, DOMAIN, BASE_URL=https://<DOMAIN>
docker compose up -d --build        # https://<DOMAIN>
```

- The SQLite file lives in the Docker volume `plainplan-data`, so it survives rebuilds.
- The `caddy` service gets a free Let's Encrypt certificate for `DOMAIN`, e.g. `1-2-3-4.sslip.io`, which
  points to IP 1.2.3.4 with no DNS setup. Ports 80 and 443 must be open; the app port is bound to localhost.
- Update: `git pull && docker compose up -d --build`.
- All secrets come from environment variables. Never commit `.env`.

---

Plainplan explains your own policy documents. It is not insurance, legal, or medical advice and does not
sell insurance. Your insurer makes the final decision on any claim.
