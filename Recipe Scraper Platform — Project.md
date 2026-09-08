# 🍽️ Recipe Scraper Platform — Project Specification

## Overview

A self-hosted platform for scraping, managing, and serving recipe/meal data via a REST API.
Built on a Proxmox LXC container (Debian 12), all services run natively — no Docker or nested virtualisation.

---

## 1. LXC Container Specification

| Resource       | Value              | Notes                                      |
|----------------|--------------------|--------------------------------------------|
| **OS**         | Debian 12 (Bookworm) | Stable, LTS, fully supported by Proxmox  |
| **Type**       | LXC Unprivileged   | Native, no nested virtualisation          |
| **vCPUs**      | 4                  | Scraping + API + DB workloads              |
| **RAM**        | 8 GB               | Headroom for Playwright + Postgres         |
| **OS Disk**    | 40 GB (RAID5)      | System, app code, virtualenvs              |
| **Data Disk**  | 100 GB (RAID6)     | Mounted at `/data` — PostgreSQL + images   |
| **Network**    | VirtIO, bridged    | Standard Proxmox config                   |
| **Hostname**   | `recipe-dev-01`    | Suggested container name                  |

> ⚠️ Keep the data disk separate (`/data`). It can be snapshotted and reattached at production migration time.

### Proxmox create command
```bash
pct create 131 local:vztmpl/debian-12-standard_12.7-1_amd64.tar.zst \
  --hostname recipe-dev-01 \
  --cores 4 \
  --memory 8192 \
  --rootfs RAID5:40 \
  --mp0 RAID6:100,mp=/data \
  --net0 name=eth0,bridge=vmbr0,ip=dhcp \
  --unprivileged 1 \
  --features nesting=0
```

---

## 2. Tech Stack (Native — No Docker)

| Layer              | Technology                        | Managed by         |
|--------------------|-----------------------------------|--------------------|
| **Scraper**        | Python 3.11 + Playwright          | systemd service    |
| **Task Queue**     | Celery + Redis                    | systemd service    |
| **API**            | FastAPI + Uvicorn                 | systemd service    |
| **Database**       | PostgreSQL 16                     | systemd service    |
| **Image Storage**  | `/data/images/`                   | Nginx static serve |
| **Web Server**     | Nginx                             | systemd service    |
| **Management UI**  | React (Vite, built to static)     | Served by Nginx    |
| **Migrations**     | Alembic                           | Run manually / CI  |
| **Python env**     | venv at `/opt/recipe-platform/`   | Per-service        |

---

## 3. Service Layout (systemd)

Each component runs as its own systemd service under a dedicated `recipe` user:

```
recipe-api.service       # FastAPI + Uvicorn on 127.0.0.1:8000
recipe-worker.service    # Celery worker
recipe-beat.service      # Celery beat scheduler (periodic scrapes)
redis-server.service     # Redis (installed via apt)
postgresql.service       # PostgreSQL 16 (installed via apt)
nginx.service            # Reverse proxy + static UI + image serving
```

---

## 4. Directory Structure

```
/opt/recipe-platform/       # App root
├── api/
│   ├── main.py
│   ├── routers/
│   │   ├── recipes.py
│   │   ├── sites.py
│   │   └── scrape.py
│   ├── models/
│   ├── schemas/
│   └── db.py
├── scraper/
│   ├── worker.py           # Celery entry point
│   ├── playwright_scraper.py
│   ├── json_ld_parser.py
│   └── sites/              # Per-site scraper configs
├── ui/dist/                # Built React static files (served by Nginx)
├── migrations/             # Alembic
├── venv/                   # Python virtualenv
├── .env                    # Secrets & config
└── README.md

/data/
├── postgres/               # PostgreSQL data directory (PGDATA)
└── images/                 # Scraped recipe images
```

---

## 5. Database Schema (Draft)

### `sites` — Scrape targets
```sql
id           SERIAL PRIMARY KEY
url          TEXT NOT NULL UNIQUE
name         TEXT
enabled      BOOLEAN DEFAULT TRUE
last_scraped TIMESTAMPTZ
created_at   TIMESTAMPTZ DEFAULT NOW()
```

