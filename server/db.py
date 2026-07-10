"""SQLite schema and upsert helpers. One connection per request/task."""

import os
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS samples (
    metric TEXT NOT NULL,
    ts     TEXT NOT NULL,
    value  REAL NOT NULL,
    unit   TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (metric, ts, source)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS sleep_nights (
    date     TEXT PRIMARY KEY,
    start_ts TEXT,
    end_ts   TEXT,
    deep_h   REAL DEFAULT 0,
    core_h   REAL DEFAULT 0,
    rem_h    REAL DEFAULT 0,
    awake_h  REAL DEFAULT 0,
    source   TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS workouts (
    id          TEXT PRIMARY KEY,
    type        TEXT,
    start_ts    TEXT,
    end_ts      TEXT,
    duration_s  REAL,
    energy_kcal REAL,
    distance_km REAL,
    avg_hr      REAL,
    raw_json    TEXT,
    route_json  TEXT
);
CREATE TABLE IF NOT EXISTS raw_points (
    metric TEXT NOT NULL,
    ts     TEXT NOT NULL,
    json   TEXT NOT NULL,
    PRIMARY KEY (metric, ts)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS ingest_log (
    ts     TEXT NOT NULL,
    kind   TEXT NOT NULL,
    n_rows INTEGER NOT NULL,
    detail TEXT DEFAULT ''
);
"""


def db_path() -> str:
    return os.environ.get("DB_PATH", "data/watch.db")


def connect() -> sqlite3.Connection:
    path = db_path()
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


def _migrate(conn):
    """Idempotent column additions for DBs created before the column existed."""
    try:
        conn.execute("ALTER TABLE workouts ADD COLUMN route_json TEXT")
    except sqlite3.OperationalError:
        pass  # already there


def upsert_samples(conn, rows):
    """rows: iterable of (metric, ts, value, unit, source)."""
    conn.executemany(
        "INSERT OR REPLACE INTO samples (metric, ts, value, unit, source) VALUES (?,?,?,?,?)",
        rows,
    )
    conn.commit()


def upsert_sleep_night(conn, row):
    """row: (date, start_ts, end_ts, deep_h, core_h, rem_h, awake_h, source)."""
    conn.execute(
        "INSERT OR REPLACE INTO sleep_nights VALUES (?,?,?,?,?,?,?,?)", row
    )
    conn.commit()


def upsert_workout(conn, row):
    """row: (id, type, start_ts, end_ts, duration_s, energy_kcal, distance_km,
    avg_hr, raw_json, route_json)."""
    conn.execute("INSERT OR REPLACE INTO workouts VALUES (?,?,?,?,?,?,?,?,?,?)", row)
    conn.commit()


def log_ingest(conn, ts, kind, n_rows, detail=""):
    conn.execute(
        "INSERT INTO ingest_log VALUES (?,?,?,?)", (ts, kind, n_rows, detail)
    )
    conn.commit()
