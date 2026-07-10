"""Seed a demo DB with 90 days of synthetic data for local UI development.

Usage: DB_PATH=/tmp/demo.db uv run python seed_demo.py
"""

import math
import random
from datetime import date, datetime, timedelta, timezone

import db

random.seed(42)


def main():
    conn = db.connect()
    today = date.today()
    days = [today - timedelta(days=i) for i in range(89, -1, -1)]
    samples = []
    rhr, hrv, temp = 52.0, 46.0, 35.1
    for d in days:
        rhr += (52.0 - rhr) * 0.2 + random.uniform(-0.8, 0.8)
        hrv += (46.0 - hrv) * 0.2 + random.uniform(-2.5, 2.5)
        temp += (35.1 - temp) * 0.2 + random.uniform(-0.08, 0.08)
        iso = d.isoformat()
        samples += [
            ("resting_heart_rate", f"{iso} 07:00:00 +1000", round(rhr, 1), "bpm", "demo"),
            ("heart_rate_variability", f"{iso} 07:00:00 +1000", round(hrv, 1), "ms", "demo"),
            ("step_count", f"{iso} 21:00:00 +1000", random.randint(4000, 13000), "count", "demo"),
            ("apple_exercise_time", f"{iso} 21:00:00 +1000", random.randint(0, 45), "min", "demo"),
            ("apple_sleeping_wrist_temperature", f"{iso} 07:00:00 +1000", round(temp, 2), "degC", "demo"),
            ("oxygen_saturation", f"{iso} 07:00:00 +1000", round(random.uniform(0.955, 0.99), 3), "%", "demo"),
            ("respiratory_rate", f"{iso} 07:00:00 +1000", round(random.uniform(13.5, 16.0), 1), "count/min", "demo"),
        ]
        bed_min = random.randint(-40, 55)
        start = f"{(d - timedelta(days=1)).isoformat()} {23 + bed_min // 60}:{abs(bed_min) % 60:02d}:00 +1000"
        db.upsert_sleep_night(
            conn,
            (
                iso,
                start,
                f"{iso} 07:0{random.randint(0, 9)}:00 +1000",
                round(random.uniform(0.7, 1.5), 2),
                round(random.uniform(3.2, 4.6), 2),
                round(random.uniform(1.0, 2.0), 2),
                round(random.uniform(0.1, 0.6), 2),
                "demo",
            ),
        )
        samples += [
            ("environmental_audio_exposure", f"{iso} 12:00:00 +1000", round(random.uniform(55, 78), 1), "dBASPL", "demo"),
            ("headphone_audio_exposure", f"{iso} 15:00:00 +1000", round(random.uniform(50, 72), 1), "dBASPL", "demo"),
        ]
        if random.random() < 0.4:
            samples.append(("mindful_minutes", f"{iso} 08:10:00 +1000", random.choice([5, 10, 12]), "min", "demo"))

    # a few workouts, most recent with a route + in-workout HR
    import json as _json

    for k, d in enumerate(days[-14::4]):
        iso = d.isoformat()
        start, end = f"{iso} 18:00:00 +1000", f"{iso} 18:42:00 +1000"
        route = [
            [-37.85 + 0.002 * math.sin(i / 8), 145.115 + 0.0012 * i]
            for i in range(40)
        ]
        for m in range(0, 42, 2):
            samples.append(
                ("heart_rate", f"{iso} 18:{m:02d}:30 +1000",
                 round(140 + 18 * math.sin(m / 6) + random.uniform(-4, 4)), "bpm", "demo")
            )
        db.upsert_workout(
            conn,
            (f"Running|{start}", "Running", start, end, 42 * 60.0,
             round(random.uniform(320, 400)), round(random.uniform(4.8, 5.6), 2),
             152.0, "{}", _json.dumps(route)),
        )

    db.upsert_samples(conn, samples)
    db.log_ingest(
        conn,
        datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S +0000"),
        "ingest",
        len(samples),
        "demo seed",
    )
    print(f"seeded {len(samples)} samples, {len(days)} nights into {db.db_path()}")
    conn.close()


if __name__ == "__main__":
    main()
