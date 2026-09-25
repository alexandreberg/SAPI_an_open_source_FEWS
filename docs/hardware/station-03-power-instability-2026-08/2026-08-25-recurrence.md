# Station-03 — recurrence of bad ~335cm level readings (2026-08-25)

Follow-up to the original incident writeup in this same directory
(`README.md`, 2026-08-20/22). The same fault signature — a fixed, exact
**335 cm** level reading — reappeared today, 2026-08-25. This note records
what was observed from the web dashboard (screenshots reviewed at
`/tmp/prob-est-03/`, taken ~07:04–07:11 local time) **before** any
troubleshooting action was taken, per the user's request to document first
and investigate later. No root cause is claimed here — see "Open questions"
below.

## 1. Symptom this time: sustained oscillation, not isolated blips

Unlike the 2026-08-20/22 incident (isolated bad `335` samples,
self-correcting within 1-2 cycles after a backup-domain power-loss reset),
today's level chart shows a **sustained square-wave oscillation** between
the genuine baseline (~47-48 cm) and the clamped `335 cm` ceiling, repeating
across many consecutive cycles from **~05:28 UTC through at least ~10:04
UTC** (the end of the available window at screenshot time) — roughly 4.5+
hours. `335.00` is also the exact all-time max in the chart's stats panel
(N=113, Média 133.99, Min 47.00, Máx 335.00), confirming every bad sample
hit the same clamp value as before, not a range of noisy values.

This produced the expected cascade of false alerts: the alert inbox shows
`[SAPI] FLOOD` emails at 04:35 and 05:20 (reporting the `335 cm` value and
an "INUNDAÇÃO" threshold crossing), interleaved with `[SAPI] Normalizado`
emails — consistent with the alert system correctly reacting to bad data
it has no way to distinguish from a real level, not a bug in the alerting
logic itself (see the existing `check_alerts.php` debounce/hysteresis work,
Issues #193/#195/#197, for that separate concern).

## 2. Everything else on the station stayed fully operational

Cross-checking every other channel transmitted by Station-03 over the exact
same time window:

- **Surface temperature** (read from the *same* US-100 sensor's internal
  temperature-compensation function, over the same serial link as the
  distance measurement): continuous throughout, no dropouts, no clamping —
  tracked a plausible slow diurnal curve (13°C → 10°C overnight, back up to
  ~12°C by mid-morning). This is the strongest single piece of evidence that
  the US-100 module itself was powered and its serial link was alive and
  responding correctly — only the *echo-distance* half of the sensor's
  function failed, not the sensor as a whole.
- **Air temperature**: continuous, unaffected, normal diurnal shape.
- **Relative humidity**: continuous, unaffected, smooth curve 78% → ~98%.
- **RSSI**: stable around -73 dBm (min -74, max -69) for the entire window —
  no LoRa link dropouts, no correlation with the level oscillation.
- **Battery voltage**: smooth, monotonic discharge from 12.10V to 11.71V —
  no brownout dips, no discontinuities that would suggest a power-loss/reset
  event (contrast with the previous incident, where bad readings tracked
  backup-domain resets visible via `reading_number`).
- **Panel voltage**: normal solar profile — flat ~0V overnight, ramping up
  to ~13V starting ~09:00 UTC as the sun rose. Normal, unaffected.

**Conclusion of this observation pass**: the fault is isolated to the US-100
ultrasonic **distance/echo** measurement path specifically. The station's
power system, MCU, LoRa radio/gateway link, and even the *other* function of
the same US-100 module (its internal temperature reading) all continued
operating normally through the entire affected window. This is consistent
with the framing needed for the dissertation/incident record: this is not a
station-wide outage, and not (on this evidence alone) a station power
problem — it did not reproduce the previous incident's power/reset
signature.

## 3. Action taken / planned (not yet done as of this note)

- User plans to press the physical reset button on Station-03 this evening
  after arriving home, to see whether that alone normalizes the readings.

## 4. Open questions for later investigation (explicitly deferred — not being pursued now)

Per the user, this note is observation-only; the following is recorded so it
isn't lost, not as a plan being executed:

- **US-100 hardware fault**: the *original* US-100 unit (in service since
  station install) is the one currently installed. Notably, the
  *replacement* unit swapped in at some point reportedly showed the *same*
  symptom, then the original was put back and the symptom is recurring again
  now — i.e. two different physical US-100 units have both exhibited this
  failure mode at different times. That weakens (but doesn't rule out) a
  single-defective-unit explanation and points more toward something shared
  between both units' installations (wiring, connector, bus noise, or
  firmware) — worth keeping in mind when this is investigated, without
  concluding it here.
- **Wiring / SPI-bus noise**: the cabling from the SAPI Shield Morpho to the
  US-100 connector was fully redone last time using wire-wrap connections.
  Worth checking for noise/continuity issues on that signal path.
- **Firmware**: whether this is a recurrence of the same root cause tracked
  in Issue #203 (bad first-reading-after-reset), a related firmware issue,
  or something new — cannot be determined from the dashboard screenshots
  alone; needs `reading_number` continuity from the `measurements` table
  (as was done for the original incident) and/or live serial console access
  (Issue #202, still open) to investigate properly.

No `measurements` rows have been flagged invalid for this recurrence yet —
that should happen once the affected window is confirmed bounded (i.e. after
tonight's reset and any further troubleshooting settles the station back to
normal), following the same procedure as section 5 of the original
`README.md`.
