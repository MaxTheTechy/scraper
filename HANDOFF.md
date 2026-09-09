# Handoff — 2026-09-09

Snapshot of where the recipe scraper platform stands at the end of this
session, and what's queued up for next time. Read alongside
["Recipe Scraper Platform — Project.md"](Recipe%20Scraper%20Platform%20%E2%80%94%20Project.md)
(the original design spec) and [README.md](README.md) (how to run things).
Supersedes the prior handoff (2026-09-08) — see git history for that one.

## What changed this session

Theme: turn ingestion from "one manually-triggered site" into an automated,
multi-site pipeline, with cross-site duplicate detection so the same recipe
never lands twice.

- **Deduplication** (`scraper/dedup.py`, new): every scraped recipe is
  checked against all *other* sites' recipes, not just its own — first by
  an exact hash of the normalized title, then by Postgres `pg_trgm`
  `word_similarity` (title) combined with ingredient-set Jaccard overlap.
  A match sets `status="duplicate"` + `duplicate_of_id` instead of silently
  re-saving or silently dropping; the image download is skipped for
  flagged duplicates. Migration `a1c3f9e2b7d4` adds `content_hash` /
  `duplicate_of_id` to `recipes`, enables `pg_trgm`, and backfills hashes
  for pre-existing rows. **Note**: plain `similarity()` was tried first and
  rejected — it badly under-scores a short title against a real title with
  a long marketing suffix (verified live: 0.23 vs 0.68 word_similarity on
  the same pair). See the docstring in `dedup.py` for the reasoning.
- **Generic JSON-LD site adapter** (`scraper/sites/generic.py`, new): any
  site domain *not* in `SCRAPER_REGISTRY` now falls back to this instead of
  erroring — it discovers URLs via the site's sitemap and parses
  schema.org Recipe JSON-LD (`scraper/json_ld_parser.py`, written last
  session but unused until now). Verified live against
  `cookieandkate.com` (a real site, added through the running UI, never
  hand-coded): 4/5 sitemap candidates were genuine recipes, correctly
  saved; the 5th (a non-recipe index page) was correctly skipped. **Note**:
  an early version filtered discovered URLs to ones containing "recipe" in
  the path — dropped after live testing against `budgetbytes.com` showed
  this backfires (matches roundup pages like `/easy-kale-recipes/`,
  excludes real posts like `/french-bread-pizza/`). No URL filtering now;
  the JSON-LD check itself is the filter.
- **Automation**: new Celery beat task `scrape_all_enabled_sites` fans out
  to every enabled site on a cron (`SCRAPE_SCHEDULE_CRON`, default 3am
  daily; per-site pull size `SCRAPE_DEFAULT_AUTO_LIMIT`, default 20).
  `recipe-beat.service` is now enabled and running — it was failing before
  (`PermissionError` writing its schedule file, since `recipe` doesn't own
  `/opt/scraper`); fixed by pointing `--schedule` at `/data/celery/`
  (created this session, owned by `recipe`). Both the live unit at
  `/etc/systemd/system/recipe-beat.service` and the repo copy at
  `deploy/systemd/recipe-beat.service` were updated.
