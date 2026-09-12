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
@file config_production.py
@brief Production configuration for the SAPI real-time M4 LightGBM prediction pipeline.

All runtime paths are under PRODUCTION_DIR.  The model is trained once by
train_production_model.py and then loaded by sapi_predict.py on every cron run.

Constants here mirror the backtesting config (results_final_m4_lgbm/config.py)
so the production model is identical to the validated one.
"""

import os

# ---------------------------------------------------------------------------
# Runtime paths (on Raspberry Pi)
# ---------------------------------------------------------------------------

PRODUCTION_DIR = "/home/ilha3d/SAPI/LightGBM_Production"
"""Root directory for all production artefacts (gitignored at runtime)."""

MODEL_PATH      = os.path.join(PRODUCTION_DIR, "models", "model4_lgbm.pkl")
"""Serialised Darts LightGBMModel — written by train_production_model.py."""

STATE_PATH      = os.path.join(PRODUCTION_DIR, "state", "debounce_state.json")
"""JSON file persisting per-station debounce counters across cron runs."""

LOG_LAST_PRED   = os.path.join(PRODUCTION_DIR, "logs", "ultima_predicao.log")
"""Human-readable summary of the most recent prediction run (overwritten each run)."""

API_KEY_FILE    = os.path.join(PRODUCTION_DIR, "config", "api_key.txt")
"""Plain-text file containing the RPi prediction API key (chmod 600, gitignored)."""

TELEGRAM_CONFIG_PATH = os.path.join(PRODUCTION_DIR, "config", "telegram_config.json")
"""JSON file with bot_token and chat_ids for Telegram alerts (Issue #110, chmod 600, gitignored).
See AppTest/webserver/private_configs/sapi/telegram_config-sample.json for the expected format."""

# Historical CSVs — same source used for offline backtesting.
DATA_DIR        = "/home/ilha3d/SAPI/data"
LEVEL_CSV       = os.path.join(DATA_DIR, "station01_level.csv")
MERGE_CSV       = os.path.join(DATA_DIR, "merge_precip.csv")
STATION02_CSV   = os.path.join(DATA_DIR, "station02_precip.csv")

# Event windows CSV (for training split — copy stored alongside production scripts).
EVENTS_CSV = os.path.join(PRODUCTION_DIR, "event_windows_v2.csv")

# ---------------------------------------------------------------------------
# Hostinger API
# ---------------------------------------------------------------------------

API_BASE_URL    = "https://ilha3d.com/sapi/api"
"""Base URL for the SAPI Hostinger REST API. Note: sapi.ilha3d.com only redirects
browser navigation; use the canonical domain for programmatic API calls."""
"""Base URL for the SAPI Hostinger REST API (no trailing slash)."""

API_TIMEOUT_S   = 15
"""HTTP request timeout in seconds."""

# ---------------------------------------------------------------------------
# Pre-processing (identical to results_final_m4_lgbm)
# ---------------------------------------------------------------------------

RESAMPLE_MIN     = 5
GAP_FILL_MAX_MIN = 15
LEVEL_MIN_CM     = 25
LEVEL_MAX_CM     = 250
LEVEL_MAX_DELTA  = 40

import pandas as pd
PRECIP_CUTOFF = pd.Timestamp("2026-01-02", tz="UTC")
"""Switch point: before this date MERGE is used; from this date Station-02 is used."""

STATION02_REPORT_STEPS = 3
"""Number of 5-min steps each Station-02 report is spread over (Issue #124).

The tipping-bucket transmits an accumulated total every 15 min.  Dropping that total into
a single 5-min slot followed by two zeros made the forecasts jump at every transmission.
The total is instead split evenly across the step it arrives in and the two that follow.
The spread is forward-only, so rain never appears before the instant it was transmitted,
and the total is conserved exactly.

MUST match `STATION02_REPORT_STEPS` in the backtest config used for training
(results_final_m4_lgbm/config.py) — the model is trained on the spread series, so it has
to be served the spread series."""

# ---------------------------------------------------------------------------
# Model hyper-parameters (identical to results_final_m4_lgbm)
# ---------------------------------------------------------------------------

RESAMPLE_MIN       = 5
HORIZONS_MIN       = [30, 60, 90, 120]
HORIZON_STEP_IDX   = {30: 5, 60: 11, 90: 17, 120: 23}
OUTPUT_CHUNK_STEPS = 24

RANDOM_STATE       = 42

LGBM_LAGS          = [-24, -18, -12, -9, -6, -3, -1]
LGBM_PRECIP_LAGS   = [-18, -12, -6, -1]
LGBM_BUFFER_STEPS  = max(abs(l) for l in LGBM_LAGS)   # = 24 steps = 2 h
LGBM_N_ESTIMATORS  = 500
LGBM_NUM_LEAVES    = 31

# ---------------------------------------------------------------------------
# Alert thresholds (cm) per station — same for both until field-tuned
# ---------------------------------------------------------------------------

STATIONS = [1, 3]
"""Station IDs to run predictions for."""

THRESHOLDS = {
    1: {"atencao": 60, "alerta": 75, "inundacao": 90},
    3: {"atencao": 60, "alerta": 75, "inundacao": 90},
}
"""Model-evaluation thresholds in cm, recalibrated from 50/60/75 in Issue #225.

Station-01's monthly median level rose from 29 cm (Jul/2025) to 47 cm (Sep/2026) — about
18 cm in 14 months, corroborated by Station-03 — so the old 50 cm was being exceeded 31 %
of the time and no longer separated an event from normal flow.  The new values sit on the
natural gaps of the 42-episode peak distribution (13 cm between 84 and 97 cm, 5 cm between
69 and 74 cm).  Inundacao at 90 cm deliberately coincides with the *operational* Atencao
level, bridging the model scale and the field alert scale.

These are the thresholds the FORECAST is classified against.  The observed-level alert
system is separate and unaffected: `alert_rules` / `check_alerts.php` stay at 90/110/130 cm.

Changing a threshold does NOT require retraining — the models forecast level in cm and the
threshold is applied afterwards, where a forecast becomes an alert."""
"""Per-station thresholds in cm.  Station-03 starts equal to Station-01;
adjust after at least one field event is observed."""

# ---------------------------------------------------------------------------
# Gate + debounce
# ---------------------------------------------------------------------------

GATE_MM          = 5.0
"""Minimum 6-hour rolling precipitation (mm) to activate the prediction gate."""

GATE_WINDOW_MIN  = 360
"""Rolling window for precipitation gate (6 h = 72 steps at 5-min resolution)."""

DEBOUNCE_STEPS   = 3
"""Number of consecutive 5-min steps a raw alert must persist before firing."""

# ---------------------------------------------------------------------------
# Data fetch windows
# ---------------------------------------------------------------------------

LEVEL_FETCH_HOURS   = 4
"""Hours of level history to fetch from the API for live inference.
2 h covers the buffer + a safety margin."""

PRECIP_FETCH_HOURS  = 7
"""Hours of Station-02 precip to fetch (covers the 6 h gate window + margin)."""

MERGE_FALLBACK_HOURS = 11
"""Hours of MERGE CSV lookback when Station-02 is offline (5 h MERGE delay + 6 h gate)."""

MIN_PRECIP_ROWS      = 10
"""Minimum Station-02 rows in the fetch window; fewer triggers MERGE fallback."""
