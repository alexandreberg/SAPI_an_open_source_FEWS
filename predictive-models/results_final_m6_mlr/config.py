# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2024–2026 Alexandre Nuernberg <alexandreberg@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
"""
@file config.py
@brief Configuration for M6 DARTS LinearRegressionModel continuous backtesting.

All hyper-parameters that appear also in results_final_m4_lgbm/config.py are
kept **identical** so that M4 and M6 share the same input features, preprocessing
pipeline, thresholds, gate, and debounce logic.  The only difference is the model
class (LinearRegressionModel vs LightGBMModel).

EVENTS_CSV points to results_final_m4_lgbm/event_windows_v2.csv — the shared
event catalogue is not duplicated.
"""

import os
import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

DATA_DIR = "/home/ilha3d/SAPI/data"
"""Root directory containing the real measurement CSVs."""

_HERE = os.path.dirname(os.path.abspath(__file__))
_V3_DIR = os.path.join(_HERE, "..", "results_final_m4_lgbm")

OUTPUT_DIR = os.path.join(_HERE, "output")
"""Output directory for plots and metrics."""

LEVEL_CSV = os.path.join(DATA_DIR, "station01_level_gapfilled.csv")
"""Reprocessed from raw level_cm via
../reprocess_level_spike_return_filter.py (Issue #211), then gap-filled from
Station-03 via ../build_gapfilled_level.py (Issue #225) — see those scripts'
module docstrings and
Documentation/predictive_model/auditoria_lead_time_rmse_20eventos.md.
Same file used by results_final_m4_lgbm/config.py."""

LEVEL_PROVENANCE_CSV = os.path.join(DATA_DIR, "station01_level_gapfilled.csv")
"""Same file as LEVEL_CSV, read for its `source` column when evaluation needs
to know which samples came from Station-03 rather than Station-01."""
MERGE_CSV = os.path.join(DATA_DIR, "merge_20260404.csv")
"""Historical MERGE precipitation archive (2025-01-01 → 2026-04-04).
The rolling 7-day cache (merge_precip.csv) only covers recent data and cannot
reach the 2025 training events E1/E4/E7/E8 — this archive is used instead."""
STATION02_CSV = os.path.join(DATA_DIR, "station02_precip.csv")

EVENTS_CSV = os.path.join(_V3_DIR, "event_windows_v3.csv")
"""Shared event catalogue from results_final_m4_lgbm/ — not duplicated."""

# ---------------------------------------------------------------------------
# Pre-processing (identical to results_final_m4_lgbm)
# ---------------------------------------------------------------------------

RESAMPLE_MIN = 5
"""Target time resolution in minutes (5-min grid)."""

GAP_FILL_MAX_MIN = 15
"""Maximum gap (minutes) filled by linear interpolation; longer gaps stay NaN."""

LEVEL_MIN_CM = 25
"""Physical noise floor: readings below this value are clipped."""

LEVEL_MAX_CM = 250
"""Physical ceiling: readings above this value are clipped (sensor fault)."""

LEVEL_MAX_DELTA = 40
"""Delta-filter threshold: |v − prev_clean| > this (cm) flags a spike."""

PRECIP_CUTOFF = pd.Timestamp("2026-01-02", tz="UTC")
"""Splice point: before this date MERGE precipitation is used; from this date
Station-02 tipping-bucket data is used."""

STATION02_REPORT_STEPS = 3
"""Station-02 reports the rain accumulated over its ~15-min sleep cycle, so one
report spans 15 / RESAMPLE_MIN = 3 five-minute steps (Issue #124). Each
report's total is spread evenly over the step it lands in and the next two —
forward only, so rain never appears before the instant it was transmitted.
Summing it into a single step instead left a sawtooth (one wet step, two dry)
that made the forecasts jump on every report. Identical to
results_final_m4_lgbm/config.py."""

PRECIP_MERGE_SCALE = 1.0
"""Multiplicative bias correction applied to MERGE precipitation before the
splice (Issue #223 ablation arm).

The dissertation's cross-validation found MERGE underestimating Station-02 by
-29.8% on daily totals, i.e. MERGE ~ 0.702 x Station-02, so the neutralising
factor is 1/0.702 = 1.42 (NOT 1.29 — that would under-correct by ~10 points).

Kept at 1.0 by default and exercised as an explicit ablation rather than
folded into the baseline, because: (a) the monthly ratio behind the -29.8%
figure ranges from -9.5% to -75.6%, so a single scalar is a coarse summary;
(b) it would be derived from Jan-Jun/2026 and applied retroactively to 2025,
where no Station-02 exists to verify the bias is stationary; and (c) it does
not address the train/test mismatch of #2.4.1 in the audit report, which is
about SHAPE (MERGE is hourly ffill/12, structurally smooth) rather than
magnitude. The argument in favour is consistency: with continuous training
spanning the splice, a systematic 29.8% step makes the same physical rainfall
map to two different feature values."""

