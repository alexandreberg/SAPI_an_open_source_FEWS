# SAPI M4 LightGBM — Production Pipeline Guide

**Issue**: #108  
**Status**: Operational since 2026-05-10  
**Branch merged**: `feature/issue-108-realtime-prediction` → PR #109

---

## What the system does

Every 5 minutes, the Raspberry Pi:

1. Fetches the latest water level and precipitation from the Hostinger database via HTTPS
2. Runs the trained M4 LightGBM model to predict the water level at **+30, +60, +90 and +120 minutes** ahead
3. Checks whether the **precipitation gate** is active (≥ 5 mm in the last 6 hours)
4. Applies a **debounce filter** (requires 3 consecutive alert steps = 15 min before firing)
5. Posts the result back to Hostinger for storage and web visualisation
6. On `fired` / `cleared` transitions: sends a **Telegram notification** with a chart image (Issue #110)

The prediction results are visible at **https://ilha3d.com/sapi/predictions.php** and update automatically every 5 minutes.

---

## Architecture

```
Raspberry Pi (cron */5 min)
│
├── GET https://ilha3d.com/sapi/api/data.php
│       station_id=1, field=level,  hours=4  → level_delta_cm (Station-01)
├── GET https://ilha3d.com/sapi/api/data.php
│       station_id=3, field=level,  hours=4  → level_delta_cm (Station-03)
├── GET https://ilha3d.com/sapi/api/data.php
│       station_id=2, field=precip, hours=7  → precipitation_mm (Station-02)
│       └── fallback: local /home/ilha3d/SAPI/data/merge_precip.csv (11 h window)
│
├── Load model4_lgbm.pkl (24 MB, trained on events E1/E4/E7/E8)
│
├── For each station (1, 3):
│   ├── Pre-process: resample 5-min → delta filter → gap-fill → Darts TimeSeries
│   ├── model.predict(n=24) → h_pred_{30, 60, 90, 120}
│   ├── Gate: rolling_precip_6h >= 5 mm → gate_active
│   │         Precipitation source priority (per run):
│   │           1. Station-02 API (field=precip) — if ≥ 10 rows
│   │           2. MERGE/GPM API  (field=merge)  — if Station-02 offline
│   │           3. Local merge_precip.csv         — if Hostinger unreachable
│   │           4. Zero series                    — absolute last resort
│   ├── Debounce: consecutive_steps counter (state/debounce_state.json)
│   ├── POST https://ilha3d.com/sapi/api/predictions.php
│   └── If fired/cleared → telegram_notifier.notify_alert()
│           fired  → sendPhoto (chart image: last 2h level + 4 horizons + thresholds)
│           cleared → sendMessage (text summary)
│
└── Write logs/ultima_predicao.log (last-run summary, overwritten each run)

Hostinger
├── api/data.php           — serves sensor data to the RPi
│                             field=level  → level_delta_cm from measurements
│                             field=precip → precipitation_mm from measurements
│                             field=merge  → prec_mm from merge table (no station_id needed)
├── api/predictions.php    — receives prediction results + sends email notifications
├── DB: predictions        — one row per 5-min run per station
├── DB: prediction_alerts  — state transitions (fired / cleared), notification_sent flag
├── DB: merge              — MERGE/GPM hourly precipitation (updated by MERGE2MySQL pipeline)
└── predictions.php        — public web dashboard (Chart.js)
```

---

## File locations

### Raspberry Pi — production runtime

| Path | Description |
|------|-------------|
| `/home/ilha3d/SAPI/LightGBM_Production/` | Root production directory |
| `sapi_predict.py` | Cron entry point |
| `config_production.py` | All constants (paths, thresholds, gate, debounce) |
| `api_client.py` | HTTPS GET/POST client |
| `inference.py` | Pre-processing + model prediction + gate |
| `state.py` | Debounce state persistence |
| `train_production_model.py` | One-time training script (already run) |
| `models/model4_lgbm.pkl` | Trained model (24 MB) |
| `config/api_key.txt` | RPi API key (chmod 600) |
| `config/telegram_config.json` | Telegram bot token + chat IDs (chmod 600, never committed) |
| `state/debounce_state.json` | Per-station debounce counters |
| `logs/sapi_predict.log` | Full cron log (appended) |
| `logs/ultima_predicao.log` | Last-run summary (overwritten each run) |
| `.venv/` | Dedicated Python venv (darts 0.43, lightgbm 4.6, matplotlib 3.10) |

### Raspberry Pi — source code (repo)

```
predictive-models/production/
├── config_production.py
├── api_client.py
├── inference.py
├── state.py
├── sapi_predict.py
├── telegram_notifier.py      ← Issue #110: chart generation + Telegram Bot API
├── train_production_model.py
└── requirements_production.txt
```

> After changing any source file in the repo, copy it to
> `/home/ilha3d/SAPI/LightGBM_Production/` for the change to take effect.

### Hostinger

| Path | Description |
|------|-------------|
| `public_html/sapi/predictions.php` | Public web dashboard |
| `public_html/sapi/api/data.php` | GET endpoint for RPi |
| `public_html/sapi/api/predictions.php` | POST endpoint for RPi |
| `private_configs/sapi/api_config.php` | RPi API key (outside public_html) |

---

## Alert logic

```
raw_signal   = ANY horizon prediction >= threshold AND gate_active
debounced    = raw_signal persists for >= 3 consecutive 5-min steps (15 min)
alert_fired  = debounced transitions from "none" → active level
alert_cleared= debounced transitions from active level → "none"
```

**Thresholds** (both stations, adjustable in `config_production.py`):

| Level | Threshold |
|-------|-----------|
| Atenção | 60 cm |
| Alerta | 75 cm |
| Inundação | 90 cm |

**Gate**: 5 mm / 6 h rolling precipitation sum. If dry, no alert fires regardless of predictions (eliminates false alarms during dry periods; recall = 1.0 at Alerta and Inundação levels — validated in Issue #105).

**Debounce**: 3 consecutive steps (15 min) required. Prevents single-step spikes from firing alerts.

---

## Notifications (Issue #110)

On every `fired` or `cleared` alert transition, the system sends:

| Channel | Triggered by | Content |
|---------|-------------|---------|
| **Telegram (chart image)** | RPi `telegram_notifier.py` | `fired` → `sendPhoto` with matplotlib chart (last 2 h level + 4 dashed prediction horizons + threshold lines). `cleared` → plain `sendMessage`. |
| **Email** | Hostinger `api/predictions.php` | Email via PHPMailer (Gmail SMTP) to all active contacts assigned to the station in `alert_contacts`. |

### Email setup (Hostinger — one-time)

PHPMailer must be installed and the Gmail App Password configured before emails work.

**1. Install PHPMailer via Composer** (SSH into Hostinger):

```bash
cat > ~/composer.json <<'EOF'
{"require":{"phpmailer/phpmailer":"^6.9"}}
EOF
composer install --no-dev
```

**2. Create mail config** (copy from sample, fill in real App Password):

```bash
cp ~/domains/ilha3d.com/public_html/sapi/private_configs/sapi/mail_config-sample.php \
   ~/private_configs/sapi/mail_config.php
chmod 600 ~/private_configs/sapi/mail_config.php
vi ~/private_configs/sapi/mail_config.php   # set SAPI_SMTP_PASS (16 chars, no spaces)
```

Generate the App Password at: Google Account → Security → 2-Step Verification → App passwords.

Constants use the `SAPI_SMTP_*` prefix to avoid collision with `sapi.php` which defines `SMTP_HOST` for Hostinger's own relay.

**3. Test email delivery**:

```bash
php ~/domains/ilha3d.com/public_html/sapi/cron/test_prediction_email.php you@example.com 1
```

### Telegram config file (RPi)

```
/home/ilha3d/SAPI/LightGBM_Production/config/telegram_config.json
```

```json
{
  "bot_token": "<BotFather token>",
  "chat_ids": ["<user or group chat ID>"]
}
```

`chmod 600` — never committed. See sample in `webserver/private_configs/sapi/telegram_config-sample.json`.

### Testing without a real flood

```bash
cd /home/ilha3d/SAPI/LightGBM_Production
.venv/bin/python3 test_notification.py 1   # Station-01
```

Fetches live data, runs real inference, sends a Telegram photo with `fired=True`. No DB writes, no threshold changes.

---

## How to check if the system is working

### 1. Last-run summary (RPi)

The quickest check — shows predictions, gate status and alert level from the most recent run:

```bash
cat /home/ilha3d/SAPI/LightGBM_Production/logs/ultima_predicao.log
```

Expected output (normal dry day):
```
=== SAPI Última Predição — 2026-05-10 15:05:01 UTC ===

  Estação 1
    h_pred_30     : 45.1 cm
    h_pred_60     : 45.0 cm
    h_pred_90     : 44.8 cm
    h_pred_120    : 44.8 cm
    Precip 6h     : 0.00 mm  (station02)
    Gate ativo    : NÃO
    Nível bruto   : none
    Nível alerta  : none
    Debounce steps: 0
  ...
```

### 2. Full cron log (RPi)

Shows every run with timestamps, row counts, POST status:

```bash
# Live tail (watch new runs arrive every 5 min):
tail -f /home/ilha3d/SAPI/LightGBM_Production/logs/sapi_predict.log

# Last run only:
tac /home/ilha3d/SAPI/LightGBM_Production/logs/sapi_predict.log | \
  awk '/=== sapi_predict start/{found=1} found{print} /=== sapi_predict done/{exit}'
```

What to look for in a healthy run:
- `Level rows fetched: NNN` — should be > 24 (at least 2 h of data)
- `Precip rows fetched: NNN (Station-02)` — if < 10, MERGE fallback is used
- `POST OK` for each station
- `sapi_predict done in N s` — typically 15–20 s on RPi 4

### 3. Web dashboard

Open **https://ilha3d.com/sapi/predictions.php**

- Both station cards should show prediction values in the footer (+30/+60/+90/+120 min)
- The chart shows the last 3 hours of observed level (blue) + the 4-horizon prediction cone (pink dashed, 4 red dots)
- Gate badge: green = active, grey = inactive
- Alert badge: Normal / Atenção / Alerta / Inundação
- Page auto-refreshes every 5 minutes

### 4. Debounce state (RPi)

Shows the current consecutive-step counters per station:

```bash
cat /home/ilha3d/SAPI/LightGBM_Production/state/debounce_state.json
```

Normal (no active alert):
```json
{
  "1": {"consecutive_steps": 0, "last_alert_level": "none", "last_update": "..."},
  "3": {"consecutive_steps": 0, "last_alert_level": "none", "last_update": "..."}
}
```

During a flood, `consecutive_steps` counts up to 3 then holds; `last_alert_level` shows the active level.

### 5. Database (phpMyAdmin)

Check that new rows are being inserted every 5 minutes:

```sql
-- Latest predictions per station
SELECT id_station, timestamp, h_pred_30, h_pred_60, gate_active, alert_level
FROM predictions
ORDER BY timestamp DESC
LIMIT 10;

-- Recent alert transitions
SELECT * FROM prediction_alerts ORDER BY timestamp DESC LIMIT 20;
```

### 6. Cron entry (RPi)

Confirm the cron is installed:

```bash
crontab -l | grep sapi_predict
```

Expected:
```
*/5 * * * * /home/ilha3d/SAPI/LightGBM_Production/.venv/bin/python3 \
    /home/ilha3d/SAPI/LightGBM_Production/sapi_predict.py \
    >> /home/ilha3d/SAPI/LightGBM_Production/logs/sapi_predict.log 2>&1
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `Level rows fetched: 0` | API key wrong or data.php not reachable | Check `config/api_key.txt` matches `api_config.php` on Hostinger; curl `data.php` manually |
| `POST FAILED` for both stations | Hostinger unreachable or API key mismatch | Check `sapi_predict.log` for HTTP error code; verify `predictions.php` on Hostinger |
| `Model not found` error | `model4_lgbm.pkl` missing | Re-run `train_production_model.py` from `/home/ilha3d/SAPI/LightGBM_Production/` |
| Gate always 0 mm even during rain | Recent rain outside 6 h window, or Station-02 offline | Check `precip_source` in log; if `merge`, Station-02 is offline or sending < 10 rows |
| `predictions.php` shows "Sem predições ainda" | No rows in `predictions` table yet | Run `sapi_predict.py` manually once; check `sapi_predict.log` for errors |
| Chart not updating | Browser cache | Hard-refresh (Ctrl+Shift+R); the page auto-refreshes every 5 min |
| No Telegram notification on alert | Config file missing or wrong path | Check `config/telegram_config.json` exists (chmod 600) and has valid `bot_token` + `chat_ids`; run `test_notification.py` |
| Telegram `ok=False` | Invalid token or chat ID | Verify token with `api.telegram.org/bot<TOKEN>/getMe`; re-send `/start` to the bot and call `getUpdates` |

---

## Re-training the model

**Do not use `train_production_model.py`.** It is deprecated as of 2026-09-12: it trains on
flood windows only (the Issue #223 selection bias), reads the v2 event catalogue, applies no
sensor-artifact mask (Issue #227), does not spread the Station-02 reports (Issue #124), and
its `MERGE_CSV` points at the rolling six-day `merge_precip.csv` rather than the frozen
`merge_20260404.csv` — so it silently produces a model trained almost without rain.

Training now runs through the **same code that produced the published results**:

```bash
cd predictive-models
V=/home/ilha3d/SAPI/LightGBM_Production/.venv/bin/python3
$V train_production_from_backtest.py --model m4     # ~25 min
```

It imports `config` and `real_utils` from `results_final_m4_lgbm/`, so it inherits the
3-pass filtered and gap-filled level series, the spliced rain with the Issue #124 spread,
the artifact mask and continuous training. `TRAIN_END` is pushed past the end of the record
at runtime, so the deployed model is fitted on **all** available data — the chronological
hold-out exists to evaluate, not to deploy. The backtest `config.py` is never modified.

The model is written to a **staging** path and does not touch the file being served:

```
models/model4_lgbm_v2.pkl        # new model
models/model4_lgbm_v2.meta.json  # provenance: input hashes, versions, hyper-parameters
```

Before promoting it, run the parity check that proves production serves the same rain
series the model was trained on:

```bash
$V production/test_precip_parity.py
```

Promote with an explicit rename, keeping the previous model for rollback:

```bash
cd /home/ilha3d/SAPI/LightGBM_Production/models
mv model4_lgbm.pkl model4_lgbm_v1_20260510.pkl
mv model4_lgbm_v2.pkl model4_lgbm.pkl
```

The next cron run (within 5 min) picks it up — there is no service to restart. Rollback is
the reverse rename.

### Train/serve differences that are accepted and documented

Two known differences remain between the series the model is trained on and the series it
is served (Issue #225 / #211, decided 2026-09-12):

- **Level filter.** Training uses the 3-pass series, whose Pass 2 (Issue #211) is
  non-causal — it looks up to 20 min ahead to decide whether a spike returns to baseline.
  Production only has Pass 0 (`filter_level.php`) and Pass 1 (the 40 cm delta filter). The
  gap is exactly that one pass. Porting it is Issue #228.
- **Station-01/03 gap fill.** Training uses `station01_level_gapfilled.csv`, where
  Station-01 outages are filled from Station-03 with a per-band offset. In operation each
  station runs on its own series, with its real gaps.

---

## Key configuration constants (`config_production.py`)

| Constant | Value | Description |
|----------|-------|-------------|
| `GATE_MM` | 5.0 mm | Minimum 6 h precipitation to activate gate |
| `GATE_WINDOW_MIN` | 360 min | Rolling precipitation window |
| `DEBOUNCE_STEPS` | 3 | Consecutive steps before alert fires (15 min) |
| `LEVEL_FETCH_HOURS` | 4 h | Level history fetched from API per run |
| `PRECIP_FETCH_HOURS` | 7 h | Precipitation history fetched from API |
| `THRESHOLDS[1/3]["atencao"]` | 60 cm | Atenção threshold (both stations) |
| `THRESHOLDS[1/3]["alerta"]` | 75 cm | Alerta threshold |
| `THRESHOLDS[1/3]["inundacao"]` | 90 cm | Inundação threshold |

To change any value: edit `config_production.py` in the repo, copy to `/home/ilha3d/SAPI/LightGBM_Production/config_production.py`, and the next cron run uses the new value immediately (no restart needed).

---

*Created: 2026-05-10 | Issue #108 | Branch: feature/issue-108-realtime-prediction*  
*Updated: 2026-05-12 | Issue #110 — Telegram + email notifications on predictive alert transitions*
