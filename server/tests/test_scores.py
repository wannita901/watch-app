"""Score formulas — pure functions, synthetic data with known z-scores."""

import pytest

import scores


def test_z_score_basic():
    hist = [50.0] * 9 + [60.0]  # mean 51, sd ~3
    z = scores.z(60.0, hist)
    assert z == pytest.approx((60 - 51) / scores._sd(hist), abs=1e-6)


def test_readiness_all_at_baseline_is_50():
    hist = [50.0, 52.0, 48.0, 51.0, 49.0] * 6
    r = scores.readiness(
        hrv=sum(hist) / len(hist), hrv_hist=hist,
        rhr=sum(hist) / len(hist), rhr_hist=hist,
        sleep_h=sum(hist) / len(hist), sleep_hist=hist,
    )
    assert r["score"] == 50


def test_readiness_good_hrv_low_rhr_raises_score():
    flat = [50.0, 52.0, 48.0, 51.0, 49.0] * 6
    r = scores.readiness(hrv=60, hrv_hist=flat, rhr=44, rhr_hist=flat,
                         sleep_h=50, sleep_hist=flat)
    assert r["score"] > 60


def test_readiness_clamped_0_100():
    flat = [50.0, 52.0, 48.0, 51.0, 49.0] * 6
    hi = scores.readiness(hrv=500, hrv_hist=flat, rhr=1, rhr_hist=flat,
                          sleep_h=500, sleep_hist=flat)
    lo = scores.readiness(hrv=1, hrv_hist=flat, rhr=500, rhr_hist=flat,
                          sleep_h=1, sleep_hist=flat)
    assert hi["score"] == 100 and lo["score"] == 0


def test_readiness_missing_hrv_skips_term_and_flags_component():
    flat = [50.0, 52.0, 48.0, 51.0, 49.0] * 6
    r = scores.readiness(hrv=None, hrv_hist=[], rhr=50, rhr_hist=flat,
                         sleep_h=50, sleep_hist=flat)
    assert r["score"] == 50
    assert r["components"]["hrv"] is None


def test_readiness_needs_minimum_history():
    r = scores.readiness(hrv=50, hrv_hist=[50.0] * 3, rhr=None, rhr_hist=[],
                         sleep_h=None, sleep_hist=[])
    assert r["components"]["hrv"] is None  # < MIN_HISTORY days → no z


def test_sleep_score_perfect_night():
    s = scores.sleep_score(duration_h=8.0, deep_h=1.3, rem_h=1.7, bedtime_offset_min=0)
    assert s["score"] == 100


def test_sleep_score_short_night_scores_lower():
    s = scores.sleep_score(duration_h=5.0, deep_h=0.8, rem_h=1.0, bedtime_offset_min=0)
    assert 40 < s["score"] < 85


def test_sleep_score_late_bedtime_penalised():
    on_time = scores.sleep_score(8.0, 1.3, 1.7, bedtime_offset_min=0)
    late = scores.sleep_score(8.0, 1.3, 1.7, bedtime_offset_min=120)
    assert late["score"] < on_time["score"]


def test_sleep_score_none_duration_returns_none():
    assert scores.sleep_score(None, None, None, None) is None
