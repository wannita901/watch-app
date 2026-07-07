"""Daily aggregation, rolling bands, and the /api/summary contract."""

from datetime import date, timedelta

import pytest


def seed(conn, metric, day_values, unit=""):
    import db

    rows = [
        (metric, f"{d} 12:00:00 +1000", v, unit, "")
        for d, v in day_values
    ]
    db.upsert_samples(conn, rows)


def days_back(n):
    """n dates ending today, oldest first."""
    today = date.today()
    return [(today - timedelta(days=i)).isoformat() for i in range(n - 1, -1, -1)]


def test_rolling_band_flat_series_is_tight():
    import queries

    band = queries.rolling_band([50.0] * 10, window=5, k=1.5)
    assert len(band) == 10
    lo, hi = band[-1]
    assert lo == pytest.approx(50) and hi == pytest.approx(50)


def test_rolling_band_widens_with_variance():
    import queries

    band = queries.rolling_band([40, 60, 40, 60, 40, 60], window=6, k=1.5)
    lo, hi = band[-1]
    assert lo < 40 + 5 and hi > 60 - 5


def test_series_sums_counter_metrics_per_day(client, conn):
    d = days_back(1)[0]
    import db

    db.upsert_samples(
        conn,
        [
            ("step_count", f"{d} 09:00:00 +1000", 612, "count", ""),
            ("step_count", f"{d} 10:00:00 +1000", 431, "count", ""),
        ],
    )
    pts = client.get("/api/series/step_count?days=7").json()["points"]
    assert len(pts) == 1
    assert pts[0]["value"] == 1043
    assert pts[0]["date"] == d


def test_series_averages_gauge_metrics_per_day(client, conn):
    d = days_back(1)[0]
    import db

    db.upsert_samples(
        conn,
        [
            ("resting_heart_rate", f"{d} 08:00:00 +1000", 50, "bpm", ""),
            ("resting_heart_rate", f"{d} 20:00:00 +1000", 54, "bpm", ""),
        ],
    )
    pts = client.get("/api/series/resting_heart_rate?days=7").json()["points"]
    assert pts[0]["value"] == 52


def test_series_includes_band(client, conn):
    vals = list(zip(days_back(10), [50, 51, 49, 50, 52, 48, 50, 51, 49, 50]))
    seed(conn, "resting_heart_rate", vals)
    body = client.get("/api/series/resting_heart_rate?days=10").json()
    assert len(body["points"]) == 10
    p = body["points"][-1]
    assert p["lo"] < p["value"] < p["hi"]


def test_summary_contract(client, conn):
    import db

    dd = days_back(70)
    seed(conn, "heart_rate_variability", [(d, 45 + (i % 5)) for i, d in enumerate(dd)])
    seed(conn, "resting_heart_rate", [(d, 52 + (i % 3)) for i, d in enumerate(dd)])
    seed(conn, "step_count", [(d, 8000 + 100 * (i % 7)) for i, d in enumerate(dd)])
    seed(conn, "apple_exercise_time", [(d, 25) for d in dd])
    seed(conn, "apple_sleeping_wrist_temperature", [(d, 35.1) for d in dd])
    seed(conn, "oxygen_saturation", [(d, 0.97) for d in dd])
    for d in dd:
        db.upsert_sleep_night(conn, (d, f"{d} 23:30:00 +1000", f"{d} 07:00:00 +1000",
                                     1.1, 4.0, 1.5, 0.3, "test"))

    s = client.get("/api/summary?days=30").json()
    assert 0 <= s["readiness"]["score"] <= 100
    assert s["readiness"]["components"]["hrv"] is not None
    assert 0 <= s["sleep_score"]["score"] <= 100
    assert s["domains"]["sleep"]["last_night_h"] == pytest.approx(6.6)
    assert s["domains"]["heart"]["rhr"] is not None
    assert s["domains"]["heart"]["hrv"] is not None
    assert s["domains"]["activity"]["steps_today"] > 0
    assert s["domains"]["body"]["spo2"] == pytest.approx(0.97)
    assert len(s["domains"]["heart"]["spark"]) == 30
    assert s["exercise_week"]["minutes"] == pytest.approx(25 * 7)


def test_summary_empty_db_degrades_gracefully(client):
    s = client.get("/api/summary?days=30").json()
    assert s["readiness"]["score"] is None
    assert s["sleep_score"]["score"] is None
    assert s["domains"]["sleep"]["last_night_h"] is None


def test_summary_resolves_metric_aliases(client, conn):
    # importer writes heart_rate_variability_sdnn; HAE writes heart_rate_variability
    dd = days_back(40)
    seed(conn, "heart_rate_variability_sdnn", [(d, 45) for d in dd])
    s = client.get("/api/summary?days=30").json()
    assert s["domains"]["heart"]["hrv"] == pytest.approx(45)
