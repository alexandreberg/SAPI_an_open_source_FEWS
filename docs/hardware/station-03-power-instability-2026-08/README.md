# Station-03 — intermittent power instability causing bad ~335cm readings (2026-08-20/22)

Field/bench notes for a real hardware incident on Station-03 (Nucleo L476RG,
US-100 ultrasonic sensor, serial mode). Documented here so the affected
period is clearly understood as a **hardware problem**, not a sensor
calibration error or a software bug in the delta filter / alert system.

## 1. Symptom

Starting ~2026-08-20 13:46, Station-03 began intermittently transmitting a
fixed, exact **335 cm** level reading, interleaved with the genuine ~46-48cm
level. The bad value never varied — always exactly `335`, never `334` or
`336` — which was itself a clue that this was not ordinary ultrasonic echo
noise (real echo noise, even spurious reflections, is expected to jitter at
least slightly). This caused a cascade of false "flood" alert emails from
`check_alerts.php` throughout 2026-08-20 evening and most of 2026-08-21 (see
Issue references below for the alerting-side fixes that were needed
regardless of the hardware cause).

## 2. Root cause investigation

Cross-referencing the `measurements` table's `reading_number` column against
`level_cm` was the key diagnostic step. `reading_number` is not an arbitrary
sequence — the firmware sets it directly from a persistent boot counter
(`sensorData.reading_number = bootCounter;`, `main.cpp:1056`) stored in an
STM32 RTC backup register (BR4), incremented on every `setup()` run and
**never cleared anywhere in the firmware**. Station-03 deliberately goes
through a full chip reset every reading cycle via `LowPower.shutdown()`
(STANDBY-equivalent deep sleep, woken by the RTC alarm) — this is normal,
by-design behavior, and `reading_number` climbing by ~2 every ~5 minutes
cycle-to-cycle reflects it correctly. Backup registers survive that kind of
reset. They only reset to 0 on a genuine loss of power to the backup domain
itself (VDD/VBAT dropping out) — not a normal RTC-wake reset, and not a
plain external reset (NRST/reset button) either.

Every time `reading_number` was observed dropping back down to a low number
in the DB (i.e. a genuine backup-domain power loss, not the normal wake
cycle), the very next reading was **deterministically** `level_cm = 335`,
self-correcting within 1-2 further readings (about one minute). This
happened at least 6 separate times across the incident:

- 4 times the evening of 2026-08-21, within a ~25-minute window, with no
  user action involved (spontaneous)
- Once more on 2026-08-22 morning, immediately following the sequence
  described in section 3 below

This is strong evidence that the bad reading is not sensor/echo noise at
all, but an artifact of the **very first** ultrasonic read attempt right
after a real power interruption — most likely the sensor (or its serial
link) not yet being ready/warmed-up at that exact moment, with the failure
response landing on `level_cm = 335` after being run through the firmware's
`level_cm = levelZero − distance_raw` conversion (Station-03's `levelZero` =
236cm; `236 + 99 = 335` matches the shape of a known US-100 error/timeout
sentinel value, `-99`, though this exact numeric path has not yet been
confirmed against the current `ultrasonic.cpp` source — see Issue #203).

## 3. What actually happened physically (confirmed with the user, 2026-08-22)

The 2026-08-22 morning occurrence was initially unclear — it looked like a
plain reset-button press alone had triggered the same backup-domain-clear
symptom, which would have been surprising (a plain NRST reset does not
normally clear STM32 backup registers). Clarified afterward: the actual
sequence was **power off → physically reconnect wiring for field
installation → power on** (producing the bad `335` reading as the first
sample after this genuine power cycle) **→ reset button pressed
afterward** (redundant, not the actual trigger). This is consistent with —
not contradictory to — the "genuine power loss" diagnosis; no NRST-only
anomaly needs to be assumed.

Prior to that, on 2026-08-21, the user found and reseated a loose
connection at the ultrasonic sensor's connector/cable. A ~30 minute test
with the enclosure open showed clean readings; closing the enclosure
brought the fault back — pointing at a mechanical contact issue sensitive
to the pressure/flex of closing the case. The connector/cable was
subsequently reseated more carefully and the enclosure resealed.

## 4. Confirmation the fix held

An unattended overnight test (enclosure sealed, ~2026-08-21 23:20 through
2026-08-22 09:31) showed `reading_number` climbing **continuously and
monotonically** from 1 to 233 — the normal +2-per-cycle pattern, ~5:19
between readings — across the full ~10 hour, 100+-cycle window, with
**zero** backup-domain resets and **zero** bad readings (`level_cm` stayed
stable at 30-31cm throughout). This is a clean, strong confirmation that
resealing the connector resolved the intermittent power dropout, at least
under bench/lab conditions.

The station was then moved to field (re)installation on 2026-08-22 (see
section 3's power-cycle event, which is part of that reinstallation).

## 5. Affected data marked invalid

All `measurements` rows for `id_station = 3` between **2026-08-20 13:46:00**
(when the noise began) and **2026-08-22 10:07:46** (the first reading after
the final field-reconnection power-up, `reading_number = 3`, exclusive —
that reading and everything after it is valid field data) were nulled out
and flagged `flag = 'b'` — **513 rows** — because the station was on the
bench for troubleshooting during that whole window, not deployed in the
field: none of that period's data (level, RSSI, temperature, humidity,
voltages) reflects real field/installation conditions, not just the level
readings that happened to look obviously wrong.

## 5b. Recurrence (2026-08-25)

The same `335 cm` fault signature reappeared on 2026-08-25, this time as a
sustained multi-hour oscillation rather than isolated blips, with no
power/reset signature observed on the battery-voltage trace this time. See
`2026-08-25-recurrence.md` in this same directory for the full observation
notes (documentation only — root-cause investigation deferred).

## 6. Follow-up (open)

- **Issue #202** — Station-03 has no simple, reliable way to get a live
  serial console when the ST-Link segment is detached (three
  partially-working paths exist; none worked cleanly this session). This
  made the whole investigation slower than necessary — root cause was
  reconstructed from DB timestamps after the fact instead of observed live.
- **Issue #203** — whether a firmware fix is warranted regardless of the
  hardware root cause (e.g. logging STM32 reset-cause flags at boot to
  distinguish power-on vs. external reset definitively going forward, and/or
  discarding or delaying the first ultrasonic reading after any detected
  backup-domain reset so a recurrence of this kind of power event — e.g. from
  field conditions the bench test didn't cover: rain, vibration, thermal
  cycling — can't reach the database again even if the mechanical fix
  doesn't hold forever).
