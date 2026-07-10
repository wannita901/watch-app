"""v2: workout routes (GPX), mindful sessions, workouts API, HAE route ingest."""

import io
import json
import zipfile

from conftest import TEST_API_KEY

HEADERS = {"X-API-Key": TEST_API_KEY}

EXPORT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<HealthData locale="en_AU">
 <Record type="HKCategoryTypeIdentifierMindfulSession" sourceName="Watch"
   startDate="2026-07-05 08:00:00 +1000" endDate="2026-07-05 08:12:00 +1000"/>
 <Record type="HKQuantityTypeIdentifierHeartRate" sourceName="Watch" unit="count/min"
   startDate="2026-07-04 18:05:00 +1000" endDate="2026-07-04 18:05:00 +1000" value="145"/>
 <Record type="HKQuantityTypeIdentifierHeartRate" sourceName="Watch" unit="count/min"
   startDate="2026-07-04 18:20:00 +1000" endDate="2026-07-04 18:20:00 +1000" value="158"/>
 <Workout workoutActivityType="HKWorkoutActivityTypeRunning" duration="42"
   durationUnit="min" sourceName="Watch"
   startDate="2026-07-04 18:00:00 +1000" endDate="2026-07-04 18:42:00 +1000">
   <WorkoutStatistics type="HKQuantityTypeIdentifierActiveEnergyBurned" sum="350" unit="kcal"/>
 </Workout>
</HealthData>
"""

# GPX times are UTC: 18:05 +1000 == 08:05Z, inside the workout above.
GPX = """<?xml version="1.0"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1">
 <trk><trkseg>
   <trkpt lat="-37.8500" lon="145.1150"><time>2026-07-04T08:05:00Z</time></trkpt>
   <trkpt lat="-37.8510" lon="145.1160"><time>2026-07-04T08:15:00Z</time></trkpt>
   <trkpt lat="-37.8520" lon="145.1170"><time>2026-07-04T08:25:00Z</time></trkpt>
 </trkseg></trk>
</gpx>
"""


def make_zip(with_route=True) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("apple_health_export/export.xml", EXPORT_XML)
        if with_route:
            z.writestr("apple_health_export/workout-routes/route_2026-07-04_6.05pm.gpx", GPX)
    return buf.getvalue()


def do_import(client, **kw):
    r = client.post(
        "/api/import",
        files={"file": ("export.zip", make_zip(**kw), "application/zip")},
        headers=HEADERS,
    )
    assert r.status_code == 200
    job = client.get(f"/api/import/{r.json()['job_id']}").json()
    assert job["status"] == "done", job
    return job


def test_migration_adds_route_column_to_existing_db(tmp_path, monkeypatch):
    import sqlite3

    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.execute(
        """CREATE TABLE workouts (id TEXT PRIMARY KEY, type TEXT, start_ts TEXT,
           end_ts TEXT, duration_s REAL, energy_kcal REAL, distance_km REAL,
           avg_hr REAL, raw_json TEXT)"""
    )
    old.close()
    monkeypatch.setenv("DB_PATH", str(path))
    from importlib import reload

    import db

    reload(db)
    conn = db.connect()
    cols = {r[1] for r in conn.execute("PRAGMA table_info(workouts)")}
    conn.close()
    assert "route_json" in cols


def test_import_attaches_gpx_route_to_matching_workout(client):
    do_import(client)
    workouts = client.get("/api/workouts?days=9999").json()["workouts"]
    assert len(workouts) == 1
    detail = client.get(f"/api/workouts/{workouts[0]['id']}").json()
    route = detail["route"]
    assert len(route) == 3
    assert route[0] == [-37.85, 145.115]


def test_import_without_route_still_works(client):
    do_import(client, with_route=False)
    workouts = client.get("/api/workouts?days=9999").json()["workouts"]
    assert len(workouts) == 1
    detail = client.get(f"/api/workouts/{workouts[0]['id']}").json()
    assert detail["route"] is None


def test_route_downsampled_to_500_points(client):
    import importer

    pts = [[float(i), float(i)] for i in range(2000)]
    out = importer.downsample(pts, 500)
    assert len(out) <= 500
    assert out[0] == [0.0, 0.0] and out[-1] == [1999.0, 1999.0]


def test_import_mindful_session_stored_as_minutes(client):
    do_import(client)
    pts = client.get("/api/series/mindful_minutes?days=9999").json()["points"]
    assert len(pts) == 1 and pts[0]["value"] == 12.0


def test_workout_detail_includes_hr_series_from_window(client):
    do_import(client)
    w = client.get("/api/workouts?days=9999").json()["workouts"][0]
    detail = client.get(f"/api/workouts/{w['id']}").json()
    assert [p["value"] for p in detail["hr"]] == [145.0, 158.0]


def test_workouts_list_shape(client):
    do_import(client)
    w = client.get("/api/workouts?days=9999").json()["workouts"][0]
    assert w["type"] == "Running"
    assert w["duration_s"] == 42 * 60
    assert w["energy_kcal"] == 350
    assert w["has_route"] is True


def test_unknown_workout_404(client):
    assert client.get("/api/workouts/nope").status_code == 404


def test_ingest_hae_workout_with_route(client):
    payload = {
        "data": {
            "metrics": [],
            "workouts": [
                {
                    "name": "Outdoor Walk",
                    "start": "2026-07-06 07:00:00 +1000",
                    "end": "2026-07-06 07:30:00 +1000",
                    "duration": 30.0,
                    "route": [
                        {"lat": -37.85, "lon": 145.115, "timestamp": "2026-07-06 07:00:05 +1000"},
                        {"lat": -37.851, "lon": 145.116, "timestamp": "2026-07-06 07:10:00 +1000"},
                    ],
                }
            ],
        }
    }
    client.post("/api/ingest", json=payload, headers=HEADERS)
    w = client.get("/api/workouts?days=9999").json()["workouts"][0]
    detail = client.get(f"/api/workouts/{w['id']}").json()
    assert detail["route"] == [[-37.85, 145.115], [-37.851, 145.116]]