# ---------------------------------------------------------------------------
# Training-set composition (Issue #223)
# ---------------------------------------------------------------------------

TRAIN_MODE = "continuous"
"""How model.fit() is fed — "continuous" (default) or "events".

"events" is the historical behaviour: fit only on the catalogued windows with
split_set == "train". That makes the training sample 100% flood episodes
(1,598 five-minute steps, mean level 54.9 cm, 67.4% above the Atencao
threshold) while inference then runs over the whole record (133,445 steps,
mean 35.8 cm, 1.8% above threshold) — a case-control selection bias. With the
lags unable to constrain the answer at long horizons, the forecast regresses
to that flood-shaped training prior: at +120 min M4 forecast >= 50 cm in 75.2%
of all steps (observed: 1.8%) and averaged 85.6 cm with the channel dry.

"continuous" fits on an unbroken period of record — floods AND dry weather —
so the training and inference populations match. Out-of-sample this took the
+120 min RMSE from 34.51 to 2.46 cm (M4) and 14.34 to 2.84 cm (M6) while
preserving the in-event response. Both modes are kept so the dissertation can
report the comparison. See Issue #223 and
Documentation/predictive_model/lead_time_horizontes_longos_investigacao.md."""

TRAIN_END = pd.Timestamp("2026-05-01")
"""Chronological train/test cut used when TRAIN_MODE == "continuous".

Training spans the start of the record up to this instant; events entirely
after it are the out-of-time test set, events entirely before it are training,
and any event straddling the cut is excluded so no test event shares data with
training.

The split is chronological, not by event, because in a time series the test
must come after the training: with continuous training every event before the
cut is in-sample, and its metrics would be optimistic (M4 +30 min RMSE 0.63 cm
in-sample vs 1.05 cm out-of-sample, 2026-09-11).

2026-05-01 (moved from 2026-02-01 in Issue #225, when the record was extended
to 2026-09-09) keeps BOTH precipitation regimes in training — MERGE before the
2026-01-02 splice and ~4 months of native Station-02 after it — while the
out-of-time test set (May–Sep/2026) holds 9 events, including the three most
recent Inundação events (E31, E33, E35). First test event: E27 (2026-05-09).
By time, ~79 % of the 5-min steps are training and ~21 % test. A walk-forward
evaluation (several successive cuts) would use more events as test without
leakage — possible future work. See
Documentation/predictive_model/artefatos_catalogo_v3.md."""

# ---------------------------------------------------------------------------
# Model horizons (identical to results_final_m4_lgbm)
# ---------------------------------------------------------------------------

HORIZONS_MIN = [30, 60, 90, 120]
"""Prediction horizons in minutes."""

HORIZON_STEP_IDX = {30: 5, 60: 11, 90: 17, 120: 23}
"""0-based step index within a 24-step output chunk for each horizon."""

OUTPUT_CHUNK_STEPS = 24
"""Simultaneous future steps predicted (24 × 5 min = 120 min)."""

# ---------------------------------------------------------------------------
# Alert thresholds (cm) — identical to results_final_m4_lgbm (Issue #99)
# ---------------------------------------------------------------------------

THRESHOLD_ATENCAO = 60
THRESHOLD_ALERTA = 75
THRESHOLD_INUNDACAO = 90

