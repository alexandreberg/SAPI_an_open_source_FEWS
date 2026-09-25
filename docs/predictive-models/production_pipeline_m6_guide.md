# SAPI M6 MLR — Production Pipeline Guide

**Issue**: #120  
**Status**: Implemented 2026-05-16 — pending deployment  
**Branch**: `feature/issue-120-mlr-m6-production`

---

## What the system does

Every 5 minutes (offset 2 min from M4), the Raspberry Pi runs the M6 MLR pipeline in **parallel** with M4 LightGBM:

1. Fetches the latest water level and precipitation from Hostinger via HTTPS (same API endpoints as M4)
2. Runs the trained M6 `LinearRegressionModel` to predict water level at **+30, +60, +90 and +120 minutes**
3. Checks the **precipitation gate** (≥ 5 mm / 6 h — identical to M4)
4. Applies **debounce** (3 consecutive steps = 15 min before firing — identical to M4)
5. Posts results to `/sapi/api/predictions_m6.php` → stored in `predictions_m6` table
6. On `fired` / `cleared` transitions: sends Telegram + email notifications with "M6 MLR" label

Results are visible at **https://ilha3d.com/sapi/predictions.php** as an orange dashed line overlaid on the M4 purple line.

---

## Isolation from M4

| Resource | M4 LightGBM | M6 MLR |
|---|---|---|
| RPi folder | `/home/ilha3d/SAPI/LightGBM_Production/` | `/home/ilha3d/SAPI/MLR_Production/` |
| Source folder (repo) | `production/` | `production_m6/` |
| Model file | `models/model4_lgbm.pkl` | `models/model6_mlr.pkl` |
| State file | `state/debounce_state.json` | `state/debounce_state_m6.json` |
| Last-run log | `logs/ultima_predicao.log` | `logs/ultima_predicao_m6.log` |
| API endpoint | `/sapi/api/predictions.php` | `/sapi/api/predictions_m6.php` |
| DB table (predictions) | `predictions` | `predictions_m6` |
| DB table (alerts) | `prediction_alerts` | `prediction_alerts_m6` |
| Python venv | `/home/ilha3d/SAPI/LightGBM_Production/.venv` | **shared** (same venv, same packages) |

Disabling M6 (remove or comment the cron line) has zero impact on M4.

---

## Architecture

```
Raspberry Pi (cron */5 * * * *, offset 2 min after M4)
│   sleep 120 && python3 /home/ilha3d/SAPI/MLR_Production/sapi_predict_m6.py
│
├── GET https://ilha3d.com/sapi/api/data.php  (level, precip — same as M4)
│
├── Load model6_mlr.pkl (LinearRegressionModel, trained on E1/E4/E7/E8)
│
├── For each station (1, 3):
│   ├── Pre-process: resample 5-min → delta filter → gap-fill → ffill (NaN-fill for LinearRegression)
│   ├── model.predict(n=24) → h_pred_{30, 60, 90, 120}
│   ├── Gate: rolling_precip_6h >= 5 mm
│   ├── Debounce: state/debounce_state_m6.json
│   ├── POST https://ilha3d.com/sapi/api/predictions_m6.php
│   └── If fired/cleared → telegram_notifier_m6.notify_alert() + email
│
└── Write logs/ultima_predicao_m6.log

Hostinger
├── api/predictions_m6.php    — receives M6 results, sends email
├── DB: predictions_m6        — one row per 5-min run per station
└── DB: prediction_alerts_m6  — M6 alert state transitions
```

---

## Key difference from M4: NaN handling

`LinearRegressionModel` (sklearn MultiOutputRegressor internally) cannot route NaN values in lag feature windows — unlike LightGBM which handles them natively in tree splits.

**Fix applied in `inference_m6.py`** (before `model.predict()`):
```python
df_filled = ts_level.to_dataframe().ffill().bfill()
ts_level  = TimeSeries.from_dataframe(df_filled, freq="5min")
```

