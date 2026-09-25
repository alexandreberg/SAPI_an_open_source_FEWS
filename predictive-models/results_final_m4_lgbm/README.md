# results_final_m4_lgbm

**Final validated backtesting for Model 4 — LightGBM (Darts).**

Previously named `real_data_v3_continuous/`. This is the reference implementation used to
validate the production M4 model configuration, and the source of the M4 numbers published
in the dissertation. The M6 counterpart is [`../results_final_m6_mlr/`](../results_final_m6_mlr/).

## Scripts

| Script | Purpose |
|---|---|
| `config.py` | Hyper-parameters, thresholds (60/75/90 cm), train/test split (`TRAIN_END = 2026-05-01`) and paths — mirrored in `production/config_production.py` |
| `real_utils.py` | Data loading and preprocessing utilities |
| `01_model4_continuous.py` | Continuous backtest over the full record (2024-12-30 → 2026-09-12, ~21 months); auto-detects 25 Atenção-crossing periods |
| `02_precip_gate_analysis.py` | Sensitivity analysis for 5/10/15 mm precipitation gates |
| `04_lead_time_m4.py` | Lead time (advance warning) per event, threshold crossing and horizon |
| `lead_time_utils.py` | The single implementation of the lead-time rule, shared with M6 and the audit report |
| `05_event_catalogue.py` | Timeline figure of the catalogued events (`output/event_catalogue.png`) |
| `06_event_comparison_plots.py` | Per-event M4/M6 figures for the four test-set Inundação events (E31, E33, E35, E37) |

## Event catalogue

