# Dispatch Run Console — Deploy (runs.rolodex-ai.com)

Mirrors the wave-pick console deploy (`picks.rolodex-ai.com`). The console
serves a single dispatcher, read-only against CartonCloud, on the laptop
(data + `.env` CC creds live here).

## Process
- App: `scripts/serve_web_dispatch.py` → uvicorn `web_dispatch.app:app` on
  `127.0.0.1:8078`.
- Published at **https://runs.rolodex-ai.com** via a named Cloudflare Tunnel
  `wms-runs`, gated by Cloudflare Access (same one-time-PIN email allowlist
  as picks).

## Tunnel (run these via `!` — they trip the exposure classifier)
```
cloudflared tunnel create wms-runs
# write ~/.cloudflared/wms-runs.yml:
#   tunnel: <wms-runs-id>
#   credentials-file: /home/pop_os/.cloudflared/<wms-runs-id>.json
#   ingress:
#     - hostname: runs.rolodex-ai.com
#       service: http://127.0.0.1:8078
#     - service: http_status:404
cloudflared tunnel route dns wms-runs runs.rolodex-ai.com
```
Add `runs.rolodex-ai.com` to the existing Cloudflare Access application (or
clone the picks policy) so the email allowlist is enforced at the edge.

## systemd --user services
Create `~/.config/systemd/user/wms-runs-app.service` (ExecStart =
`/home/pop_os/archive/rolodex/gocold-wms-flow/.venv/bin/python
scripts/serve_web_dispatch.py`, WorkingDirectory = repo root) and
`wms-runs-tunnel.service` (`After=wms-runs-app.service`, ExecStart =
`cloudflared tunnel run wms-runs`). Then:
```
systemctl --user daemon-reload
systemctl --user enable --now wms-runs-app wms-runs-tunnel
```
Linger is already enabled for `pop_os`. After a Python change:
`systemctl --user restart wms-runs-app` (templates/CSS need no restart).

## Verify
- `curl -sI http://127.0.0.1:8078/` → 200.
- Unauthenticated `https://runs.rolodex-ai.com` → 302 to Cloudflare Access.
