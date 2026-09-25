# SAPI Alert Systems — How Notifications Actually Get Sent

**Status:** Living document — reflects the state of both systems as of 2026-08-13
**Related issues:** #52, #57, #63, #108, #110, #120, #160, #174, #175, #193, #195, #197

---

## Why this document exists

SAPI has **two independent alert-sending systems**. They look similar from the
outside (both classify a station into Atenção/Alerta/Inundação-style levels and
send Telegram/email/WhatsApp notifications), but they read different input
signals, run on different machines, use different thresholds, and have
different failure histories. Debugging "why didn't I get an alert" or "why did
I get five alerts for the same thing" requires knowing which system you're
looking at — several past incidents (Issues #160, #174, #193) came from
investigating the wrong one, or assuming a fix in one applied to both.

There is also a **third, cosmetic-only** threshold definition (the legend drawn
on `predictions.php`'s chart) that does not send anything — mentioned here only
to rule it out, see [Not an alert system](#not-an-alert-system-the-chart-legend).

---

## System #2 — Predictive alert pipeline (M4 LightGBM / M6 MLR)

**Runs on:** Raspberry Pi (`sapi-server`), cron every 5 minutes
**Input signal:** the model's **forecast** (+30/+60/+90/+120 min ahead), not the current reading
**Code:**
- `predictive-models/production/` (M4) and `production_m6/` (M6) — mirrored logic
- Entry point: `sapi_predict.py` → `inference.py` (forecast + gate) → `state.py` (debounce + notification decision) → `telegram_notifier.py` (Telegram) + `api/predictions.php` on Hostinger (email + DB log)
- Production copies actually run from `/home/ilha3d/SAPI/LightGBM_Production/` and `/home/ilha3d/SAPI/MLR_Production/` — **synced manually from the repo after every merge**, not git-pulled (Issue #174 was a 10-day gap caused by forgetting this step)

### Pipeline, step by step

```
Raspberry Pi (cron */5 min, M6 offset by "sleep 120")
│
├── Fetch last ~4h of level (Hostinger API, level_delta_cm) + last ~7h of
│   Station-02 precipitation (MERGE CSV fallback if Station-02 is offline)
│
├── Run the model → h_pred_30 / h_pred_60 / h_pred_90 / h_pred_120 (cm)
│
├── Classify raw_alert_level = highest threshold any horizon reaches
│       thresholds (config_production.py THRESHOLDS): atencao=50, alerta=60, inundacao=75 cm
│       (same values for Station-01 and Station-03 — not yet field-differentiated)
│
├── Gate: gated_alert_level = raw_alert_level  if 6h rolling precip ≥ GATE_MM (5mm)
│                            = "none"           otherwise
│       (inference.py: compute_gate() / _classify_alert(), "Suppress if gate is not active")
│
├── Debounce: gated_alert_level must hold for DEBOUNCE_STEPS (3) consecutive
│   5-min runs before it becomes the "debounced level" shown on the dashboard
│   and used for notification decisions (state.py: update())
│
├── Notification decision — NOT a simple "level changed" check:
│   fired   = debounced_level != "none" AND its rank > peak_notified_level's rank
│   cleared = debounced_level == "none" AND peak_notified_level != "none"
│       peak_notified_level = highest level already notified in the current
│       active episode (Issue #193) — a de-escalation (e.g. inundacao→alerta)
│       is never itself notified, and re-escalating back to an
│       already-notified level does NOT re-fire. Only resets to "none" on a
│       full `cleared` (raw drops below Atenção OR the rain gate deactivates).
│
└── On fired/cleared: Telegram (chart image on fired, plain text on cleared,
    telegram_notifier.py) + POST to Hostinger, which sends email
    (api/predictions.php) and logs a row to prediction_alerts / prediction_alerts_m6
```

### Known gap (Issue #195, open, not yet implemented)

`peak_notified_level` only resets on a *full* clear. A flood event with two
real, separate peaks — separated by a recession that stays *above* the
Atenção threshold and doesn't fully clear — will have its **second peak
silently suppressed**, because the debounced level never exceeds the
already-notified rank. Validated against a real double-peak event
(Station-01, 2025-01-17, catalogued in `event_windows_v2.csv`). Planned fix:
a `steps_below_peak` counter that re-arms the peak after `REARM_STEPS` (24,
≈2h) consecutive steps at a lower rank, without requiring a full clear. See
Issue #195 for the full design.

### Notification content

Two channels, built independently but from the same `result` dict:

| | Telegram (`telegram_notifier.py`) | Email (`api/predictions.php`) |
|---|---|---|
| Fired | Chart image (2h history + 4 prediction points + threshold lines) + caption | Same chart, embedded inline via Content-ID (Issue #190 — never a public URL, which would get overwritten by the next alert before the email is opened) |
| Cleared | Plain text — projections + precip | Plain text — "Situação normalizada" |
| Recipients | All chat IDs in `telegram_config.json` | `alert_contacts` rows joined to the station via `contact_stations` |

There is currently **no message for a de-escalation that doesn't fully
clear** (e.g. inundação → alerta) — this is intentional per #193's scope, not
a bug. See [System #3](#system-3--fixed-threshold-alert-check_alertsphp) for
where that kind of message already exists.

---

## System #3 — Fixed-threshold alert (`check_alerts.php`)

**Runs on:** Hostinger shared hosting, cron every **1 minute**
**Input signal:** the **actual observed** level (as of 2026-08-13, Issue #63:
`level_delta_cm` — previously `level_kalman_cm`, see "The Kalman bug" under Known gaps below)
**Code:** `webserver/cron/check_alerts.php` (single file, no RPi involvement)

### Pipeline, step by step

```
Hostinger (cron * * * * *, every 1 min)
│
├── For every (station, variable) with at least one enabled rule in alert_rules:
│     read the latest value — level_cm uses level_delta_cm (fallback: raw
│     level_cm), precipitation_mm sums the last 60 min, everything else is
│     the single latest reading
│
├── determineLevel(): highest-severity alert_rules row whose operator/threshold
│     the value satisfies → 'none' | 'attention' | 'alert' | 'flood'
│     (admin-editable per station+variable via admin/alert_rules.php, Issue #52;
│     seed values: Station-01 80/120/160 cm, Station-03 60/100/140 cm — these
│     are DIFFERENT numbers from system #2's thresholds, deliberately: two
│     independent signals, not meant to line up)
│
├── Compare to alert_state.current_level for this (station, variable).
│     No change → nothing happens. ANY change → notification fires immediately.
│     ⚠️ no debounce at all (see gap below) — a single 1-minute reading swing
│     across a threshold sends a notification right now, every time.
│
├── event_type = escalation      (rank went up)
│             | normalized       (rank dropped to 'none')
│             | de-escalation    (rank dropped but is still active)
│
└── sendAlert() for every enabled contact assigned to the station:
      - email (PHPMailer/SMTP)
      - WhatsApp (CallMeBot API) — if the contact has whatsapp_number + apikey
    After a 'normalized' event, an extra 'summary' message is sent reporting
    event_max_level ("Nível máximo atingido: X. Situação atual: Normalizado.")
```

### This system already has the message taxonomy system #2 lacks

Unlike system #2, **every transition is a first-class notified event** —
escalation, de-escalation, normalized, and a post-event summary all have their
own message text (`buildMessage()`, `check_alerts.php` ~line 320):

```
escalation    → "[SAPI] {LEVEL} — {station}\n{var}: {value}\nNível de alerta atingido: {LEVEL}."
de-escalation → "[SAPI] Retornando para {LEVEL} — {station}\n{var}: {value}."
normalized    → "[SAPI] Normalizado — {station}\n{var}: {value}\nSituação normalizada."
summary       → "[SAPI] Resumo do evento — {station}\nNível máximo atingido: {maxLevel}.\nSituação atual: Normalizado."
```

These are the `"SAPI - Alerta de In..."` emails with subjects like
`[SAPI] Normalizado — FLN Norte - Estacao-01` or `[SAPI] FLOOD — FLN Norte -
Estacao-01` — distinct from system #2's `[SAPI] Alerta Preditivo — ...`
subjects. Easy to mix up when reading an inbox; the subject line is the
tell.

### Known gaps

- **The Kalman bug (Issue #63, fixed 2026-08-13).** `getCurrentValue()` used
  to read `level_kalman_cm`, which has ~10-25 min of lag at flood peaks
  (confirmed on a real Station-03 event: raw peak 06:29, Kalman peak ~07:54).
  A threshold crossing evaluated against a 25-minute-old smoothed value can
  fire well after the actual conditions that caused it have passed — this
  produced alerts that looked disconnected from reality. Fixed by switching
  to `level_delta_cm` (already computed by `filter_level.php`, zero added
  lag, spike-rejecting). Deployed to Hostinger the same day.
- **Zero debounce (Issue #197, open, not yet implemented).** As described
  above — any single-minute reading swing fires immediately. The proposed
  fix does **not** need system #2's `peak_notified_level`/re-arm machinery,
  because de-escalation is already its own notified event here — there's no
  silent "limbo" state for a peak to get stuck in. A plain symmetric
  debounce (require N consecutive minutes at the new level before
  confirming any transition, up or down) is sufficient. See Issue #197.
- **No precipitation/context gate**, unlike system #2's `GATE_MM`. Flagged,
  not yet an issue — more delicate than it sounds, since gating a *reactive*
  observed-level alert on local rain could mask a real rise the rain gauge
  didn't capture (e.g. rain further upstream, gauge offline).
- **`telegram_chat_id` field exists on `alert_contacts` and is editable in
  `admin/contacts.php`, but nothing ever sends to it.** This system's only
  channels are email and WhatsApp — don't assume a contact configured with a
  Telegram chat ID here will receive anything via that channel.

---

## Side-by-side comparison

| | System #2 — Predictive (M4/M6) | System #3 — Fixed-threshold |
|---|---|---|
| Signal | Model forecast (+30..+120 min) | Observed level (`level_delta_cm`) |
| Runs on | Raspberry Pi | Hostinger (PHP cron) |
| Cadence | 5 min | 1 min |
| Thresholds | `config_production*.py` `THRESHOLDS` — 50/60/75 cm, same for both stations | `alert_rules` DB table, admin-editable, **different values per station** (80/120/160 vs 60/100/140 cm) |
| Precipitation gate | Yes (`GATE_MM` = 5mm/6h) | No |
| Debounce | Yes (`DEBOUNCE_STEPS` = 3 steps = 15 min) | **No** (Issue #197, open) |
| Re-escalation hysteresis | Yes (`peak_notified_level`, Issue #193); double-peak gap open (Issue #195) | N/A — every transition already notifies on its own |
| De-escalation notification | No (silent, intentional) | **Yes** (`de-escalation` event) |
| "All clear" summary | Plain "normalizado" message | "Normalizado" + separate "Resumo do evento" with max level reached |
| Channels | Telegram (RPi) + Email (Hostinger) | Email + WhatsApp (Hostinger) |
| DB log | `predictions`/`predictions_m6` (every run) + `prediction_alerts`/`prediction_alerts_m6` (transitions) | `alert_log` (every notification attempt) |
| Dashboard page | `predictions.php` | `alert_log.php` / `admin/alert_log.php` — **a different page** |

---

## Not an alert system: the chart legend

`predictions.php`'s chart draws horizontal lines for Atenção/Alerta/Inundação
using a hardcoded `$stations[...]` array in `public_html/sapi/predictions.php`.
These happen to match system #2's thresholds (coincidence of shared values,
not a shared source), but **this array does not drive any notification
logic** — it exists purely to annotate the chart. If it's ever edited without
also editing `config_production.py`/`config_production_m6.py`, the chart and
the actual alert thresholds will silently disagree.

---

## Quick answers to "why didn't I get an alert"

1. **Which page did you check?** `predictions.php` (system #2) and
   `alert_log.php` (system #3) are independent — a fix or a bug in one does
   not affect the other.
2. **Which subject line?** `[SAPI] Alerta Preditivo — ...` is system #2.
   `[SAPI] {LEVEL} — ...` / `[SAPI] Normalizado — ...` / `[SAPI] Resumo do
   evento — ...` (no "Preditivo") is system #3.
3. **Did the level de-escalate without fully clearing?** System #2 stays
   silent on that by design. System #3 sends a `de-escalation` message for
   it.
4. **Did it escalate again to a level already notified this episode, without
   a real recession in between?** System #2 will stay silent until Issue
   #195 ships. System #3 doesn't have this failure mode at all.
5. **Was it a single-reading blip?** System #2 is protected by
   `DEBOUNCE_STEPS`. System #3 currently is not (Issue #197) — a lone noisy
   minute can and does fire a real notification today.