Same fill is applied in `train_production_model_m6.py` for training segments.

---

## File locations

### Raspberry Pi — production runtime (deploy manually)

| Path | Description |
|------|-------------|
| `/home/ilha3d/SAPI/MLR_Production/` | Root production directory |
| `sapi_predict_m6.py` | Cron entry point |
| `config_production_m6.py` | Constants (MLR_LAGS, thresholds, gate, paths) |
| `api_client_m6.py` | HTTPS GET/POST client (posts to predictions_m6.php) |
| `inference_m6.py` | Pre-processing + LinearRegressionModel + gate |
| `state_m6.py` | Debounce state persistence |
| `telegram_notifier_m6.py` | Telegram chart + notifications (M6 labels) |
| `train_production_model_m6.py` | One-time training script |
| `models/model6_mlr.pkl` | Trained model (small — KB range) — backed up at [GitHub Release `model6-mlr-v2.0.0`](https://github.com/alexandreberg/SAPI_an_open_source_FEWS/releases/tag/model6-mlr-v2.0.0) (release assets: see docs/PROVENANCE.md) |
| `config/api_key.txt` | Same RPi API key as M4 (copy from M4 config/) |
| `config/telegram_config.json` | Same Telegram config as M4 (copy from M4 config/) |
| `state/debounce_state_m6.json` | Per-station debounce counters (M6-specific) |
| `logs/sapi_predict_m6.log` | Full cron log |
| `logs/ultima_predicao_m6.log` | Last-run summary |

### Raspberry Pi — source code (repo)

```
predictive-models/production_m6/
├── config_production_m6.py
├── api_client_m6.py
├── inference_m6.py
├── state_m6.py
├── sapi_predict_m6.py
├── telegram_notifier_m6.py
├── train_production_model_m6.py
└── requirements_production_m6.txt
```

### Hostinger

| Path | Description |
|------|-------------|
| `public_html/sapi/api/predictions_m6.php` | POST endpoint for RPi M6 results |
| `public_html/sapi/predictions.php` | Public web dashboard (shows M4 + M6) |
| `migration_m6_mlr.sql` | DB migration (predictions_m6, prediction_alerts_m6) |

---

## Deployment steps (one-time)

### 1. Run DB migration (Hostinger phpMyAdmin or SSH)

```bash
mysql -u USER -p DBNAME < webserver/migration_m6_mlr.sql
```

### 2. Upload Hostinger files

```bash
scp -P 65002 webserver/public_html/sapi/api/predictions_m6.php \
    <HOSTINGER_USER>@hostinger:~/public_html/sapi/api/

scp -P 65002 webserver/public_html/sapi/predictions.php \
    <HOSTINGER_USER>@hostinger:~/public_html/sapi/
```

### 3. Deploy RPi scripts

```bash
mkdir -p /home/ilha3d/SAPI/MLR_Production/{models,state,config,logs}

cp predictive-models/production_m6/*.py \
    /home/ilha3d/SAPI/MLR_Production/

# NOTE (2026-09-12): the event_windows_v2.csv copy that used to go here is obsolete.
# Training no longer reads it — see "Re-training the model" below.

# Copy secrets from M4 (same key and Telegram config)
cp /home/ilha3d/SAPI/LightGBM_Production/config/api_key.txt \
    /home/ilha3d/SAPI/MLR_Production/config/
cp /home/ilha3d/SAPI/LightGBM_Production/config/telegram_config.json \
    /home/ilha3d/SAPI/MLR_Production/config/
chmod 600 /home/ilha3d/SAPI/MLR_Production/config/*.txt \
          /home/ilha3d/SAPI/MLR_Production/config/*.json
```

### 4. Train the model

> **2026-09-12:** `train_production_model_m6.py` is deprecated — see "Re-training the
> model" at the end of this document. The command below is kept only as the historical
> record of how the 2026-05-16 model was produced.

```bash
/home/ilha3d/SAPI/LightGBM_Production/.venv/bin/python3 \
    /home/ilha3d/SAPI/MLR_Production/train_production_model_m6.py
```

Training is fast (seconds vs ~2 min for M4's 500 trees). Expected output:
```
  M6 MLR (LinearRegressionModel) — Production Training
  [1/3] Loading historical data ...
  [2/3] Building training segments ... 4 segments
  [3/3] Training LinearRegressionModel ...
  Model saved → .../models/model6_mlr.pkl  (NNN KB)
```

### 5. Publish a model release

After training (step 4) or any retraining, publish a `model6-mlr-vX.Y.Z` tag + GitHub
Release with the updated `model6_mlr.pkl` and a fresh data-snapshot `.tar.gz`, per the
"Production Release Procedure" (see docs/PROVENANCE.md). This is the only backup of the model
file outside the RPi's local disk.

### 6. Add cron entry (offset 2 min from M4)

```bash
crontab -e
```

Add:
```
*/5 * * * * sleep 120 && /home/ilha3d/SAPI/LightGBM_Production/.venv/bin/python3 /home/ilha3d/SAPI/MLR_Production/sapi_predict_m6.py >> /home/ilha3d/SAPI/MLR_Production/logs/sapi_predict_m6.log 2>&1
```

---

## Verification

```bash
# 1. Run manually and check output
/home/ilha3d/SAPI/LightGBM_Production/.venv/bin/python3 \
    /home/ilha3d/SAPI/MLR_Production/sapi_predict_m6.py

# 2. Check last-run summary
cat /home/ilha3d/SAPI/MLR_Production/logs/ultima_predicao_m6.log

# 3. Check DB row was inserted (Hostinger phpMyAdmin)
SELECT * FROM predictions_m6 ORDER BY timestamp DESC LIMIT 5;

# 4. Open web dashboard
# https://ilha3d.com/sapi/predictions.php
# → orange dashed line (M6 MLR) appears alongside purple line (M4)
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `M6 model not found` | `model6_mlr.pkl` missing | Run `train_production_from_backtest.py --model m6`, then promote (see below) |
| `POST FAILED` | Wrong endpoint or key | Check `api/predictions_m6.php` is uploaded; verify API key file |
| `predict() failed` — NaN error | NaN slipped through ffill | Check `build_level_series` returned enough non-NaN rows (need ≥ 24) |
| M6 line missing on web | `predictions_m6` table empty | Run cron manually once; check log for errors |
| M6 line shows old data | Cron not running | `crontab -l | grep sapi_predict_m6` |

---

## Re-training the model

**Do not use `train_production_model_m6.py`.** Deprecated on 2026-09-12: it trains on flood
windows only (Issue #223), reads the v2 event catalogue, applies no sensor-artifact mask
(Issue #227) and does not spread the Station-02 reports (Issue #124).

Training runs through the same code that produced the published results:

```bash
cd predictive-models
V=/home/ilha3d/SAPI/LightGBM_Production/.venv/bin/python3
$V train_production_from_backtest.py --model m6     # ~1 min
$V production/test_precip_parity.py                 # must PASS before promoting
```

Output goes to a staging path — `models/model6_mlr_v2.pkl` plus a `.meta.json` carrying the
input hashes, library versions and hyper-parameters. Promote with an explicit rename:

```bash
cd /home/ilha3d/SAPI/MLR_Production/models
mv model6_mlr.pkl model6_mlr_v1_20260516.pkl
mv model6_mlr_v2.pkl model6_mlr.pkl
```

The next cron run picks it up within 5 min; rollback is the reverse rename. The accepted
train/serve differences (level filter, Station-01/03 gap fill) are documented in
`production_pipeline_guide.md`.

---

*Created: 2026-05-16 | Issue #120 | Branch: feature/issue-120-mlr-m6-production*
