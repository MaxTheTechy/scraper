# scraper

Self-hosted recipe scraper platform: Playwright/BeautifulSoup scraper → FastAPI →
PostgreSQL, with a React management UI. Runs natively on Debian 12 (no Docker),
each component as its own systemd service. Full design doc:
["Recipe Scraper Platform — Project.md"](Recipe%20Scraper%20Platform%20%E2%80%94%20Project.md).

Demo scrape target: [retete.unica.ro/recipes](https://retete.unica.ro/recipes/).

## Layout

```
api/            FastAPI app, SQLAlchemy models, routers, schemas
scraper/        Celery worker, per-site scrapers (scraper/sites/), JSON-LD & Playwright helpers
migrations/     Alembic
ui/             React (Vite) management UI, built to ui/dist/
deploy/         systemd unit files + Nginx site config
```

## Environment

- App root: `/opt/scraper` (this repo). Python venv at `venv/`, Node/npm system-wide.
- Data dir: `/data` (Postgres cluster at `/data/postgres`, scraped images at
  `/data/images`) — currently on the container's root filesystem, **not** yet
  a dedicated mounted disk. Reattaching a real disk at `/data` later needs no
  code changes.
- Config: `.env` (gitignored, real secrets) — copy `.env.example` and fill in
  `DATABASE_URL` to set up a new environment.
- Service user: `recipe` (system account, nologin) — owns `api/`, `scraper/`,
  `migrations/`, and `/data/images`.

## Running

Services are managed by systemd (`deploy/systemd/*.service`, installed to
`/etc/systemd/system/`):

```
recipe-api.service       # FastAPI on 127.0.0.1:8000
recipe-worker.service    # Celery worker (scrape jobs)
recipe-beat.service      # Celery beat — installed but not enabled; no periodic
                          # schedule defined yet
```

Nginx (`deploy/nginx/recipe-platform.conf`) serves `ui/dist/` at `/`, proxies
`/api/` to the FastAPI app, and serves `/images/` from `/data/images/`.

```bash
systemctl status recipe-api recipe-worker nginx postgresql redis-server
```

## Database

```bash
source venv/bin/activate
alembic upgrade head              # apply migrations
alembic revision --autogenerate -m "..."   # after changing api/models/
```

## Scraper

Add a site and trigger a scrape via the API (or the Sites panel in the UI):

```bash
curl -X POST http://localhost/api/sites -d '{"url": "...", "name": "..."}' -H 'Content-Type: application/json'
curl -X POST http://localhost/api/sites/<id>/scrape
```

`scraper/sites/` holds one module per site (URL-discovery + HTML-parsing
rules). `scraper/json_ld_parser.py` handles schema.org `Recipe` JSON-LD for
sites that expose it (retete.unica.ro doesn't — it's parsed via HTML rules in
`scraper/sites/unica.py` instead). `scraper/playwright_scraper.py` is the
fallback renderer for JS-rendered sites.

Politeness: rate limit and User-Agent are set in `.env`
(`SCRAPE_RATE_LIMIT_MIN/MAX_SECONDS`, `SCRAPE_USER_AGENT`); each `scrape_site`
run is capped (`limit`, default 10) rather than scraping a whole site at once.

## Frontend dev

```bash
cd ui
npm install
npm run dev      # proxies /api to 127.0.0.1:8000, matching Nginx's prod behavior
npm run build     # outputs ui/dist/, served by Nginx
```

See [.claude/skills/frontend-ui/SKILL.md](.claude/skills/frontend-ui/SKILL.md)
for frontend conventions.

## Known gaps

- No auth (deferred to production migration, see spec Section 10).
- Sites panel can only add/list/trigger-scrape — no enable/disable/remove
  endpoint yet.
- Recipe/ingredient edits in the review UI are local-state only pending a
  content-PATCH endpoint (`PATCH /recipes/{id}/status` only changes status).
- `/data` is not yet a dedicated mounted disk on this container.
