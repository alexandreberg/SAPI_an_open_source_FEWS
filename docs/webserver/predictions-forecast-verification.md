# Forecast Verification — `predictions.php`

*Implemented: 2026-08-16 | Branch: `feature/predictions-forecast-verification`*
*File: `webserver/public_html/sapi/predictions.php`*

---

## Why this exists

The M4 (LightGBM) and M6 (MLR) predictive models each fire a Telegram/email
alert when their forecast crosses a station's threshold (Atenção/Alerta/
Inundação). Until this feature, the only way to check whether a specific
alert's forecast actually came true — and how far off in time it was — was to
manually cross-reference production logs (`sapi_predict.log`,
`sapi_predict_m6.log`), the received Telegram/email messages, and the
`predictions.php` table by hand. That process doesn't scale past a handful of
events and can't produce an aggregate accuracy figure.

This feature adds two things to the existing `predictions.php` dashboard,
without any database migration (all data already existed in `predictions`,
`predictions_m6`, `prediction_alerts`, `prediction_alerts_m6`,
`measurements.level_delta_cm`):

1. A **retrospective verification view** for any individual fired alert.
2. An **aggregate accuracy card** across many alerts in a date range.

---

## 1. Retrospective verification (`?verify_id=&model=m4|m6`)

Every `fired` row in the "Transições de alerta preditivo" table gets a
**Verificar** link. Clicking it opens a card at the top of the page showing:

- The forecast cone (purple M4 / orange M6 dashed line) **re-anchored to that
  alert's own moment** (`bridgeTs`), overlaid on the observed level extended
  ~3h past the alert — not "now", like the live station cards.
- A table of Previsto / Observado / Erro for each of the 4 horizons
  (+30/+60/+90/+120 min), matching the model's raw `h_pred_*` output against
  the nearest `measurements.level_delta_cm` reading (±3 min tolerance).
- A **reaction-time comparison**: how many minutes after the alert the
  forecast implied the threshold would be crossed, versus how many minutes it
  actually took.

### How the threshold-crossing time is computed