"""Alert thresholds recalibrated 2026-09-09 (Issue #225), from 50/60/75 cm.

The old values were set when the channel baseline sat near 35 cm. That baseline
is not stationary: Station-01's monthly median went from 29 cm (Jul/2025) to
45 cm (Jul/2026) and 47 cm (Sep/2026), so by Sep/2026 the old Atencao level of
50 cm was being exceeded 31% of the time — it had stopped separating an event
from normal flow.

The new set was chosen from the distribution of all 42 distinct episodes over
Dec/2024-Sep/2026, and deliberately lands on its natural discontinuities rather
than on round numbers:

    162, 101, 101, 98, 97 | 84, 79, 77, 75, 74 | 69 ... 60 | 59 ... 45
                          ^ 13 cm gap          ^ 5 cm gap

  Atencao   60 cm -> 23 events (16 train / 7 test), exceeded  9.0% of Sep/2026
  Alerta    75 cm ->  9 events ( 6 train / 3 test), exceeded  2.8% of Sep/2026
  Inundacao 90 cm ->  5 events ( 3 train / 2 test), exceeded  1.1% of Sep/2026

Atencao at 60 cm keeps 13 cm of margin over Station-01's Sep/2026 median.
Inundacao at 90 cm falls inside the 84->97 gap, so any value in 85-96 selects
the same five events; 90 was picked because it also coincides with the
operational alert system's own Atencao level, bridging this evaluation scale to
the deployed one.

These are FIXED thresholds, deliberately: a hydrometeorological station does
not move its alert levels between dry and wet years. The baseline drift is
documented as a limitation (Issue #225), not compensated for.

Thresholds can be changed without retraining. The models forecast level in cm;
these values are applied afterwards, where a forecast becomes an alert. Only
the evaluation scripts (04_lead_time_*, 05_rmse_per_event, the confusion
matrix) need re-running — the fitted model is untouched. That makes an
operator-facing control for these levels feasible: as the event history grows
and the empirical picture sharpens, the levels can be moved toward the real
alert stages without a new training cycle.

Reference station is Station-01 by seniority of record, NOT by metrological
quality. Station-01 is an HC-SR04 in trigger/echo mode with no temperature
compensation and no bench calibration; Station-03 is a US-100 in serial mode
with internal temperature compensation and a bench calibration curve, and is
the more accurate instrument of the two. Station-01 is the reference only
because it holds 20 months of record against Station-03's 6, which is the
period the models need. Station-03 reads about +2 cm higher for the same water
(same river, 30 m apart, correlation 0.93-0.98) — that is the calibration
difference between the two sensors, not a difference in river level."""

# ---------------------------------------------------------------------------
# Lead time per threshold-crossing occurrence (Issue #229, lead_time_utils.py)
# Identical to results_final_m4_lgbm/config.py.
# ---------------------------------------------------------------------------

REARM_HYSTERESIS_CM = 5.0
"""An observed up-crossing only counts as a new alert occurrence after the level
has fallen to threshold - REARM_HYSTERESIS_CM. See results_final_m4_lgbm/config.py."""

PRED_PERSISTENCE_STEPS = 3
"""Consecutive 5-min steps a forecast must stay at or above the threshold before
its alarm fires (15 min, same as the operational debounce). Lead time is
measured to the firing instant."""

CAUSALITY_MAX_LEAD_MIN = 180
"""Earliest pairing of a predicted alarm with an observed crossing, in minutes
before it. See lead_time_utils.py."""

# ---------------------------------------------------------------------------
# M6 — DARTS LinearRegressionModel hyper-parameters
#
# Deliberately identical to the LGBM_* constants in results_final_m4_lgbm/
# config.py so that M4 and M6 share the same lag feature structure and the only
# variable is the learning algorithm.
# ---------------------------------------------------------------------------

RANDOM_STATE = 42

MLR_LAGS = [-24, -18, -12, -9, -6, -3, -1]
"""Level lags in 5-min steps: −120, −90, −60, −45, −30, −15, −5 min.
Identical to LGBM_LAGS in results_final_m4_lgbm/config.py."""

MLR_PRECIP_LAGS = [-18, -12, -6, -1]
"""Past-covariate (precipitation) lags: −90, −60, −30, −5 min.
Identical to LGBM_PRECIP_LAGS in results_final_m4_lgbm/config.py."""

MLR_BUFFER_STEPS = max(abs(l) for l in MLR_LAGS)
"""Minimum history steps required before first prediction (= max |lag| = 24)."""

# ---------------------------------------------------------------------------
# Continuous simulation parameters (same as results_final_m4_lgbm)
# ---------------------------------------------------------------------------

WINDOW_STEPS = MLR_BUFFER_STEPS * 2
"""Sliding history window size in steps (48 × 5 min = 240 min = 4 hours)."""

DEBOUNCE_STEPS = [1, 2, 3]
"""Debounce scenarios tested (steps of 5 min each):
1 step  (5 min)  = Scenario A
2 steps (10 min) = Scenario B
3 steps (15 min) = Scenario C  ← operational choice from M4 analysis"""

EVENT_MERGE_GAP_MIN = 120
"""Maximum gap in minutes between detected flood steps to merge into one period."""
