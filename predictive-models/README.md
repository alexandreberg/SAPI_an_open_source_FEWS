# predictive-models

Darts-based predictive models for SAPI — M4 (LightGBM) and M6 (multiple linear
regression) — plus the data pipeline that feeds them and the production deployment.

## Directory structure

| Path | Purpose | Status |
|---|---|---|
| `config.py` | Shared paths and constants for the data pipeline below | **Active** |
| `build_event_catalogue.py` | Segments the level series into episodes → `event_windows_v3.csv` | **Active** |
| `build_gapfilled_level.py` | Fills Station-01 outages from Station-03 (Issue #225) | **Active** |
| `reprocess_level_spike_return_filter.py` | Three-pass level filter (Issue #211) | **Active** |
| `train_production_from_backtest.py` | Trains the **deployed** models through the backtest code path | **Active** |
| `replay_flood_event.py` | Replays a past flood through two models, step by step | **Active** |
| `plot_events_audit_pdf.py` | A3 audit report, two pages per catalogued event | **Active** |
| `scan_audit_findings.py` | Calibration scan and audit checks | **Active** |
| `results_final_m4_lgbm/` | **M4 backtest** — the numbers published in the dissertation | **Reference** |
| `results_final_m6_mlr/` | **M6 backtest** — same, plus the M4-vs-M6 comparison | **Reference** |
| `production/` | **M4 production** (inference, alert state, Telegram) | **Deployed** |
| `production_m6/` | **M6 production** | **Deployed** |
| `output_audit/` | Generated audit PDF | Output |
Superseded code and experiments (the `legacy/` folder of the development repository) are not
published here. If a script or document points at a version of the catalogue or of the
thresholds that does not match this table, it is outdated.

## Two different event counts — read this first

This directory reports two unrelated numbers, both current and correct:

- **37 catalogued episodes**, of which **28 are valid events**
  (`results_final_m4_lgbm/event_windows_v3.csv`, E01–E37) — segmented by amplitude over a
  trailing baseline, then classified against the fixed 60/75/90 cm thresholds. Nine are
  excluded as sensor artifacts (Issue #227). The chronological split at
  `TRAIN_END = 2026-05-01` gives **17 train / 11 test**, with four Inundação events in the
  test set: E31, E33, E35 and E37.
- **25 auto-detected periods** (`event_detected_001.png` … `event_detected_025.png`) — the
  output of a threshold-crossing detector run over the continuous backtest, with no relation
  to the catalogue's boundaries. See Issue #213 for the investigation of why the two counts
  differ.

## Data pipeline

Run in this order after a new database dump. The dump is read directly, with no database
connection, by `../predictive_model/00_load_sql_dump.py`:

```bash
V=/home/ilha3d/SAPI/LightGBM_Production/.venv/bin/python3

# 1. dump → raw CSVs (uses the predictive_model venv, which has dotenv + matplotlib)
(cd ../predictive_model && DATA_DIR=/home/ilha3d/SAPI/data ./.venv/bin/python3 \
    00_load_sql_dump.py /home/ilha3d/SAPI/DB/<dump>.sql)

# 2. three-pass filter — ALWAYS pass --dump, the default is a pinned older file
$V reprocess_level_spike_return_filter.py --dump /home/ilha3d/SAPI/DB/<dump>.sql
$V build_gapfilled_level.py
$V build_event_catalogue.py          # compare against the previous catalogue before accepting

# 3. backtests
(cd results_final_m6_mlr  && $V 01_model6_mlr_continuous.py)   # ~5 min
(cd results_final_m4_lgbm && $V 01_model4_continuous.py)       # ~40 min

# 4. metrics and report
(cd results_final_m4_lgbm && $V 04_lead_time_m4.py && $V 02_precip_gate_analysis.py)
(cd results_final_m6_mlr  && $V 04_lead_time_m6.py && $V 05_rmse_per_event.py \
                          && $V 06_compare_fullsim.py && $V 03_compare_m4_m6.py)
$V scan_audit_findings.py --calibration
$V plot_events_audit_pdf.py
```

Two traps worth knowing, both of which fail **silently**:

- `DEFAULT_DUMP` in `plot_events_audit_pdf.py` is a pinned path, imported by the filter and
  used by `scan_audit_findings.py` (which has no `--dump` flag). A stale value produces a
  record truncated at the old dump's last timestamp, with no error. `load_raw_level` now
  warns when it detects this.
- `/home/ilha3d/SAPI/data/merge_precip.csv` is a **rolling** file rewritten nightly with
  about six days of rain. Training must use the frozen `merge_20260404.csv`.

## Production

Both models run on this Raspberry Pi via cron, every 5 minutes, M6 offset by 2 minutes:

- M4 → `/home/ilha3d/SAPI/LightGBM_Production/`
- M6 → `/home/ilha3d/SAPI/MLR_Production/`

Training is **not** done by the scripts inside `production/` — those are deprecated. Use
`train_production_from_backtest.py`, which runs the same code that produced the published
results. Full procedure in [`docs/predictive-models/production_pipeline_guide.md`](../docs/predictive-models/production_pipeline_guide.md)
(M6: [`production_pipeline_m6_guide.md`](../docs/predictive-models/production_pipeline_m6_guide.md)).

## Where the current numbers live

The dissertation is authoritative, and its numbers come from the audit report
[`output_audit/auditoria_eventos_A3.pdf`](output_audit/auditoria_eventos_A3.pdf) and the
`results_final_*` folders. Thresholds and catalogue: [`docs/predictive-models/limiares_e_catalogo_v3.md`](../docs/predictive-models/limiares_e_catalogo_v3.md).