`event_windows_v3.csv` (E01–E37) is the catalogue used for training and testing: **37 episodes,
of which 28 are valid events** and 9 are excluded as sensor artifacts (Issue #227). The
chronological split at `TRAIN_END = 2026-05-01` gives 17 train / 11 test events. It is built
by [`../build_event_catalogue.py`](../build_event_catalogue.py). The earlier hand-curated
20-event catalogue (`event_windows_v2.csv`) is archived in the
development repository and feeds nothing.

## Output images (`output/`)

- `alert_timeline_atencao.png` / `alert_timeline_alerta.png` / `alert_timeline_inundacao.png`
  — full monitoring period with predicted alerts overlaid on observed level
- `precip_gate_timeline_[level]_gate[5/10/15]mm.png` — 9 images showing the gate effect
- `lead_time_[level]_m4.png` — lead time per level
- `event_catalogue.png` — the catalogue on the level series
- `event_detected_001.png` … `event_detected_025.png` — forecast vs actual per auto-detected period

## Auto-detected period → catalogued event mapping

Each `event_detected_NNN.png` is the *N*th Atenção-threshold-crossing period (observed level
≥ 60 cm) found in chronological order while scanning the full continuous backtest, with
crossings less than `EVENT_MERGE_GAP_MIN = 120 min` apart merged and 2 h of padding on each
side (`detect_flood_periods()` in `01_model4_continuous.py`). Its number has no fixed
relationship to the catalogue's `E01`–`E37` numbering: a period is mapped to every catalogued
event whose `[analysis_start, analysis_end]` window overlaps it. The same periods apply to the
identically numbered plots of `results_final_m6_mlr/`, since both scripts run
`detect_flood_periods()` over the same observed level, threshold and merge gap.

This table was regenerated on 2026-09-24 by running `detect_flood_periods()` on
`output/continuous_predictions.csv` and overlapping the result with `event_windows_v3.csv`
(it replaces the older table, which described 41 periods against the superseded v2 catalogue
and the 50/60/75 cm thresholds):

| `event_detected_NNN.png` | Detected period (UTC) | Catalogued event(s) |
|---|---|---|
| `001` | 2025-01-17 04:10 → 2025-01-17 21:25 | E01 (Alerta) |
| `002` | 2025-01-25 21:15 → 2025-01-26 05:05 | E02 (Atenção) |
| `003` | 2025-04-10 16:40 → 2025-04-11 06:40 | E04 (Inundação) |
| `004` | 2025-12-09 12:05 → 2025-12-09 21:40 | E08 (Inundação) |
| `005` | 2025-12-29 20:35 → 2025-12-30 03:50 | E10 (Inundação) |
| `006` | 2026-01-18 21:25 → 2026-01-19 04:10 | E18 (Atenção) |
| `007` | 2026-01-30 09:45 → 2026-01-30 14:00 | — |
| `008` | 2026-01-30 15:30 → 2026-01-30 19:45 | — |
| `009` | 2026-02-02 17:35 → 2026-02-02 21:50 | — |
| `010` | 2026-02-04 23:35 → 2026-02-05 03:50 | — |
| `011` | 2026-02-25 02:10 → 2026-02-25 10:00 | E20 (Atenção) |
| `012` | 2026-03-20 03:40 → 2026-03-20 09:50 | E22 (Atenção) |
| `013` | 2026-03-20 10:25 → 2026-03-20 14:30 | E22 (Atenção) |
| `014` | 2026-04-07 06:55 → 2026-04-07 18:20 | E25 (Alerta) |
| `015` | 2026-04-08 01:00 → 2026-04-08 13:20 | E25 (Alerta) |
| `016` | 2026-06-20 19:30 → 2026-06-20 23:35 | E28 (Atenção) |
| `017` | 2026-06-30 07:55 → 2026-06-30 19:35 | E29 (Atenção) |
| `018` | 2026-07-01 10:15 → 2026-07-01 16:45 | E30 (Atenção) |
| `019` | 2026-07-11 10:00 → 2026-07-12 08:55 | E31 (Inundação) |
| `020` | 2026-08-12 14:30 → 2026-08-13 05:20 | E32 (Alerta) |
| `021` | 2026-08-13 22:10 → 2026-08-16 12:40 | E33 (Inundação) |
| `022` | 2026-08-29 12:35 → 2026-08-29 22:50 | E34 (Alerta) |
| `023` | 2026-08-29 21:20 → 2026-08-30 07:05 | E34 (Alerta) |
| `024` | 2026-08-30 11:40 → 2026-09-01 20:55 | E35 (Inundação) |
| `025` | 2026-09-11 13:00 → 2026-09-12 10:55 | E37 (Inundação) |

- **19 catalogued events have no detected period.** Ten are `Normal` events — the observed
  peak stays below the 60 cm Atenção threshold, so no detection is *supposed* to happen
  (E03, E05, E06, E07, E11, E12, E24, E26, E27, E36) — and nine are the sensor-artifact
  episodes excluded in Issue #227 (E09, E13, E14, E15, E16, E17, E19, E21, E23), whose windows
  are blanked out of the series.
- **`012`/`013`, `014`/`015` and `022`/`023` are not duplicates.** Each pair is two separate
  threshold-crossing spells inside one catalogued event, further apart than the 120 min merge
  gap; the 2 h padding can make their windows overlap (`022`/`023`).
- **`007`–`010` have no catalogued event.** Each is a brief crossing — only 4 steps (20 min)
  at or above 60 cm, peaking between 66 and 72 cm — that the catalogue segmentation, which
  works on amplitude over a trailing baseline, did not keep as an episode.

## Key results

- Continuous backtest over the full record (2024-12-30 → 2026-09-12): 25 auto-detected
  threshold-crossing periods, distinct from the 37 catalogued episodes (28 valid) used for the
  train/test split — see Issue #213 for why the two counts differ.
- `GATE_MM_OPERATIONAL = 5 mm / 6 h`, persistence filter of 3 consecutive steps (15 min).
- Thresholds: Atenção = 60 cm, Alerta = 75 cm, Inundação = 90 cm (recalibrated 2026-09-09,
  Issue #225).
- The published RMSE and lead-time numbers are **out of sample** (test period from
  2026-05-01). For the figures and tables the dissertation uses, see
  the dissertation and the audit report `../output_audit/auditoria_eventos_A3.pdf`.

## Related

- Production config: `../production/config_production.py`
- M6 comparison: `../results_final_m6_mlr/`
