# Apple Watch Health Web Dashboard — Deep Research Report
*Generated: 2026-07-07 | Sources: ~60 (web, GitHub API, Apple docs) | Confidence: High on architecture, Medium on undocumented sampling internals*

## Executive Summary

Apple provides **no web/cloud API for HealthKit** — health data lives on-device (E2E-encrypted in iCloud), so every web dashboard needs something running on the iPhone to push data out. The community-standard pipeline is the **Health Auto Export** iOS app ($24.99 lifetime) POSTing JSON to a self-hosted REST endpoint, plus a one-time **export.zip** parse for historical backfill. Realistic data freshness is minutes-to-hours while the phone is in use, with overnight gaps (iOS blocks Health reads while locked). All major Apple Watch metrics are reachable: HR, HRV, sleep stages, workouts + GPS, VO2max, SpO2, respiratory rate, wrist temperature, ECG waveforms — but Apple-derived scores (Sleep Score, Vitals classifications, hypertension analysis) are largely **not** third-party readable; only their inputs are. No polished open-source dashboard occupies this niche — nearest neighbors are Grafana stacks and 2-commit hobby projects — so building a custom single-user dashboard is both necessary and unencumbered. For personal use, HIPAA does not apply and GDPR's household exemption covers it, provided the dashboard is not publicly accessible.

---

## 1. What data is available (HealthKit catalog)

### Cardiovascular
| Metric | Identifier | Granularity |
|---|---|---|
| Heart rate (background) | `heartRate` | ~every 3–10 min at rest (motion-dependent, undocumented) |
| Heart rate (workout) | `heartRate` | every few seconds, continuous |
| Resting HR / Walking HR avg | `restingHeartRate`, `walkingHeartRateAverage` | 1/day |
| HRV (SDNN) | `heartRateVariabilitySDNN` | sporadic — handful/day; reliable only via Breathe sessions and sleep; triggers undocumented (Altini) |
| RR intervals | `HKHeartbeatSeriesSample` | beat-to-beat, around HRV windows |
| ECG | `HKElectrocardiogram` | on-demand, 30 s single-lead @ ~512 Hz, full voltage waveform readable |
| VO2max | `vo2Max` | estimated from outdoor walk/run/hike workouts |
| AFib History | category | weekly burden % (requires diagnosis) |

Raw PPG optical signal is NOT exposed — only derived HR/HRV/RR.

### Respiratory / temperature / sleep
- **SpO2** (`oxygenSaturation`): on-demand + background readings day/night. US Masimo saga resolved: feature re-enabled Aug 2025 via iPhone-side computation; ITC closed case Apr 2026, no import ban. Samples land in HealthKit either way.
- **Respiratory rate**: during sleep only.
- **Wrist temperature** (`appleSleepingWristTemperature`): one nightly aggregate vs ~5-night baseline (Series 8+).
- **Sleep stages** (`sleepAnalysis`): Awake/REM/Core/Deep interval samples, watchOS 9+.
- **Breathing Disturbances** (`appleSleepingBreathingDisturbances`): nightly, iOS 18.1+, third-party readable.

### Activity
Steps, distance, flights, active/basal energy, exercise minutes, stand hours (= the three rings), walking metrics, `HKWorkout` with GPS routes (`HKWorkoutRoute`) and HR series. `workoutEffortScore` (iOS 18) readable.

### Newer features (watchOS 11 / 26)
- Vitals app (overnight out-of-range detection), Training Load, sleep-apnea notifications (watchOS 11).
- Hypertension notifications (FDA-cleared, shipped Sept 2025, Series 9+), Sleep Score 0–100 (watchOS 26).
- **Caveat:** Apple-computed scores/classifications (Sleep Score, Vitals ranges, Training Load class, hypertension internals) are largely NOT exposed as readable HealthKit types. Inputs are readable; recompute scores yourself if needed.

### Key constraints
- Per-type read permissions; denial is **undetectable** (queries return empty, not errors).
- Background delivery capped per type (steps: hourly at best; workouts: immediate); no delivery while phone locked.
- Watch-only data: continuous HR, HRV, ECG, SpO2, resp rate, wrist temp, sleep stages, VO2max, noise. iPhone alone: steps/distance/basic sleep.

## 2. Getting data out (pathway comparison)

