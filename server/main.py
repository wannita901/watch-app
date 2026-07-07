import os
import shutil
import tempfile
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Request,
    UploadFile,
)

import db
import importer
import ingest
import queries


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.connect().close()  # ensure schema exists at startup
    yield


app = FastAPI(title="watch-app", lifespan=lifespan)


def require_api_key(x_api_key: str | None = Header(default=None)):
    expected = os.environ.get("API_KEY")
    if not expected or x_api_key != expected:
        raise HTTPException(status_code=401, detail="invalid or missing X-API-Key")


def now_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S +0000")


@app.get("/api/health")
def health():
    return {"status": "ok", "db": db.db_path()}


@app.post("/api/ingest", dependencies=[Depends(require_api_key)])
async def ingest_route(request: Request):
    payload = await request.json()
    conn = db.connect()
    try:
        return ingest.ingest_payload(conn, payload, now_ts())
    finally:
        conn.close()


@app.post("/api/import", dependencies=[Depends(require_api_key)])
def import_route(file: UploadFile, background: BackgroundTasks):
    job_id = uuid.uuid4().hex[:12]
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".upload")
    with tmp:
        shutil.copyfileobj(file.file, tmp)
    importer.JOBS[job_id] = {"status": "queued", "parsed": 0, "counts": {}}

    def run_and_cleanup():
        try:
            importer.run_import(job_id, tmp.name)
        finally:
            os.unlink(tmp.name)

    background.add_task(run_and_cleanup)
    return {"job_id": job_id}


@app.get("/api/import/{job_id}")
def import_status(job_id: str):
    job = importer.JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="unknown import job")
    return job


@app.get("/api/status")
def status():
    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT ts, kind, n_rows FROM ingest_log ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return {"last_sync": None, "last_kind": None, "n_rows": 0}
    return {"last_sync": row[0], "last_kind": row[1], "n_rows": row[2]}


@app.get("/api/series/{metric}")
def series(metric: str, days: int = 30):
    conn = db.connect()
    try:
        points = queries.series_with_band(conn, metric, days)
    finally:
        conn.close()
    return {"metric": metric, "points": points}


@app.get("/api/summary")
def summary(days: int = 30):
    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT ts FROM ingest_log ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
        return queries.summary(conn, days, row[0] if row else None)
    finally:
        conn.close()


@app.get("/api/sleep")
def sleep(days: int = 30):
    conn = db.connect()
    try:
        rows = conn.execute(
            """SELECT date, start_ts, end_ts, deep_h, core_h, rem_h, awake_h
               FROM sleep_nights WHERE date >= date('now', ?) ORDER BY date""",
            (f"-{days} days",),
        ).fetchall()
    finally:
        conn.close()
    keys = ["date", "start_ts", "end_ts", "deep_h", "core_h", "rem_h", "awake_h"]
    return {"nights": [dict(zip(keys, r)) for r in rows]}


# Serve the built frontend (must be mounted last so /api/* wins).
_STATIC = os.environ.get(
    "STATIC_DIR", os.path.join(os.path.dirname(__file__), "..", "web", "dist")
)
if os.path.isdir(_STATIC):
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=_STATIC, html=True), name="static")
