"""Streaming importer for Apple Health export.zip (multi-hundred-MB safe).

Uses ElementTree.iterparse and clears elements as it goes; sleep stage records
are aggregated into per-night rows keyed by wake-up date.
"""

import json
import re
import zipfile
from collections import defaultdict
from datetime import datetime
from xml.etree.ElementTree import iterparse

import db

JOBS: dict[str, dict] = {}

_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")

STAGE_VALUES = {
    "HKCategoryValueSleepAnalysisAsleepDeep": "deep_h",
    "HKCategoryValueSleepAnalysisAsleepCore": "core_h",
    "HKCategoryValueSleepAnalysisAsleepREM": "rem_h",
    "HKCategoryValueSleepAnalysisAwake": "awake_h",
}

BATCH = 5000


def _snake(hk_type: str) -> str:
    for prefix in ("HKQuantityTypeIdentifier", "HKCategoryTypeIdentifier", "HKDataType"):
        if hk_type.startswith(prefix):
            hk_type = hk_type[len(prefix):]
            break
    return _CAMEL.sub("_", hk_type).lower()


def _dt(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S %z")


def _hours(start: str, end: str) -> float:
    return (_dt(end) - _dt(start)).total_seconds() / 3600


def run_import(job_id: str, path: str):
    """Parse an export.zip (or bare export.xml) at `path` into the DB."""
    job = JOBS[job_id] = {"status": "running", "parsed": 0, "counts": {}}
    conn = db.connect()
    try:
        counts = _parse(conn, path, job)
        counts["routes"] = _attach_routes(conn, path)
        db.log_ingest(
            conn,
            datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z"),
            "import",
            sum(counts.values()),
            json.dumps(counts),
        )
        job.update(status="done", counts=counts)
    except Exception as e:  # surfaced to the UI, not raised into the void
        job.update(status="error", error=str(e))
    finally:
        conn.close()


def _open_xml(path: str):
    if zipfile.is_zipfile(path):
        z = zipfile.ZipFile(path)
        name = next(n for n in z.namelist() if n.endswith("export.xml"))
        return z.open(name)
    return open(path, "rb")


def _parse(conn, path, job):
    samples, workouts = [], 0
    # nights[date] = {stage: hours, start_ts, end_ts}
    nights = defaultdict(lambda: {v: 0.0 for v in STAGE_VALUES.values()})
    flushed = 0

    with _open_xml(path) as f:
        root = None
        for event, el in iterparse(f, events=("start", "end")):
            if event == "start":
                if root is None:
                    root = el
                continue
            if el.tag == "Record":
                t = el.get("type", "")
                if t == "HKCategoryTypeIdentifierMindfulSession":
                    # no numeric value; the duration is the datum
                    end = el.get("endDate")
                    minutes = _hours(el.get("startDate"), end) * 60
                    samples.append(
                        ("mindful_minutes", end, round(minutes, 2), "min",
                         el.get("sourceName", ""))
                    )
                elif t == "HKCategoryTypeIdentifierSleepAnalysis":
                    stage = STAGE_VALUES.get(el.get("value", ""))
                    if stage:
                        end = el.get("endDate")
                        night = nights[end[:10]]
                        night[stage] += _hours(el.get("startDate"), end)
                        night.setdefault("start_ts", el.get("startDate"))
                        night["end_ts"] = end
                else:
                    try:
                        value = float(el.get("value"))
                    except (TypeError, ValueError):
                        el.clear()
                        continue
                    samples.append(
                        (
                            _snake(t),
                            el.get("endDate"),
                            value,
                            el.get("unit", ""),
                            el.get("sourceName", ""),
                        )
                    )
            elif el.tag == "Workout":
                _import_workout(conn, el)
                workouts += 1
            else:
                continue  # keep children of open Workout elements intact
            job["parsed"] += 1
            # Records never nest inside Workouts, so clearing the root here
            # only drops already-processed siblings — keeps memory flat.
            root.clear()
            if len(samples) >= BATCH:
                db.upsert_samples(conn, samples)
                flushed += len(samples)
                samples = []

    db.upsert_samples(conn, samples)
    for date, n in sorted(nights.items()):
        db.upsert_sleep_night(
            conn,
            (
                date,
                n.get("start_ts"),
                n.get("end_ts"),
                round(n["deep_h"], 4),
                round(n["core_h"], 4),
                round(n["rem_h"], 4),
                round(n["awake_h"], 4),
                "import",
            ),
        )
    return {
        "samples": flushed + len(samples),
        "sleep_nights": len(nights),
        "workouts": workouts,
    }


def _import_workout(conn, el):
    wtype = el.get("workoutActivityType", "").removeprefix("HKWorkoutActivityType")
    start, end = el.get("startDate", ""), el.get("endDate", "")
    energy = distance = None
    for st in el.findall("WorkoutStatistics"):
        if st.get("type") == "HKQuantityTypeIdentifierActiveEnergyBurned":
            energy = float(st.get("sum", 0))
        elif st.get("type") == "HKQuantityTypeIdentifierDistanceWalkingRunning":
            distance = float(st.get("sum", 0))
    try:
        duration_s = float(el.get("duration", 0)) * 60  # durationUnit is minutes
    except ValueError:
        duration_s = None
    db.upsert_workout(
        conn,
        (
            f"{wtype}|{start}",
            wtype,
            start,
            end,
            duration_s,
            energy,
            distance,
            None,
            json.dumps(dict(el.attrib)),
            None,  # route attached after the XML pass (GPX files live beside it)
        ),
    )


MAX_ROUTE_POINTS = 500


def downsample(points, limit=MAX_ROUTE_POINTS):
    """Thin a point list to <= limit, always keeping first and last."""
    if len(points) <= limit:
        return points
    step = (len(points) - 1) / (limit - 1)
    return [points[round(i * step)] for i in range(limit)]


def _attach_routes(conn, path):
    """Parse workout-routes/*.gpx from the zip and attach each to the workout
    whose time window contains the route's first point. ponytail: linear scan
    per route — fine at personal scale (hundreds of workouts)."""
    if not zipfile.is_zipfile(path):
        return 0
    workouts = [
        (wid, _dt(s), _dt(e))
        for wid, s, e in conn.execute(
            "SELECT id, start_ts, end_ts FROM workouts"
        ).fetchall()
        if s and e
    ]
    attached = 0
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if "workout-routes/" not in name or not name.endswith(".gpx"):
                continue
            points, first_time = [], None
            with z.open(name) as f:
                for _, el in iterparse(f, events=("end",)):
                    if el.tag.endswith("}trkpt") or el.tag == "trkpt":
                        points.append([float(el.get("lat")), float(el.get("lon"))])
                        if first_time is None:
                            time_el = next(iter(el), None)
                            if time_el is not None and time_el.text:
                                first_time = datetime.fromisoformat(
                                    time_el.text.replace("Z", "+00:00")
                                )
                        el.clear()
            if not points or first_time is None:
                continue
            for wid, start, end in workouts:
                if start <= first_time <= end:
                    conn.execute(
                        "UPDATE workouts SET route_json = ? WHERE id = ?",
                        (json.dumps(downsample(points)), wid),
                    )
                    attached += 1
                    break
    conn.commit()
    return attached