- **API**: `PATCH`/`DELETE /sites/{id}` (enable/disable/rename/remove —
  delete 409s with a clear message if the site has recipes attached, since
  there's no cascade), `POST /sites/{id}/scrape?limit=N` (was hard-coded),
  `GET /recipes?status=` filter. `RecipeStatusUpdate` now accepts
  `"duplicate"` too, so a reviewer can manually flag/unflag one.
- **UI**: Sites panel has enable/disable buttons and a scrape-limit input
  (the stale "no backend endpoint yet" TODO is gone). Recipe review has a
  "Duplicates" filter tab; a flagged recipe shows which id it duplicates
  and a "Not a duplicate" button to send it back to pending.
- **Data**: three more sites scraped in addition to `retete.unica.ro`
  (id=3) — `cookieandkate.com` (id=7, generic JSON-LD adapter),
  `gustos.ro` (id=8, one of Romania's largest recipe sites — see below),
  and `www.budgetbytes.com` (id=6, intermittent — see quirks). A
  `bbc.co.uk/food/recipes` site (id=5) was added live through the UI but
  not yet scraped. The duplicate `retete.unica.ro` registration (id=4, the
  same domain registered twice under different URLs, which meant Celery
  could scrape it via two concurrent tasks and undermine its own
  per-domain rate limit) was removed — it had zero recipes attached, so
  deletion was clean.
- **`scraper/sites/gustos.py`** (new, at the user's request for a second
  Romanian source alongside unica.ro): gustos.ro publishes complete
  schema.org Recipe JSON-LD (title + full ingredients + method — verified
  live, unlike `pofta-buna.com` and `lauralaurentiu.ro`, two other
  Romanian sites checked and rejected because their JSON-LD omits
  ingredients/instructions entirely or is missing altogether).
  `savoriurbane.com` was also checked and rejected outright — its
  `robots.txt` explicitly disallows `ClaudeBot` by name and sets
  `Content-Signal: ai-train=no`, an explicit opt-out worth respecting
  regardless of what User-Agent this scraper sends. gustos.ro needs its
  own module (not the plain generic fallback) only because its sitemap
  lives at a non-standard path (`/o_cache/sitemap/sitemap.xml`) and its
  "articole" sub-sitemaps mix real recipes with unrelated tip articles;
  parsing itself reuses `scraper.sites.generic.parse_recipe` directly.
- **Safety hardening**, prompted by the user asking how daily automated
  pulls stay safe / avoid getting blocked:
  - `scraper/robots.py` (new): every `scrape_site` run now fetches and
    parses the target's `robots.txt` once, gates every subsequent request
    through `PoliteFetcher.get()` (raises `RobotsDisallowed`, caught and
    logged, not a crash), and raises the rate-limit floor to the site's own
    `Crawl-delay` if it asks for something slower than our 2-5s default.
    Previously this was only checked by hand before adding a site.
  - **Auto-disable after repeated failures**: `sites.consecutive_failures`
    (migration `b7d4f0a2c9e1`) increments on a run that finds nothing but
    robots.txt blocks / fetch errors, resets on any successful run, and
    auto-disables the site (`enabled=False`) at `MAX_CONSECUTIVE_FAILURES`
    (3, in `scraper/worker.py`). A human re-enabling a site via
    `PATCH /sites/{id}` resets the counter, so it gets a fresh 3 strikes
    rather than immediately re-disabling on the next hiccup. Verified with
    an isolated test (a throwaway Site row, no real HTTP requests) rather
    than deliberately forcing failures against a real site. Visible in the
    Sites panel as "(N failed runs in a row)" next to the status badge.
  - **A real bug found live while testing the above**: the first version
    of the auto-disable code only called `db.commit()` when
    `consecutive_failures` actually changed, which meant `site.last_scraped`
    (set on the same object just before) silently stopped being persisted
    for any site that was already healthy (`consecutive_failures == 0`) —
    the common case. Caught because a second real gustos.ro run kept
    showing the first run's timestamp. Fixed by always committing in
    `_record_run_outcome`; see that function's docstring for why the
    unconditional commit matters.

## Known quirks (not bugs — just worth knowing)

- Everything from the previous handoff still applies (`postgresql` oneshot
  wrapper reporting `inactive`, `/data` not a real mounted disk yet).
- **`budgetbytes.com` (site id=6) is intermittently blocked**, not
  consistently — earlier the same session its sitemap returned a
  Cloudflare-style HTML challenge page instead of XML (handled gracefully,
  yields zero URLs that run), but a later run the same day succeeded
  cleanly (3/3 real recipes saved, no errors). Looks like some kind of
  bot-detection that isn't triggered every time rather than a hard block.
  The new auto-disable-after-3-failures (see above) means this is now
  self-limiting either way — worth just leaving it enabled and letting the
  system decide, rather than pre-judging it.
- The dedup thresholds (`TITLE_SIMILARITY_THRESHOLD = 0.5`,
  `INGREDIENT_OVERLAP_THRESHOLD = 0.4` in `scraper/dedup.py`) were tuned
  against one real example, not a labeled test set. Watch the "Duplicates"
  review tab for false positives/negatives as more sites accumulate data
  and retune if needed — they're named constants for exactly this.

## Known gaps / deliberately left undone

1. **No auth** — deferred per spec Section 10.
2. **Recipe/ingredient content edits in the review UI still don't
   persist** — unchanged from last session; `PATCH /recipes/{id}/status`
   only changes `status` (now including `"duplicate"`). Still no endpoint
   to save title/description/tags/method edits.
3. **The generic adapter is JSON-LD-only** — sites without schema.org
   Recipe markup (like `retete.unica.ro`) still need a bespoke module in
   `scraper/sites/`. Sites behind bot-protection (like Budget Bytes) need
   Playwright wired in, which isn't done.
4. **`/data` still isn't a dedicated mounted disk** (Proxmox/infra-level,
   unrelated to this session's work).

## Suggested next-session plan, roughly in priority order

1. **Watch the duplicate detector against real cross-site data** once
   more sites accumulate recipes — the current tuning is based on one
   verified example, not a labeled set.
2. **Close the content-editing loop** (gap #2) — still the biggest
   standing UX hole, carried over from last session.
3. **Watch for auto-disabled sites** — check `consecutive_failures` /
   `enabled` in the Sites panel occasionally; a site that trips the
   3-strikes auto-disable is a signal worth a look (genuinely blocked?
   temporary? worth wiring Playwright in for?), not something to ignore.
4. **Reattach the real `/data` disk** from the Proxmox host — still
   pending, still fine for now (usage headroom unchanged).
5. **Production hardening** (spec Section 10, no urgency yet).

## Quick orientation commands for next session

```bash
systemctl status recipe-api recipe-worker recipe-beat nginx postgresql@15-main redis-server
curl -s http://localhost/api/health
curl -s http://localhost/api/recipes?status=duplicate
su postgres -c "psql -d recipe_platform -c 'SELECT id, title, status, duplicate_of_id FROM recipes ORDER BY id;'"
cd /opt/scraper && git status && git log --oneline -5
```
