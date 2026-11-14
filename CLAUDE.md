# Plainplan

Family insurance helper for US parents (30-45) whose family has 4-8 policies (health, dental, auto, home/renters).
Pain: nobody reads their policies; when something happens they don't know which policy applies, what to do, by when, and whom to call.
Web only (PWA ok), no login. All product copy is in English. Screens and UX (source of truth): docs/screens.md. Feature details: docs/functionality.md. Copy: docs/copy.md. Design: docs/design/*.png.

## Stack
- One FastAPI app serves everything: Jinja2 templates + HTMX + Tailwind (CDN). No React, no separate frontend, no CORS.
- SQLModel; DATABASE_URL from env (Neon Postgres in prod, sqlite:///local.db locally).
- pdfplumber (page-level chunks), rank_bm25, anthropic SDK, stripe (test mode). .ics written by hand.
- Deploy: Render web service from main. Start: uvicorn app.main:app --host 0.0.0.0 --port $PORT

## Repo layout
app/main.py, app/config.py, app/db.py, app/models.py
app/routes/{pages,policies,ask,situation,billing,calendar}.py
app/services/{pdf,search,citations,llm,routing,redflags,deadlines,ics}.py
app/templates/ (base.html, pages, partials/), app/static/ (manifest.json, icons)
tests/, samples/ (public PDFs + SOURCES.md + demo_family.json), docs/

## Hard rules
- Guest mode: httpOnly cookie hh_id (uuid4) -> Household. No accounts, no login screens, no fake "logged in" profile.
  First visit opens the demo family; "Start my own family" creates an empty household for this guest.
- Data model: Household -> Members (nickname, role) ; Policy belongs to a Member OR is shared (member_id NULL = Shared).
- One /ask endpoint with scope: household | member:{id} | policy:{id}; scope only filters which chunks BM25 searches.
- "Something happened?" is a separate flow (/situation), not the ask box.
- The LLM is called ONLY from app/services/llm.py and ONLY to: (1) extract key fields with verbatim quotes,
  (2) classify a situation into a fixed enum + emergency flag, (3) phrase answers/steps from retrieved chunks.
- Every answer/step/field carries chunk_id + verbatim quote. app/services/citations.py (pure Python, no LLM)
  checks the quote exists in that chunk after normalization (case, whitespace, quotes, dashes), and every number
  in the answer appears in a verified quote. Nothing verifies -> refusal: "Not clear from your documents" + claims phone.
- Routing (situation type -> which policy types apply) is a plain Python dict in routing.py, not an LLM call.
- Do NOT add payout or out-of-pocket calculations. Do NOT give medical advice or say where to get treatment.
- Red flags (regex in redflags.py OR LLM emergency flag) -> banner "If anyone is hurt or in danger, call 911 first."
- Privacy: delete uploaded PDFs after text extraction; mask VINs and policy numbers; members are nickname + role only.
- Disclaimer in footer of every page: "Plainplan explains your own policy documents. It is not insurance, legal,
  or medical advice and does not sell insurance. Your insurer makes the final decision on any claim."
- Demo values entered from samples/demo_family.json are labeled "Demo · entered by user". Never fake extracted data.
- SECRETS: the repo is PUBLIC. Keys only via environment variables (see .env.example). Never write a key into
  any file, test, or commit. Never commit .env.

## Key fields per policy type
- health: deductible, out_of_pocket_max, emergency_room, urgent_care, specialist_visit, not_covered, plan_year
- dental: annual_maximum, deductible, preventive_pct, basic_pct, major_pct, orthodontia, waiting_periods
- auto: policy_period, liability_limits, collision_deductible, comprehensive_deductible, medical_payments, duties_after_accident
- home: policy_period, dwelling, personal_property, deductible, water_damage, loss_of_use, duties_after_loss

## Style
- Small, readable code; the jury reads the repo. Type hints, short functions, no clever abstractions.
- Tests for citations, routing, redflags, deadlines. Run `pytest` before every commit.
- Small meaningful commits. Show `git diff` before committing.
