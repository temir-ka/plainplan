# Plainplan

Every policy your family has, in one place. Ask anything, see the exact line that answers it, and never miss a renewal.

One FastAPI app serves HTML pages (Jinja2 + HTMX, own CSS/JS). No login: a guest gets an httpOnly cookie `hh_id`
that points to their household.

## Run locally

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # fill in keys locally; .env is git-ignored
uvicorn app.main:app --reload # http://localhost:8000
```

Without `DATABASE_URL` the app uses `sqlite:///local.db`. Tables are created on startup.

## Tests

```bash
pytest
```

## Run with Docker

```bash
docker build -t plainplan .
docker run --rm -p 8000:8000 --env-file .env plainplan
```

## Deploy (own server)

```bash
git clone <repo> plainplan && cd plainplan
cp .env.example .env && nano .env   # real keys, server only
docker compose up -d --build        # https://<DOMAIN>
```

The SQLite file lives in the Docker volume `plainplan-data`, so it survives rebuilds.
HTTPS: the `caddy` service gets a free Let's Encrypt certificate for `DOMAIN` (e.g. `1-2-3-4.sslip.io`,
which points to IP 1.2.3.4 with no DNS setup). Ports 80 and 443 must be open; the app port is bound to localhost.
Update: `git pull && docker compose up -d --build`.
All secrets come from environment variables. Never commit `.env`.

Plainplan explains your own policy documents. It is not insurance, legal, or medical advice and does not sell
insurance. Your insurer makes the final decision on any claim.
