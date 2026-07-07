# Watch Dashboard

Self-hosted web dashboard for Apple Watch health data: wellness trends + full archive.
Data flows in two ways — Health Auto Export (iOS app) auto-POSTs JSON, and manual upload of
Apple Health `export.zip` via the Import page. Single user, Tailscale-private, no login.

Docs: `plan/` (open `plan/1_requirements-architecture.html` in a browser), research in
`research/`, frozen UI spec in `design/mockup.html`.

## Run it

```bash
echo "API_KEY=$(openssl rand -hex 16)" > .env   # keep this key
docker compose up -d --build
open http://localhost:8000
```

The server picks the key up from `.env` automatically. The two *clients* need it pasted in
manually, once each: the Health Auto Export automation (as an `X-API-Key` header, step 3 below)
and the dashboard's Import page (remembered by the browser after the first use). To see your key
later: `cat .env`.

SQLite lives in the `watch-data` Docker volume (deliberately not under OneDrive — sync
would corrupt it). Backup: `docker compose cp watch-app:/data/watch.db ./backup.db`.

## First-time setup (Wannita's checklist)

1. **Backfill history**: iPhone Health app → profile picture → *Export All Health Data* →
   AirDrop the `export.zip` to the Mac → dashboard → *Import file* → paste API key → drop the zip.
   Progress shows records parsed; re-importing is always safe (deduplicated).
2. **Tailscale**: install on phone + this machine (free tier). Note the machine's tailnet IP
   (`tailscale ip -4`).
3. **Health Auto Export** (App Store, Premium ~$25 lifetime): create a REST API automation →
   URL `http://<tailnet-ip>:8000/api/ingest`, method POST, format JSON, add header
   `X-API-Key: <your key>`. Enable the metrics you care about + sleep + workouts, aggregation
   "days" is fine (the server aggregates per day anyway). Set it to run hourly and after wake.
4. Confirm the header pill shows a recent sync. It turns amber after 24 h without data —
   usually means iOS paused HAE; open the HAE app once to nudge it.

## Development

```bash
cd server && uv sync && uv run pytest          # backend tests (37, ~1 s)
DB_PATH=/tmp/demo.db uv run python seed_demo.py                    # fake 90 days
DB_PATH=/tmp/demo.db API_KEY=demo uv run uvicorn main:app --reload # api on :8000
cd web && npm install && npx vitest run && npm run dev             # ui on :5173, proxies /api
```

Score formulas and all tunable constants: `server/scores.py` (`CONFIG` dict).
Metric name aliases (HAE vs export.xml naming): `server/queries.py` (`ALIASES`).

## API

| Route | Auth | Purpose |
|---|---|---|
| `POST /api/ingest` | X-API-Key | Health Auto Export target (JSON) |
| `POST /api/import` | X-API-Key | Upload export.zip / HAE JSON file |
| `GET /api/import/{job}` | — | Import progress |
| `GET /api/summary?days=N` | — | Scores + headlines + sparklines |
| `GET /api/series/{metric}?days=N` | — | Daily values + rolling normal band |
| `GET /api/sleep?days=N` | — | Per-night sleep stages |
| `GET /api/status` | — | Last sync time |

GET routes are unauthenticated by design: the app must only ever be reachable over the
tailnet / LAN. Do not port-forward it to the public internet.
