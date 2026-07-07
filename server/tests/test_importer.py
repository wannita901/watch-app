"""Manual import of Apple Health export.zip (streaming XML parse)."""

import io
import zipfile

from conftest import TEST_API_KEY

HEADERS = {"X-API-Key": TEST_API_KEY}

EXPORT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<HealthData locale="en_AU">
 <Record type="HKQuantityTypeIdentifierRestingHeartRate" sourceName="Watch"
   unit="count/min" startDate="2026-07-05 00:00:00 +1000"
   endDate="2026-07-05 23:59:00 +1000" value="52"/>
 <Record type="HKQuantityTypeIdentifierStepCount" sourceName="Phone"
   unit="count" startDate="2026-07-05 09:00:00 +1000"
   endDate="2026-07-05 09:10:00 +1000" value="612"/>
 <Record type="HKQuantityTypeIdentifierStepCount" sourceName="Phone"
   unit="count" startDate="2026-07-05 10:00:00 +1000"
   endDate="2026-07-05 10:10:00 +1000" value="431"/>
 <Record type="HKCategoryTypeIdentifierSleepAnalysis" sourceName="Watch"
   value="HKCategoryValueSleepAnalysisAsleepDeep"
   startDate="2026-07-05 23:30:00 +1000" endDate="2026-07-06 00:30:00 +1000"/>
 <Record type="HKCategoryTypeIdentifierSleepAnalysis" sourceName="Watch"
   value="HKCategoryValueSleepAnalysisAsleepCore"
   startDate="2026-07-06 00:30:00 +1000" endDate="2026-07-06 04:30:00 +1000"/>
 <Record type="HKCategoryTypeIdentifierSleepAnalysis" sourceName="Watch"
   value="HKCategoryValueSleepAnalysisAsleepREM"
   startDate="2026-07-06 04:30:00 +1000" endDate="2026-07-06 06:00:00 +1000"/>
 <Record type="HKCategoryTypeIdentifierSleepAnalysis" sourceName="Watch"
   value="HKCategoryValueSleepAnalysisAwake"
   startDate="2026-07-06 06:00:00 +1000" endDate="2026-07-06 06:15:00 +1000"/>
 <Workout workoutActivityType="HKWorkoutActivityTypeRunning" duration="42"
   durationUnit="min" sourceName="Watch"
   startDate="2026-07-04 18:00:00 +1000" endDate="2026-07-04 18:42:00 +1000">
   <WorkoutStatistics type="HKQuantityTypeIdentifierActiveEnergyBurned"
     sum="350" unit="kcal"/>
 </Workout>
</HealthData>
"""


def make_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("apple_health_export/export.xml", EXPORT_XML)
    return buf.getvalue()


def do_import(client):
    r = client.post(
        "/api/import",
        files={"file": ("export.zip", make_zip(), "application/zip")},
        headers=HEADERS,
    )
    assert r.status_code == 200
    return r.json()["job_id"]


def test_import_requires_api_key(client):
    r = client.post(
        "/api/import", files={"file": ("export.zip", make_zip(), "application/zip")}
    )
    assert r.status_code == 401


def test_import_reports_progress_and_counts(client):
    job_id = do_import(client)
    job = client.get(f"/api/import/{job_id}").json()
    assert job["status"] == "done"
    assert job["counts"]["samples"] == 3
    assert job["counts"]["sleep_nights"] == 1
    assert job["counts"]["workouts"] == 1


def test_import_maps_hk_identifiers_to_snake_case(client):
    do_import(client)
    pts = client.get("/api/series/resting_heart_rate?days=9999").json()["points"]
    assert len(pts) == 1 and pts[0]["value"] == 52
    pts = client.get("/api/series/step_count?days=9999").json()["points"]
    assert [p["value"] for p in pts] == [1043]  # same-day counter points sum per day


def test_import_aggregates_sleep_stages_to_wake_date_night(client):
    do_import(client)
    nights = client.get("/api/sleep?days=9999").json()["nights"]
    assert len(nights) == 1
    n = nights[0]
    assert n["date"] == "2026-07-06"  # spans midnight → keyed by wake date
    assert n["deep_h"] == 1.0 and n["core_h"] == 4.0
    assert n["rem_h"] == 1.5 and n["awake_h"] == 0.25


def test_import_workout(client):
    do_import(client)
    import db

    conn = db.connect()
    rows = conn.execute("SELECT type, duration_s, energy_kcal FROM workouts").fetchall()
    conn.close()
    assert rows == [("Running", 42 * 60.0, 350.0)]


def test_import_is_idempotent(client):
    do_import(client)
    do_import(client)
    pts = client.get("/api/series/step_count?days=9999").json()["points"]
    assert [p["value"] for p in pts] == [1043]  # re-import doesn't double-count
    nights = client.get("/api/sleep?days=9999").json()["nights"]
    assert len(nights) == 1


def test_unknown_import_job_404(client):
    assert client.get("/api/import/doesnotexist").status_code == 404
