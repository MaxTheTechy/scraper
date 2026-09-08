# Handoff — 2026-09-08

Snapshot of where the recipe scraper platform stands at the end of this
session, and what's queued up for next time. Read alongside
["Recipe Scraper Platform — Project.md"](Recipe%20Scraper%20Platform%20%E2%80%94%20Project.md)
(the original design spec) and [README.md](README.md) (how to run things).

## State as of this session

Built and verified live on this host (`recipe-dev-01`, LXC 131), end-to-end
through the real production path (API → Redis → Celery worker → Postgres →
Nginx), not just direct function calls:

- **Backend** (`api/`): FastAPI app, SQLAlchemy models, Alembic migrations
  applied, routers for sites/recipes/ingredients/scrape.
- **Scraper** (`scraper/`): Celery worker + a working site adapter for
  `retete.unica.ro` (the demo target) — sitemap-based URL discovery, HTML
  parsing for title/ingredients/steps/times/image. Reusable JSON-LD parser
  and Playwright renderer are in place for future sites but not wired to
  any live site yet.
- **Frontend** (`ui/`): React (Vite) management UI — Sites, Scrape Queue,
  Recipe Review panels. Builds clean to `ui/dist/`.
- **Infra**: Postgres 15 (cluster relocated to `/data/postgres`), Redis,
  Nginx, all four services running under systemd (`deploy/systemd/`,
  installed to `/etc/systemd/system/`). Nginx serves the UI at `/`, proxies
  `/api/` to FastAPI, serves `/images/` from `/data/images/`.
- **Data**: DB has 1 site (`retete.unica.ro`, id=3) and 10 real scraped
  recipes with ingredients and downloaded images.
- **Git**: pushed to `main` on `git@github.com:MaxTheTechy/scraper.git`.
  Latest commit at time of writing: `3e3ec9d`.

Everything was built by three parallel agents (backend, scraper, frontend)
plus foundational infra/DB work done directly — see prior session transcript
for the detailed build log if needed.

## Known quirks (not bugs — just worth knowing)

- `systemctl is-active postgresql` reports `inactive` — that's expected on
  Debian; it's a oneshot wrapper. The real unit is
  `postgresql@15-main.service` (check that one, or use `pg_lsclusters`).
- `/data` is **not** a dedicated mounted disk — it's a plain directory on
  the container's root filesystem (49G total, currently ~42G free). The
  spec's 100GB RAID6 disk was never attached to LXC 131. Reattaching it
  later from the Proxmox host needs no code changes, just a remount.
- `recipe-beat.service` is installed but **not enabled/started** — there's
  no periodic schedule defined in `scraper/worker.py` yet, so it would have
  nothing to do.

## Known gaps / deliberately left undone

These were flagged rather than silently worked around or fabricated:

1. **No auth** — deferred per spec Section 10 (production migration step).
2. **Sites panel is add/list/scrape only** — no `PATCH`/`DELETE /sites/{id}`,
   so no enable/disable/remove from the UI yet, despite spec Section 7
   listing it.
3. **Recipe/ingredient edits in the review UI don't persist** — `PATCH
   /recipes/{id}/status` only changes `status` (approve/reject). Editing
   title/description/tags/ingredients before approving is local-state only
   in the UI right now (marked with TODOs in the component code) — there's
   no backend endpoint to save content edits.
4. **Scrape batch size is hardcoded** — `POST /sites/{id}/scrape` always
   requests the default `limit=10` (in `scraper/worker.py`); there's no way
   to override it from the API/UI yet.
5. **Only one site scraper exists** (`retete.unica.ro`). The JSON-LD parser
   and Playwright renderer are real and tested standalone, but no second
   site has been wired up to prove the multi-site path end-to-end.

## Suggested next-session plan, roughly in priority order

1. **Close the editing loop** (addresses gaps #2 and #3, the biggest UX
   hole): add `PATCH /sites/{id}` (enable/disable, maybe rename) and `PATCH
   /recipes/{id}` (content edit: title/description/tags/method) +
   `PATCH/DELETE /recipes/{id}/ingredients/{id}` or a bulk replace-ingredients
   endpoint. Wire the existing UI TODOs up to these once they exist —
   the frontend already has the local-state editing UI built, it just needs
   real endpoints to call.
2. **Expose `limit` on the scrape trigger** (gap #4): add an optional query
   param to `POST /sites/{id}/scrape` (e.g. `?limit=25`), thread it through
   to `celery_app.send_task(..., args=[site_id, limit])`, add a number input
   next to the "Scrape now" button in `SitesPanel.tsx`.
3. **Prove the multi-site path**: add a second site scraper (pick one with
   real schema.org Recipe JSON-LD, to actually exercise
   `scraper/json_ld_parser.py`, which is currently correct-but-unused in
   production). Confirms `scraper/sites/__init__.py`'s registry pattern
   holds up for more than one adapter.
4. **Reattach the real `/data` disk** from the Proxmox host (the 100GB
   RAID6 volume per spec Section 1), then migrate/verify `/data/postgres`
   and `/data/images` still work after the remount — do this before data
   volume grows large enough that root-fs space becomes a real constraint
   (currently 42G free, fine for now).
5. **`recipe-beat` periodic scraping**: once you're comfortable with manual
   trigger behavior, define a Celery beat schedule (e.g. daily per enabled
   site) and enable the service.
6. **Production hardening** (spec Section 10, no urgency yet): SSL via
   certbot, API auth (API keys or OAuth2), scheduled `pg_dump` backups,
   optionally migrate images to MinIO/S3.

## Quick orientation commands for next session

```bash
systemctl status recipe-api recipe-worker nginx postgresql@15-main redis-server
curl -s http://localhost/api/health
su postgres -c "psql -d recipe_platform -c 'SELECT id, title, status FROM recipes;'"
cd /opt/scraper && git log --oneline -5
```
