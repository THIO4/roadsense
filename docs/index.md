# RoadSense driving conditions index

**Educational metric.** It is our own transparent scoring of Digitraffic road-weather sensor
values for a Cloud Engineering course project. It is *not* an official safety rating and must
not be used for real driving decisions.

## Method

Start at **100**, subtract penalties, clamp to 0..100. Implementation: `src/roadsense/index.py`.

| Factor | Source sensor | Penalty |
|---|---|---|
| Road condition | `KELI_1` code | Dry 0 · Moist 5 · Wet 10 · Wet & salty 10 · Probably moist & salty 5 · Slushy 30 · Frost 40 · Snow 40 · Ice 55 |
| Friction | `KITKA1` µ | ≥0.60: 0 · 0.45–0.60: 15 · 0.30–0.45: 30 · <0.30: 50 |
| Ice risk | `TIE_1` ≤ 1 °C **and** (moist/wet code or precipitation > 0) | 20 |
| Near freezing | `TIE_1` ≤ 1 °C, road dry | 10 |
| Precipitation | `SADE_INTENSITEETTI` mm/h | >0.5: 5 · >2: 15 · >5: 25 |
| Visibility | `NÄKYVYYS_M` | <1000 m: 10 · <500 m: 20 · <200 m: 30 |
| Wind | `KESKITUULI` m/s | >12: 10 · >17: 20 |
| Station warning | `VAROITUS_1` | Beware 10 · Alarm 20 · Frost 15 · Rain 5 |

Rules:
- **Road condition and friction measure the same thing** (surface grip), so only the *larger*
  of the two penalties applies - never both.
- **Missing sensors never penalise.** Absent is not bad. If neither road condition nor
  friction is available (or the condition sensor reports a fault, code 0), the index is
  `null` with band `unknown`.
- Every applied penalty is returned as a named factor, so any score can be explained.

## Bands

| Score | Band |
|---|---|
| 80–100 | good |
| 60–79 | fair |
| 40–59 | poor |
| 0–39 | hazardous |

## Limitations

Thresholds are round, defensible numbers chosen by reasoning, not calibrated against accident
data. Station sensors fault, freeze and drift. Observations are up to 30 minutes old.