### `recipes`
```sql
id           SERIAL PRIMARY KEY
site_id      INT REFERENCES sites(id)
title        TEXT NOT NULL
cuisine      TEXT
description  TEXT
prep_time    INT           -- minutes
cook_time    INT           -- minutes
servings     INT
method       TEXT[]        -- ordered steps
tags         TEXT[]
source_url   TEXT UNIQUE
image_url    TEXT
image_path   TEXT          -- local path under /data/images/
status       TEXT DEFAULT 'pending'  -- pending | approved | rejected
scraped_at   TIMESTAMPTZ DEFAULT NOW()
```

### `ingredients`
```sql
id           SERIAL PRIMARY KEY
recipe_id    INT REFERENCES recipes(id) ON DELETE CASCADE
name         TEXT NOT NULL
quantity     NUMERIC
unit         TEXT
notes        TEXT          -- "finely chopped", "optional", etc.
```

---

## 6. API Endpoints (Planned)

| Method | Endpoint               | Description                            |
|--------|------------------------|----------------------------------------|
| GET    | `/recipes`             | List recipes (filter by cuisine, tag)  |
| GET    | `/recipes/{id}`        | Single recipe with ingredients         |
| POST   | `/recipes/search`      | Full-text search                       |
| GET    | `/ingredients`         | Ingredient lookup / autocomplete       |
| GET    | `/sites`               | List registered scrape targets         |
| POST   | `/sites`               | Add a new site to scrape               |
| POST   | `/sites/{id}/scrape`   | Trigger a scrape job                   |
| GET    | `/scrape/jobs`         | List active / queued scrape jobs       |
| PATCH  | `/recipes/{id}/status` | Approve or reject a scraped recipe     |
| GET    | `/images/{filename}`   | Serve stored recipe images             |

---

## 7. Management UI Features

- **Sites panel** — add/remove/enable/disable scrape targets
- **Scrape queue** — trigger scrapes, view job status and logs
- **Recipe review** — browse pending recipes, approve/reject, edit before saving
- **Ingredient editor** — fix parsed ingredient data inline
- **Image preview** — view scraped images alongside recipe data

---

## 8. Scraper Design

### Strategy per site

| Site type         | Tool                         |
|-------------------|------------------------------|
| Static HTML       | `requests` + `BeautifulSoup` |
| JS-rendered (SPA) | `Playwright` (headless)      |
| JSON-LD schema    | Parse `application/ld+json`  |

### Scrape flow
1. Site URL added via Management UI or API
2. Celery worker picks up job
3. Playwright loads page, extracts JSON-LD or HTML
4. Data normalised into recipe + ingredients model
5. Images downloaded to `/data/images/`
6. Recipe saved with `status = pending`
7. User reviews and approves via UI

### Politeness rules
- Respect `robots.txt`
- Rate limit: 1 request per 2–5 seconds per domain
- Rotate user-agent string
- Log all requests

---

## 9. Nginx Config (outline)

```nginx
server {
    listen 80;
    server_name recipe-dev-01;

    # Management UI (built React static)
    location / {
        root /opt/recipe-platform/ui/dist;
        try_files $uri /index.html;
    }

    # API proxy
    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
    }

    # Scraped images
    location /images/ {
        alias /data/images/;
    }
}
```

---

## 10. Production Migration Path

| Step | Action                                              |
|------|-----------------------------------------------------|
| 1    | Snapshot `/data` disk from Proxmox                  |
| 2    | Reattach to production LXC or bare metal            |
| 3    | Point `PGDATA` to `/data/postgres`                  |
| 4    | Add SSL via Let's Encrypt (certbot + Nginx)         |
| 5    | Set up `pg_dump` scheduled backups (cron)           |
| 6    | Harden API with auth (API keys or OAuth2)           |
| 7    | Optionally migrate images to MinIO (S3-compatible)  |

---

## 11. First Steps in Claude Code Session

1. Create and start LXC 131 with Debian 12
2. `apt install` — Python 3.11, PostgreSQL 16, Redis, Nginx, Playwright deps
3. Create `recipe` system user, set up `/opt/recipe-platform/` and `/data/`
4. Init Python venv, install FastAPI, Celery, Alembic, Playwright, BeautifulSoup
5. Run Alembic migrations to create schema
6. Scaffold FastAPI with `/sites` and `/recipes` routers
7. Write systemd unit files for api, worker, beat
8. Build basic Playwright scraper for one target site
9. Build and deploy React management UI via Nginx

---

*Generated: September 2026 | Dev host: Proxmox (128GB RAM, 20 cores) | Container: recipe-dev-01 (LXC 131, Debian 12)*