`buildForecastCurve()` builds a 5-point curve per prediction: the observed
level at t0 (the alert's own anchor) + the 4 horizon values. This is **not**
a per-horizon number — `findThresholdCrossing()` walks the curve looking for
the first point-to-point segment where it crosses the alert's threshold, and
**linearly interpolates** the exact crossing time within that segment. The
same function runs on the observed series (`measurements.level_delta_cm`,
never the Kalman-filtered value — see [[feedback_kalman_scope]]) to find when
the threshold was really crossed. Both are single numbers, but which segment
of the curve they fall in varies alert to alert.

**Two lead times are shown, not just the delta:**

```
Previsto atingir 75 cm em 44,1 min (às 01:46:15 UTC) — ocorreu de fato em 87,9 min (às 02:30:00 UTC).

  [+43,8 min a mais de tempo de reação do que o previsto]
```

- `pred_lead_min` = predicted-crossing − t0 (what the forecast promised)
- `obs_lead_min` = observed-crossing − t0 (what actually happened)
- The badge = `obs_lead_min − pred_lead_min`

**Badge semantics** (this needed a deliberate wording pass — "atrasou/
antecipou" and "modelo conservador/otimista" were both tried and rejected as
ambiguous):

| Sign | Meaning | Badge |
|---|---|---|
| **Positive ("a mais")** | The real crossing happened *later* than forecast — the operator got *more* reaction time than promised. Safe direction. | Green |
| **Negative ("a menos")**, ≤15 min | Less reaction time than promised, small deficit. | Amber |
| **Negative ("a menos")**, >15 min | Less reaction time than promised, larger deficit — the riskier direction for a flood warning. | Red |

### The "already above threshold before the window" edge case

`findThresholdCrossing()` only detects a genuine ascending transition (a
point below the threshold immediately followed by one at/above it). It
deliberately does **not** treat an already-above-threshold first point as a
crossing at that point's own timestamp — an earlier version did this and it
silently fabricated a crossing time whenever the observed level was already
elevated before the fixed lookback window (t0 − 1h) even started (e.g. during
a slow recession after a flood peak, or a second alert firing while the first
episode hadn't normalized yet). The bogus "crossing" was just wherever the
query window happened to start, not a real transition — see the alert fired
2026-08-15 23:22 UTC (M6, Alerta/60cm) for the real-world case that surfaced
this.

The forecast curve is the one exception: its own anchor point (t0) is a
well-defined reference, so `resolvePredictedCrossing()` still treats
"already at/above threshold at t0" as a legitimate crossing at t0 for that
curve specifically.

When the observed series is already above threshold before the window, the
UI shows a dedicated message instead of a false badge:

> Nível observado já estava acima de 60 cm desde antes do início da janela
> analisada (2026-08-15 22:22:07 UTC) — não é possível determinar o momento
> exato do cruzamento real a partir destes dados.

This is distinct from the "previsto mas nunca observado" case (forecast
implied a crossing that never actually happened within the 150-min tracked
window — possible model overestimation), which keeps its own message.

---

## 2. Pagination of the transitions table

`fetchRecentAlerts()`/`countRecentAlerts()` now support `?alert_page=N`
instead of a fixed `LIMIT 20`. The default view (no `alert_page` in the URL)
still shows the most recent 20, matching the previous behavior; older pages
are reachable via the pager at the bottom of the table, and the **Verificar**
link works on any page, not just the first.

**Gotcha for future edits to this query:** the DB connection in this project
uses `PDO::ATTR_EMULATE_PREPARES => false` (native prepared statements). MySQL
requires `LIMIT`/`OFFSET` placeholders to be bound as `PDO::PARAM_INT`
explicitly (`bindValue(..., PDO::PARAM_INT)`) — passing them through a plain
`execute([$pageSize, $offset])` array binds everything as strings and throws
a SQL syntax error under native prepares. This bit the first draft of the
pagination code; every other parameterized query in this file is a plain
`WHERE`/comparison value, where the string-binding is harmless.

---

## 3. Aggregate accuracy card ("Acurácia das previsões")

Filter form: **Estação** (or all), **Modelo** (M4/M6/both), **De/Até** date
range (GET params `acc_station`, `acc_model`, `acc_from`, `acc_to`).

For each model in scope, `computeAccuracyStats()`:

1. Fetches `fired` alerts in the date range (`fetchFiredAlertsInRange()`,
   capped at 300 rows).
2. Per alert, per horizon: absolute error `|observado − previsto|` (cm),
   averaged into **MAE per horizon** — one column per model in the table.
3. Per alert: predicted vs. observed threshold-crossing time (same logic as
   the retrospective view, including the "already above" exclusion), when
   both are found — averaged into **mean/median reaction-time delta**,
   rendered with the same badges and "a mais/a menos de tempo de reação do
   que o previsto" language as the individual verification card.

**Three different sample sizes appear and should not be confused:**

| Shown as | What it counts |
|---|---|
| "N alerta(s) disparado(s) no período" | All `fired` alerts matched to a prediction row |
| (MAE table, implicit) | Subset with an observed reading within tolerance at that specific horizon — varies per column |
| "(n=Z)" next to the reaction-time badges | Smaller subset with a *valid* crossing pair on both sides — excludes "never reached" and "already above" cases |

### Known cost

No caching — every filter submission re-runs the full per-alert query loop
(up to ~7 queries × up to 300 alerts × up to 2 models). Noticeably slower
than the rest of the page but tolerable in practice as of this writing.
Flagged as a candidate for pre-computation/caching if the alert history grows
much further — not implemented, out of scope for this pass.

### Data-quality cutoff — Issue #193

Predictive alerts fired before **2026-08-13** (before the [[project_issue193_notification_flood]]
fix landed in production ~13:21 local on 2026-08-12) re-fired repeatedly on
the same oscillating episode instead of firing once per genuine escalation.
Mixing those into the aggregate would silently blend two different firing
behaviors into one misleading average. To prevent this by accident:

- The default `acc_from` is the constant `ACC_SAFE_FROM` (`2026-08-13`), not
  a rolling "N days ago".
- The date input has `min="2026-08-13"` (client-side only).
- A warning banner is rendered above the filter form explaining why.

If `ACC_SAFE_FROM` ever needs to move (e.g. another firing-logic bug is found
and fixed later), update the constant in one place near the top of
`predictions.php` — the banner text and the input's `min` both read from it.

---

## Related memory / issues

- [[feedback_kalman_scope]] — why `level_delta_cm`, never Kalman, is used for
  observed comparisons here.
- [[project_issue193_notification_flood]], [[project_issue195_double_peak_rearm]] —
  the notification-flood fix this feature's date cutoff is protecting against,
  and the still-open double-peak follow-up.
- [[project_issue63_197_check_alerts_fixes]] — the *other* (fixed-threshold)
  alert system's `level_delta_cm` fix; unrelated code path, don't confuse the
  two when debugging missed alerts (see [[project_alert_systems_architecture]]).

---

*Last updated: 2026-08-16*
