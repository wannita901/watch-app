"""Ingest of Health Auto Export REST payloads.

Fixture shapes follow HAE's documented JSON format; ingest must be tolerant:
unknown metrics or point shapes are preserved (raw_points), never dropped.
"""

from conftest import TEST_API_KEY

HEADERS = {"X-API-Key": TEST_API_KEY}


def payload(metrics=None, workouts=None):
    return {"data": {"metrics": metrics or [], "workouts": workouts or []}}


STEPS = {
    "name": "step_count",
    "units": "count",
    "data": [
        {"date": "2026-07-06 23:59:00 +1000", "qty": 8412},
        {"date": "2026-07-05 23:59:00 +1000", "qty": 10033},
    ],
}

HR_MIN_AVG_MAX = {
    "name": "heart_rate",
    "units": "count/min",
    "data": [{"date": "2026-07-06 08:00:00 +1000", "Min": 48, "Avg": 62.5, "Max": 110}],
}

SLEEP = {
    "name": "sleep_analysis",
    "units": "hr",
    "data": [
        {
            "date": "2026-07-07 07:02:00 +1000",
            "sleepStart": "2026-07-06 23:40:00 +1000",
            "sleepEnd": "2026-07-07 07:02:00 +1000",
            "deep": 0.9,
            "core": 3.9,
            "rem": 1.5,
            "awake": 0.3,
        }
    ],
}

WEIRD = {
    "name": "future_metric",
    "units": "?",
    "data": [{"date": "2026-07-06 12:00:00 +1000", "payload": {"nested": True}}],
}

WORKOUT = {
    "name": "Outdoor Run",
    "start": "2026-07-06 18:00:00 +1000",
    "end": "2026-07-06 18:42:00 +1000",
    "duration": 42.0,
    "activeEnergyBurned": {"qty": 350.0, "units": "kcal"},
    "distance": {"qty": 5.2, "units": "km"},
    "avgHeartRate": {"qty": 152.0, "units": "count/min"},
}


def test_ingest_requires_api_key(client):
    assert client.post("/api/ingest", json=payload([STEPS])).status_code == 401
    r = client.post("/api/ingest", json=payload([STEPS]), headers={"X-API-Key": "nope"})
    assert r.status_code == 401


def test_ingest_quantity_metric(client):
    r = client.post("/api/ingest", json=payload([STEPS]), headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["samples"] == 2
    series = client.get("/api/series/step_count?days=9999").json()
    assert [p["value"] for p in series["points"]] == [10033, 8412]


def test_ingest_min_avg_max(client):
    client.post("/api/ingest", json=payload([HR_MIN_AVG_MAX]), headers=HEADERS)
    for metric, expected in [
        ("heart_rate", 62.5),
        ("heart_rate_min", 48),
        ("heart_rate_max", 110),
    ]:
        pts = client.get(f"/api/series/{metric}?days=9999").json()["points"]
        assert len(pts) == 1 and pts[0]["value"] == expected


def test_ingest_is_idempotent(client):
    for _ in range(2):
        client.post("/api/ingest", json=payload([STEPS]), headers=HEADERS)
    pts = client.get("/api/series/step_count?days=9999").json()["points"]
    assert len(pts) == 2


def test_ingest_sleep_night(client):
    r = client.post("/api/ingest", json=payload([SLEEP]), headers=HEADERS)
    assert r.json()["sleep_nights"] == 1
    nights = client.get("/api/sleep?days=9999").json()["nights"]
    assert len(nights) == 1
    n = nights[0]
    assert n["date"] == "2026-07-07"  # night keyed by wake-up date
    assert n["deep_h"] == 0.9 and n["core_h"] == 3.9
    assert n["rem_h"] == 1.5 and n["awake_h"] == 0.3


def test_ingest_workout(client):
    r = client.post("/api/ingest", json=payload(workouts=[WORKOUT]), headers=HEADERS)
    assert r.json()["workouts"] == 1
    # idempotent: same name+start → same id
    client.post("/api/ingest", json=payload(workouts=[WORKOUT]), headers=HEADERS)
    import db

    conn = db.connect()
    rows = conn.execute("SELECT type, distance_km, avg_hr FROM workouts").fetchall()
    conn.close()
    assert rows == [("Outdoor Run", 5.2, 152.0)]


def test_unknown_point_shape_preserved_not_dropped(client):
    r = client.post("/api/ingest", json=payload([WEIRD]), headers=HEADERS)
    assert r.status_code == 200
    import db

    conn = db.connect()
    raw = conn.execute("SELECT metric, json FROM raw_points").fetchall()
    conn.close()
    assert raw and raw[0][0] == "future_metric" and "nested" in raw[0][1]


def test_status_reports_last_sync(client):
    assert client.get("/api/status").json()["last_sync"] is None
    client.post("/api/ingest", json=payload([STEPS]), headers=HEADERS)
    status = client.get("/api/status").json()
    assert status["last_sync"] is not None
    assert status["last_kind"] == "ingest"
