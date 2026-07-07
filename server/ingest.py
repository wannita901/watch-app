"""Parse Health Auto Export REST payloads into the DB.

Tolerant by design: a point we can't interpret goes to raw_points verbatim,
never dropped — field names are confirmed against a real device at deploy.
"""

import json

import db

SLEEP_METRICS = {"sleep_analysis"}
STAGE_KEYS = {"deep": "deep_h", "core": "core_h", "rem": "rem_h", "awake": "awake_h"}


def _num(v):
    """HAE encodes quantities as numbers or {'qty': n, 'units': u}."""
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, dict) and isinstance(v.get("qty"), (int, float)):
        return float(v["qty"])
    return None


def _ingest_metric(conn, metric, samples, raws, sleeps):
    name, units = metric.get("name", "unknown"), metric.get("units", "")
    for point in metric.get("data", []):
        ts = point.get("date")
        if not ts:
            raws.append((name, "", json.dumps(point)))
            continue
        if name in SLEEP_METRICS and any(k in point for k in STAGE_KEYS):
            date = (point.get("sleepEnd") or ts)[:10]
            sleeps.append(
                (
                    date,
                    point.get("sleepStart"),
                    point.get("sleepEnd") or ts,
                    *(float(point.get(k) or 0) for k in STAGE_KEYS),
                    point.get("source", ""),
                )
            )
        elif (qty := _num(point.get("qty"))) is not None:
            samples.append((name, ts, qty, units, point.get("source", "")))
        elif _num(point.get("Avg")) is not None:
            src = point.get("source", "")
            samples.append((name, ts, _num(point["Avg"]), units, src))
            for k, suffix in (("Min", "_min"), ("Max", "_max")):
                if (v := _num(point.get(k))) is not None:
                    samples.append((name + suffix, ts, v, units, src))
        else:
            raws.append((name, ts, json.dumps(point)))


def _ingest_workout(conn, w):
    start, end = w.get("start", ""), w.get("end", "")
    wid = f"{w.get('name', 'workout')}|{start}"
    duration_min = _num(w.get("duration"))
    db.upsert_workout(
        conn,
        (
            wid,
            w.get("name"),
            start,
            end,
            duration_min * 60 if duration_min is not None else None,
            _num(w.get("activeEnergyBurned")),
            _num(w.get("distance")),
            _num(w.get("avgHeartRate")),
            json.dumps(w),
        ),
    )


def ingest_payload(conn, payload, now_ts):
    data = payload.get("data", {})
    samples, raws, sleeps = [], [], []
    for metric in data.get("metrics", []):
        _ingest_metric(conn, metric, samples, raws, sleeps)

    db.upsert_samples(conn, samples)
    for night in sleeps:
        db.upsert_sleep_night(conn, night)
    conn.executemany(
        "INSERT OR REPLACE INTO raw_points (metric, ts, json) VALUES (?,?,?)", raws
    )
    workouts = data.get("workouts", [])
    for w in workouts:
        _ingest_workout(conn, w)

    counts = {
        "samples": len(samples),
        "sleep_nights": len(sleeps),
        "workouts": len(workouts),
        "raw_points": len(raws),
    }
    db.log_ingest(conn, now_ts, "ingest", sum(counts.values()), json.dumps(counts))
    return counts
