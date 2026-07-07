"""Seed a demo DB with 90 days of synthetic data for local UI development.

Usage: DB_PATH=/tmp/demo.db uv run python seed_demo.py
"""

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