| Pathway | Freshness | Coverage | Cost | Risk |
|---|---|---|---|---|
| **Health Auto Export → REST** | minutes–hours while phone in use; overnight gaps | 150+ metrics incl. sleep phases, ECG, GPS | $24.99 lifetime | low-med (indie, active since 2016, updated Jun 2026; open payload spec, many receivers) |
| **export.zip + parser** | manual only | complete history | free | low (stable XML schema; healthkit-to-sqlite frozen 2021, apple-health-parser fresher) |
| **Custom iOS app (HKObserverQuery + background delivery)** | immediate (workouts) to hourly (steps); works without unlock ritual | anything, per-type code | $99/yr dev account (free account = 7-day re-sign treadmill) | high — 1–3 wk part-time build + ongoing churn |
| **Shortcuts → webhook** | daily / few-hourly; fails when locked | ~3–5 metrics practically | free | brittle |
| **Terra / Junction / Spike / Thryve** | near-real-time, but you still must build an SDK iOS app | broad | $99–499+/mo, B2B minimums | skip for personal use |

**Recommended:** export.zip backfill once + Health Auto Export Premium POSTing hourly-aggregated JSON to a small receiver (FastAPI/Go). Upgrade to custom companion app only if freshness-while-locked matters.

Key iOS restriction (applies to HAE and Shortcuts): Health data readable only while device unlocked; automations rely on Background App Refresh, ~30 s execution budget, not guaranteed timing. Large payloads (GPS workouts) can get killed — use batching.

## 3. Existing open-source landscape (GitHub, checked 2026-07-07)

Active:
- **open-wearables** (the-momentum, 2.1k★, MIT, FastAPI+Postgres+React): self-hosted multi-wearable API platform with own HealthKit SDKs — API platform, not a personal charts UI.
- **apple-health-grafana** (k0rventen, 573★): export.zip → InfluxDB → 4 Grafana dashboards. Snapshot, not live.
- **health-auto-export-server** (HealthyApps, 150★): official HAE receiver, Node+MongoDB+Grafana. No license file.
- **health-dashboard** (andreugordillovazquez, 25★): fully client-side React 19, upload export.zip in browser, 18 tabs, zero network egress — strong privacy reference design.
- **apple-health-dashboard** (nixfred, 8★): Bun+SQLite receiver for HAE, 13+ charts (sleep heatmap, wrist-temp anomaly, recovery score). 2 commits, no auth, no tests.

Dead/dormant: healthkit-to-sqlite (2023), healthlake (archived), healthdata_influx (2022), several one-offs.

**Gap:** no maintained single-user web dashboard with built-in auth. Common patterns: (A) batch export→InfluxDB→Grafana for history; (B) HAE→small receiver→time-series DB→charts for live. Prometheus is a poor fit (push vs pull); use SQLite/Postgres/InfluxDB.

## 4. Feature bar from commercial apps

- **Athlytic / Training Today:** Recovery/Readiness 0–100 from overnight HRV + resting HR vs rolling personal baseline (e.g., 24 h HRV vs 60-day baseline); Exertion/training-load vs recovery-adjusted target.
- **Gyroscope:** composite health score, multi-source aggregation, AI coach.
- **Bevel:** readiness + strain + sleep depth + nutrition panels.
- Recurring vocabulary: baseline-deviation scores, 7/30/90-day trends, sleep-stage composition + consistency, plain-language daily guidance. All computable from raw HealthKit fields the pipeline already carries.

## 5. Privacy / legal

- **HIPAA:** not applicable — binds covered entities/business associates only (HHS guidance).
- **GDPR:** household exemption (Art. 2(2)(c)) covers purely personal use; fails if dashboard made publicly accessible or gains professional/economic connection. Health data = Art. 9 special category if GDPR ever attaches — keep it private and single-user.
- **Security posture:** prefer LAN-only or Tailscale/WireGuard over public exposure; if exposed, TLS + auth via reverse proxy (Caddy/Authelia); require API key header on the ingest endpoint (HAE supports custom headers); treat GPS workout routes as most sensitive (home-location inference); encrypt backups.

## Key Takeaways

1. Architecture is forced: iPhone-side pusher → self-hosted receiver → DB → web UI. No Apple cloud API exists.
2. Health Auto Export ($25 lifetime) + export.zip backfill = 90% of the value at 5% of the effort of a custom iOS app.
3. Expect hourly-ish freshness with overnight gaps; design the dashboard for daily-granularity insight, not real-time monitoring.
4. Recompute recovery/readiness/sleep scores from raw inputs; Apple's own scores are not readable.
5. Keep it LAN/VPN-private → legal exposure is negligible.

## Methodology

3 parallel research agents, ~25 tool calls each, 2024–2026 sources prioritized. Sub-questions: (1) HealthKit metric catalog + constraints + sampling granularity; (2) export pathways + freshness + cost; (3) open-source dashboard landscape (GitHub API live star/commit data) + commercial feature bar + privacy. Uncertainty flags retained inline. Full per-agent findings with complete inline citations available in session transcripts; headline sources: developer.apple.com HealthKit docs, support.apple.com, healthyapps.dev docs, GitHub API, HHS.gov, gdpr-info.eu, MacRumors/9to5Mac (Masimo timeline), Marco Altini (HRV internals).
