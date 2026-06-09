# Go Cold WMS — NUC deployment

LAN-only deployment of the three WMS tools onto the warehouse NUC
(Ubuntu Server 24.04). Everything runs in Docker behind a single Caddy
reverse proxy. No public internet exposure, no Cloudflare tunnel, plain
HTTP over the LAN.

## What's in the stack

| Hostname | Service | What it is | Internal port |
|---|---|---|---|
| `picks.gocold.local` | `picks` | Wave pick console (FastAPI) | 8077 |
| `runs.gocold.local`  | `runs`  | Dispatch run console (FastAPI) | 8078 |
| `dims.gocold.local`  | `dims-frontend` → `dims-backend` | Dim-capture PWA + API | 80 → 3005 |
| _(internal only)_    | `postgres` | Postgres 16, `dimcapture` DB | 5432 |
| _(host :80)_         | `caddy` | Reverse proxy — **the only published port** | 80 |

`picks` and `runs` share one image (`gocold-consoles`) and the host's
`./data` + `./.env`. `dims-*` is the `dim-capture-app/` Node sub-project.
Postgres is used **only** by `dims-backend`; the consoles are file-based.

## Prerequisites

- Docker Engine + Compose v2 on the NUC.
- **Build-time internet.** Building pulls base images and runs `npm ci` /
  `pip install`. Build on a machine with internet (or pre-pull/cache), even
  though the running stack is LAN-only.
- **Run-time outbound HTTPS to CartonCloud.** The consoles and `dims-backend`
  pull from `api.cartoncloud.com` / `app.cartoncloud.com.au`. "LAN-only" here
  means no *inbound* exposure — the NUC still needs *outbound* HTTPS for live
  CC pulls. If it truly has zero internet, live pulls won't work and the
  consoles run only off pre-staged files in `./data`.

## One-time setup

From the repo root on the NUC:

```bash
# 1. DB password secret (set BEFORE first up — Postgres bakes it on init).
openssl rand -base64 32 > secrets/db_password.txt

# 2. App config: copy the template and fill in real CC credentials.
cp .env.example .env
$EDITOR .env          # CC_CLIENT_ID/SECRET, CC_TENANT_ID, CC_API_KEY,
                      # CC_WAREHOUSE_ID, SYNC_SECRET (openssl rand -hex 32)

# 3. Stage customer data the consoles read (dims, locations, any parquet)
#    into ./data, then hand the bind-mount to the container's app user
#    (UID 10001) so it can write run output under ./data/processed.
sudo chown -R 10001:10001 data
```

## Build & run

```bash
docker compose build          # builds gocold-consoles + dims images
docker compose up -d          # start everything detached
docker compose ps             # all services should become healthy
```

`postgres` becomes healthy first, then `dims-backend` (runs
`prisma migrate deploy`), then `dims-frontend`; the consoles and Caddy come
up alongside.

## Staff device access (DNS)

There are no real certs and no public DNS. Point the three `.local` names at
the NUC's static LAN IP. On each staff device add to its hosts file
(`/etc/hosts`, or `C:\Windows\System32\drivers\etc\hosts`):

```
# Replace <NUC_LAN_IP> with the NUC's static LAN address, e.g. 192.168.1.50
<NUC_LAN_IP>  picks.gocold.local runs.gocold.local dims.gocold.local
```

Better, set the same three A-records on the site router / local DNS so no
per-device edits are needed. Then browse to `http://picks.gocold.local`, etc.

## Operating

```bash
docker compose logs -f caddy            # proxy / routing
docker compose logs -f picks runs       # console build jobs + CC pulls
docker compose logs -f dims-backend     # API + prisma migrate output
docker compose ps                       # health status

docker compose restart picks            # restart one service
docker compose up -d --build dims-backend   # rebuild + redeploy one app
docker compose down                     # stop the stack (keeps volumes)
```

Caddy access logs are on the `caddy_logs` volume
(`/var/log/caddy/{picks,runs,dims}.log`, rolled at 10 MiB ×5).

## Security & data handling

- **No app publishes a host port** — only Caddy (:80). Postgres, the
  consoles, and `dims-backend` are reachable only on the internal Docker
  network.
- **Secrets never enter an image.** `./.env` is bind-mounted read-only;
  `./data` is bind-mounted; the DB password is a Docker secret. Each app's
  `.dockerignore` excludes `.env`, `node_modules`, build dirs, and `./data`.
- **`CC_BASE_URL` is pinned per-service** in `docker-compose.yml` (the two
  stacks use different CC bases) — do not set it in `.env`.
- **Customer data stays on host disk** under `./data` (SO-line parquet,
  carton dims, locations, generated wave + dispatch manifests). It is never
  copied into an image. Back up `./data` and the `pgdata` volume.
- **Changing the DB password later** requires resetting the `pgdata` volume
  (Postgres only reads the password file on first init):
  `docker compose down && docker volume rm gocold-wms_pgdata` then re-up.
  This wipes captured dims — export first if they matter.

## Notes / known trade-offs

- `dims-frontend` is plain `nginx:1.27-alpine`: the worker processes already
  run as the unprivileged `nginx` user, but the master runs as root to bind
  :80 — standard, and acceptable since it's internal-only behind Caddy. The
  consoles run as non-root UID 10001; `dims-backend` runs as the `node` user.
- The pre-existing `dim-capture-app/docker-compose.yml` and
  `dim-capture-app/caddy/` fragment are **superseded** by this root stack and
  are not used here.
