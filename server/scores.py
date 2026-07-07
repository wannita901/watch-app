"""Readiness and sleep score formulas.

All tunable constants live in CONFIG — retune here, never in query code.
Readiness = 50 + weighted z-scores of today's values vs the trailing baseline.
"""

from statistics import mean, stdev

CONFIG = {
    "min_history": 7,        # days of history required before a z-score counts
    "w_hrv": 25.0,           # higher HRV than usual → readier
    "w_rhr": -15.0,          # higher RHR than usual → less ready
    "w_sleep": 10.0,         # more sleep than usual → readier
    "z_cap": 3.0,            # winsorise extreme z-scores
    "sleep_target_h": 8.0,
    "deep_rem_target_frac": 0.35,
    "bedtime_grace_min": 45,  # no penalty within ±45 min of habitual bedtime
    "bedtime_zero_min": 135,  # consistency component hits 0 here
}


def _sd(values):
    return stdev(values) if len(values) >= 2 else 0.0


def z(value, history):
    """Winsorised z-score of value vs history; None if not computable."""
    if value is None or len(history) < CONFIG["min_history"]:
        return None
    sd = _sd(history)
    if sd == 0:
        return 0.0
    raw = (value - mean(history)) / sd
    return max(-CONFIG["z_cap"], min(CONFIG["z_cap"], raw))


def readiness(hrv, hrv_hist, rhr, rhr_hist, sleep_h, sleep_hist):
    components = {
        "hrv": z(hrv, hrv_hist),
        "rhr": z(rhr, rhr_hist),
        "sleep": z(sleep_h, sleep_hist),
    }
    if all(v is None for v in components.values()):
        return {"score": None, "components": components}
    score = 50.0
    for key, weight in (("hrv", "w_hrv"), ("rhr", "w_rhr"), ("sleep", "w_sleep")):
        if components[key] is not None:
            score += CONFIG[weight] * components[key]
    return {"score": round(max(0.0, min(100.0, score))), "components": components}


def sleep_score(duration_h, deep_h, rem_h, bedtime_offset_min):
    """0–100: 50 duration + 30 restorative stage fraction + 20 bedtime consistency."""
    if not duration_h:
        return None
    duration_pts = 50.0 * min(duration_h / CONFIG["sleep_target_h"], 1.0)

    restorative = (deep_h or 0) + (rem_h or 0)
    stage_pts = 30.0 * min(
        (restorative / duration_h) / CONFIG["deep_rem_target_frac"], 1.0
    )

    if bedtime_offset_min is None:
        consistency = 1.0  # unknown habitual bedtime → don't penalise
    else:
        over = max(0.0, abs(bedtime_offset_min) - CONFIG["bedtime_grace_min"])
        span = CONFIG["bedtime_zero_min"] - CONFIG["bedtime_grace_min"]
        consistency = max(0.0, 1.0 - over / span)
    return {"score": round(duration_pts + stage_pts + 20.0 * consistency)}
