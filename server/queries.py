"""Daily series, rolling normal-range bands, and the dashboard summary."""

from datetime import date, datetime, timedelta
from statistics import mean, stdev

import scores

# counters are summed per day; everything else is averaged
SUM_METRICS = {
    "step_count",
    "active_energy_burned",
    "active_energy",
    "basal_energy_burned",
    "apple_exercise_time",
    "flights_climbed",
    "distance_walking_running",
    "walking_running_distance",
    "mindful_session",
}

# canonical name → acceptable stored names (HAE and export.xml differ)
ALIASES = {
    "hrv": ["heart_rate_variability", "heart_rate_variability_sdnn"],
    "rhr": ["resting_heart_rate"],
    "steps": ["step_count"],
    "exercise": ["apple_exercise_time", "exercise_time"],
    "wrist_temp": ["apple_sleeping_wrist_temperature", "sleeping_wrist_temperature"],
    "spo2": ["oxygen_saturation", "blood_oxygen_saturation"],
    "respiratory": ["respiratory_rate"],
}

BAND_WINDOW = 30
BAND_K = 1.5


def rolling_band(values, window=BAND_WINDOW, k=BAND_K):
    """Trailing mean ± k·sd per point (window includes the point)."""
    band = []
    for i in range(len(values)):
        chunk = values[max(0, i - window + 1): i + 1]
        m = mean(chunk)
        sd = stdev(chunk) if len(chunk) >= 2 else 0.0
        band.append((m - k * sd, m + k * sd))
    return band


def daily_series(conn, metric, days, end=None):
    """[(date, value)] per day, summed or averaged by metric kind."""
    end = end or date.today()
    start = (end - timedelta(days=days - 1)).isoformat()
    agg = "SUM" if metric in SUM_METRICS else "AVG"
    rows = conn.execute(
        f"""SELECT substr(ts, 1, 10) AS day, {agg}(value) FROM samples
            WHERE metric = ? AND day >= ? AND day <= ?
            GROUP BY day ORDER BY day""",
        (metric, start, end.isoformat()),
    ).fetchall()
    return [(r[0], round(r[1], 4)) for r in rows]


def resolve(conn, canonical):
    """First alias that has any data, else the primary alias."""
    for name in ALIASES[canonical]:
        row = conn.execute(
            "SELECT 1 FROM samples WHERE metric = ? LIMIT 1", (name,)
        ).fetchone()
        if row:
            return name
    return ALIASES[canonical][0]


def series_with_band(conn, metric, days):
    pts = daily_series(conn, metric, days)
    band = rolling_band([v for _, v in pts])
    return [
        {"date": d, "value": v, "lo": round(lo, 4), "hi": round(hi, 4)}
        for (d, v), (lo, hi) in zip(pts, band)
    ]


def _values(pts):
    return [v for _, v in pts]


def _spark(pts, days):
    """Last `days` daily values (no padding — frontend scales what exists)."""
    return _values(pts)[-days:]


def _bedtime_offset_min(nights):
    """Tonight's bedtime vs median of the previous 14, in minutes (None if unknown)."""
    starts = [n for n in nights if n[1]]
    if len(starts) < 3:
        return None

    def minutes(ts):
        t = datetime.strptime(ts[:19], "%Y-%m-%d %H:%M:%S")
        m = t.hour * 60 + t.minute
        return m if m >= 12 * 60 else m + 24 * 60  # map past-midnight after evening

    prev = sorted(minutes(n[1]) for n in starts[-15:-1])
    if not prev:
        return None
    median = prev[len(prev) // 2]
    return minutes(starts[-1][1]) - median


def summary(conn, days, last_sync_row):
    hrv_m, rhr_m = resolve(conn, "hrv"), resolve(conn, "rhr")
    horizon = 90  # enough history for 60-day baselines regardless of view range

    hrv_pts = daily_series(conn, hrv_m, horizon)
    rhr_pts = daily_series(conn, rhr_m, horizon)
    steps_pts = daily_series(conn, resolve(conn, "steps"), horizon)
    exercise_pts = daily_series(conn, resolve(conn, "exercise"), horizon)
    temp_pts = daily_series(conn, resolve(conn, "wrist_temp"), horizon)
    spo2_pts = daily_series(conn, resolve(conn, "spo2"), horizon)

    nights = conn.execute(
        """SELECT date, start_ts, end_ts, deep_h, core_h, rem_h, awake_h
           FROM sleep_nights ORDER BY date DESC LIMIT 90"""
    ).fetchall()
    nights = nights[::-1]
    sleep_hours = [n[3] + n[4] + n[5] for n in nights]  # asleep = deep+core+rem

    def latest(pts):
        return pts[-1][1] if pts else None

    readiness = scores.readiness(
        hrv=latest(hrv_pts), hrv_hist=_values(hrv_pts)[-60:],
        rhr=latest(rhr_pts), rhr_hist=_values(rhr_pts)[-60:],
        sleep_h=sleep_hours[-1] if sleep_hours else None,
        sleep_hist=sleep_hours[-60:],
    )
    last = nights[-1] if nights else None
    sleep = scores.sleep_score(
        duration_h=sleep_hours[-1] if sleep_hours else None,
        deep_h=last[3] if last else None,
        rem_h=last[5] if last else None,
        bedtime_offset_min=_bedtime_offset_min(nights),
    ) or {"score": None}

    temp_base = mean(_values(temp_pts)[-30:]) if temp_pts else None
    return {
        "last_sync": last_sync_row,
        "readiness": readiness,
        "sleep_score": sleep,
        "exercise_week": {
            "minutes": round(sum(_values(exercise_pts)[-7:])),
            "spark": _spark(exercise_pts, days),
        },
        "domains": {
            "sleep": {
                "last_night_h": round(sleep_hours[-1], 2) if sleep_hours else None,
                "score": sleep["score"],
                "spark": [round(h, 2) for h in sleep_hours[-days:]],
            },
            "heart": {
                "rhr": latest(rhr_pts),
                "hrv": latest(hrv_pts),
                "spark": _spark(hrv_pts, days),
            },
            "activity": {
                "steps_today": latest(steps_pts),
                "spark": _spark(steps_pts, days),
            },
            "body": {
                "temp_dev": (
                    round(latest(temp_pts) - temp_base, 2)
                    if temp_pts and temp_base is not None
                    else None
                ),
                "spo2": latest(spo2_pts),
                "spark": _spark(temp_pts, days),
            },
        },
    }
