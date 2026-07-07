def test_health_returns_ok(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_schema_created(conn):
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert {"samples", "sleep_nights", "workouts", "ingest_log", "raw_points"} <= tables


def test_samples_upsert_idempotent(conn):
    import db

    rows = [("heart_rate", "2026-07-07 08:00:00 +1000", 62.0, "count/min", "watch")]
    db.upsert_samples(conn, rows)
    db.upsert_samples(conn, rows)  # same natural key → no duplicate
    n = conn.execute("SELECT COUNT(*) FROM samples").fetchone()[0]
    assert n == 1


def test_samples_upsert_replaces_value(conn):
    import db

    key = ("heart_rate", "2026-07-07 08:00:00 +1000")
    db.upsert_samples(conn, [(*key, 62.0, "count/min", "watch")])
    db.upsert_samples(conn, [(*key, 64.0, "count/min", "watch")])
    v = conn.execute("SELECT value FROM samples").fetchone()[0]
    assert v == 64.0
