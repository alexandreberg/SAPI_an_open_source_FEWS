# US-100 Ultrasonic Sensor — Serial Mode Test Report (Test-04)

**Test Date:** February 26, 2026
**Location:** Florianópolis, Santa Catarina, Brazil
**Tester:** Alexandre Nuernberg
**Project:** SAPI — Sistema de Alerta Prévio de Inundações (Flood Early Warning System)
**Related Issue:** #22 — Create Test-04 report template and CSV
**Firmware fix applied before this test:** #20 — Round-half-up mm→cm conversion

---

## 1. Test Objectives

This is the **final bench test** before field installation of Station-03. Unlike Tests 01–03, which were used to derive the correction formula, Test-04 is a **pure validation campaign**: its sole purpose is to confirm that the formula derived in Test-03 generalises to an independent dataset collected with the production-ready firmware.

Specific objectives:

- Independently validate the correction formula `Corrected = 0.925 × Raw + 1.41` on a fresh set of measurements
- Confirm that the formula delivers MAE ≤ ~1.5 cm and near-zero systematic bias across the Station-03 operational range (30–350 cm)
- Document sensor behaviour in the near-field zone (< 20 cm) for completeness
- Confirm the maximum reliable range, consistent with previous tests
- Lock in the production firmware configuration (correction formula + round-half-up rounding fix)

---

## 2. Equipment Used

### 2.1 Device Under Test (DUT)

**US-100 Ultrasonic Sensor**

| Parameter | Value |
|-----------|-------|
| Operating Mode | Serial (UART) — **Jumper INSTALLED** |
| Measuring Range (datasheet) | 2 cm – 450 cm |
| Resolution | 1 mm (sensor output), 1 cm (firmware, after round-half-up) |
| Beam Angle | ~15° total cone angle (±7.5° half-angle) |
| Communication | 9600 baud, 8N1 |
| Distance command | 0x55 → 2-byte response (MSB + LSB) in mm |
| Temperature command | 0x50 → 1-byte response (raw − 45 = °C) ⚠️ see Errata |
| Power Supply | 5 V (Nucleo USB 5 V pin) |
| Temperature compensation | Automatic (onboard MCU in serial mode) |

### 2.2 Reference Instrument

**Bosch GLM 20 Professional Laser Meter** — sole reference

| Parameter | Value |
|-----------|-------|
| Measuring Range | 0.15 m – 20 m |
| Accuracy | ±3.0 mm (typical) |
| Resolution | 1 mm |
| Offset Correction Applied | −10.0 cm (validated by tape meter in Test-03) |

> **Note:** The tape meter used in Test-03 to cross-validate the Bosch offset confirmed agreement to < 0.6 cm across all positions. The −10.0 cm Bosch correction is therefore considered definitively validated and was not repeated in Test-04.

### 2.3 Microcontroller

**STM32 Nucleo L476RG**

| Parameter | Value |
|-----------|-------|
| MCU | STM32L476RG (ARM Cortex-M4, 80 MHz) |
| Serial port | Serial3 (PC10 = RX, PC11 = TX) |
| Firmware | `ultrasonic.cpp` — median filtering, 11 samples |
| Sensor type | `US_SENSOR_US100` (serial mode) |
| **Active correction formula** | **`Corrected = 0.925 × Raw + 1.41`** (from Test-03) |
| Rounding fix | Round-half-up mm→cm (issue #20, PR #21, merged 2026-02-26) |
| Development environment | PlatformIO + VS Code |

---

## 3. Test Setup

### 3.1 Physical Configuration

- Indoor environment, same room as Test-03
- Sensor mounted pointing horizontally toward a flat wall
- Bosch GLM 20 measured independently at each sensor position
- Sensor powered from 5 V (Nucleo USB)
- Jumper installed on US-100 → serial (UART) mode active

### 3.2 Test Procedure

1. Position sensor at target distance from wall
2. Record US-100 **Raw (cm)** and **Corrected (cm)** as printed by firmware serial monitor
3. Record Bosch GLM 20 reading; apply −10.0 cm offset → **Bosch-Corrected**
4. Move away from wall continuously, recording at intervals
5. Stop at the first repeated timeout (maximum range boundary)

### 3.3 Test Photographs

Setup photographs are available in the `images/` subdirectory:

| File | Description |
|------|-------------|
| IMG_3328.JPG | Test setup overview |
| IMG_3329.JPG | Sensor mount detail |
| IMG_3330.JPG | Short-range measurement (near-field zone) |
| IMG_3331.JPG | Mid-range measurement |
| IMG_3332.JPG | Mid-range measurement |
| IMG_3333.JPG | Mid-range measurement |
| IMG_3334.JPG | Mid-range measurement |
| IMG_3335.JPG | Long-range measurement |
| IMG_3336.JPG | Long-range measurement |
| IMG_3337.JPG | Long-range measurement |
| IMG_3339.JPG | Maximum range / timeout boundary |

---

## 4. Test Results

> **Primary Reference:** All error calculations use `Bosch-Corrected` (= Bosch raw − 10.0 cm).
> `Error` = `US-100 Corrected − Bosch-Corrected`.
> Rows 1–4 (Bosch-Corrected < 20 cm) are flagged **NEAR-FIELD** — the correction formula was not designed for this range and these rows are excluded from the main validation statistics.

### 4.1 Raw Measurement Data

| #  | US-100 Raw (cm) | US-100 Corrected (cm) | Bosch Raw (cm) | Bosch-Corrected (cm) | Error (cm) | Notes |
|----|-----------------|-----------------------|----------------|----------------------|------------|-------|
| 1  | 5               | 6                     | 15.6           | 5.6                  | +0.4       | NEAR-FIELD |
| 2  | 7               | 8                     | 18.8           | 8.8                  | −0.8       | NEAR-FIELD |
| 3  | 9               | 10                    | 21.1           | 11.1                 | −1.1       | NEAR-FIELD |
| 4  | 21              | 21                    | 27.8           | 17.8                 | +3.2       | NEAR-FIELD |
| 5  | 26              | 25                    | 33.7           | 23.7                 | +1.3       | |
| 6  | 32              | 31                    | 40.2           | 30.2                 | +0.8       | |
| 7  | 39              | 37                    | 46.7           | 36.7                 | +0.3       | |
| 8  | 45              | 43                    | 50.6           | 40.6                 | +2.4       | |
| 9  | 48              | 46                    | 55.4           | 45.4                 | +0.6       | |
| 10 | 55              | 52                    | 61.7           | 51.7                 | +0.3       | |
| 11 | 60              | 57                    | 67.1           | 57.1                 | −0.1       | |
| 12 | 67              | 63                    | 73.4           | 63.4                 | −0.4       | |
| 13 | 74              | 70                    | 80.1           | 70.1                 | −0.1       | |
| 14 | 82              | 77                    | 87.4           | 77.4                 | −0.4       | |
| 15 | 92              | 87                    | 96.2           | 86.2                 | +0.8       | |
| 16 | 99              | 93                    | 103.2          | 93.2                 | −0.2       | |
| 17 | 109             | 102                   | 112.5          | 102.5                | −0.5       | |
| 18 | 119             | 111                   | 121.9          | 111.9                | −0.9       | |
| 19 | 132             | 124                   | 133.9          | 123.9                | +0.1       | |
| 20 | 146             | 136                   | 146.5          | 136.5                | −0.5       | |
| 21 | 157             | 147                   | 157.2          | 147.2                | −0.2       | |
| 22 | 171             | 160                   | 169.0          | 159.0                | +1.0       | |
| 23 | 181             | 169                   | 179.1          | 169.1                | −0.1       | |
| 24 | 190             | 177                   | 187.5          | 177.5                | −0.5       | |
| 25 | 200             | 186                   | 197.3          | 187.3                | −1.3       | |
| 26 | 211             | 197                   | 206.2          | 196.2                | +0.8       | |
| 27 | 220             | 205                   | 215.5          | 205.5                | −0.5       | |
| 28 | 234             | 218                   | 228.1          | 218.1                | −0.1       | |
| 29 | 243             | 226                   | 237.1          | 227.1                | −1.1       | |
| 30 | 254             | 236                   | 247.2          | 237.2                | −1.2       | |
| 31 | 264             | 246                   | 255.9          | 245.9                | +0.1       | |
| 32 | 272             | 253                   | 263.4          | 253.4                | −0.4       | |
| 33 | 280             | 260                   | 270.9          | 260.9                | −0.9       | |
| 34 | 289             | 269                   | 278.8          | 268.8                | +0.2       | |
| 35 | 301             | 280                   | 290.0          | 280.0                | 0.0        | |
| 36 | 311             | 289                   | 299.0          | 289.0                | 0.0        | |
| 37 | 325             | 302                   | 311.5          | 301.5                | +0.5       | |
| 38 | 337             | 313                   | 322.4          | 312.4                | +0.6       | |
| 39 | 349             | 324                   | 333.4          | 323.4                | +0.6       | |
| 40 | 361             | 334                   | 343.7          | 333.7                | +0.3       | |
| 41 | 372             | 346                   | 354.5          | 344.5                | +1.5       | |
| 42 | FAIL            | FAIL                  | 362.6          | 352.6                | —          | FAIL — timeout |
| 43 | FAIL            | FAIL                  | 379.6          | 369.6                | —          | FAIL — timeout |

### 4.2 Near-Field Zone (Rows 1–4, Bosch-Corrected < 20 cm)

Rows 1–4 (Bosch-Corrected = 5.6–17.8 cm) are documented for completeness but are **excluded from all validation statistics**. The correction formula `0.925 × Raw + 1.41` was derived from data in the 20–354 cm range and is not intended for use below 20 cm.

Observed behaviour in the near-field zone:

- Rows 1–3 (BC = 5.6–11.1 cm): the sensor slightly **underestimates** even after correction (errors: +0.4, −0.8, −1.1 cm). At these extreme distances the sensor's internal acoustic timing produces a different error profile than the proportional overestimation seen in the working range. This is consistent with near-field reverb effects.
- Row 4 (BC = 17.8 cm): the sensor overestimates by +3.2 cm, marking the transition back into the proportional overestimation regime. The formula reduces but does not fully compensate the error at this boundary distance.

**Practical recommendation:** do not rely on corrected readings below 20 cm Bosch-Corrected. Readings below 30 cm should be treated as approximate (see Section 5.3).

### 4.3 Row 8 — Elevated Error at Short Range

Row 8 (BC = 40.6 cm, Raw = 45 cm, Error = +2.4 cm) shows the highest error of any operational-range point. The raw overestimation at this position is 10.8%, compared to the typical 7% seen across the dataset. This is isolated: the immediately preceding (row 7, +0.3 cm) and following (row 9, +0.6 cm) readings are within normal bounds. It likely reflects natural measurement scatter combined with the inherently larger percentage variability at short ranges and integer rounding at 1 cm resolution. The reading is kept as valid; no firmware or systematic cause has been identified.

---

## 5. Statistical Analysis

### 5.1 Dataset Summary

| Parameter | Value |
|-----------|-------|
| Total rows | 43 |
| FAIL (timeout) | 2 (rows 42–43) |
| NEAR-FIELD (excluded from validation stats) | 4 (rows 1–4, BC < 20 cm) |
| **Valid for validation (BC ≥ 30 cm)** | **36** |
| **All valid including near-field** | **41** |
| Valid rate (excl. fails) | 95.3% |
| Operational range covered | 30.2 – 344.5 cm |

### 5.2 Formula Validation — Primary Results

Validation performed on the **operational range** (BC ≥ 30 cm, n = 36). This is the range for which the formula was derived and for which Station-03 will be used in the field.

| Statistic | Value |
|-----------|-------|
| **Mean error (Corrected − Bosch-Corrected)** | **+0.04 cm** (essentially zero bias) |
| **MAE** | **0.56 cm** |
| **RMSE** | **0.75 cm** |
| **MAPE** | **0.58%** |
| Max absolute error | 2.4 cm (row 8, BC = 40.6 cm — see Section 4.3) |
| Max absolute error excl. row 8 | 1.5 cm (row 41, BC = 344.5 cm) |

**Including near-field rows** (all valid, n = 41):

| Statistic | Value |
|-----------|-------|
| Mean error | +0.11 cm |
| MAE | 0.66 cm |
| RMSE | 0.91 cm |

### 5.3 Range-Dependent Performance

| Distance Range (Bosch-Corrected) | n  | Mean Error (cm) | MAE (cm) | Max \|Error\| (cm) |
|----------------------------------|----|-----------------|----------|--------------------|
| 30 – 100 cm                      | 11 | +0.36           | 0.58     | 2.4 (row 8)        |
| 100 – 200 cm                     | 10 | −0.21           | 0.59     | 1.3                |
| 200 – 300 cm                     | 10 | −0.39           | 0.45     | 1.2                |
| 300 – 350 cm                     | 5  | +0.70           | 0.70     | 1.5                |

Observations:

- The formula performs consistently across the full operational range, with MAE below 0.7 cm in every sub-range
- There is a small systematic pattern: slight over-correction at mid-range (100–300 cm, negative mean error) and slight under-correction at the extremes (< 100 cm and > 300 cm). Both effects are within ≤ 0.7 cm mean and do not affect practical use
- The pattern is consistent with Test-03 and reflects the inherent trade-off of a single linear correction over a wide range

### 5.4 Raw Sensor Performance (for Reference)

The uncorrected US-100 error in the operational range, for comparison against previous tests:

| Statistic | Test-04 Value |
|-----------|---------------|
| Mean error (Raw − Bosch-Corrected) | +12.68 cm |
| MAE | 12.68 cm (all errors positive) |
| MAPE | 7.00% |

The 7.0% raw MAPE is fully consistent with Tests 01 (7.7%), 02 (7.2%), and 03 (6.9%), confirming the sensor's systematic overestimation behaviour is stable across all four independent test campaigns.

### 5.5 Comparison: Test-03 Predictions vs Test-04 Measurements

| Metric | Test-03 (derivation, n=37) | Test-04 (validation, n=36) | Assessment |
|--------|---------------------------|---------------------------|------------|
| MAE (corrected) | 0.73 cm | **0.56 cm** | Better than predicted |
| RMSE (corrected) | 0.91 cm | **0.75 cm** | Better than predicted |
| Mean error | −0.05 cm | **+0.04 cm** | Near-zero bias confirmed |
| MAPE (corrected) | — | **0.58%** | Excellent |
| Raw MAPE | 6.88% | **7.00%** | Consistent |

The formula **generalises well**: Test-04 independent validation outperforms the Test-03 derivation metrics in both MAE and RMSE, confirming the formula is not overfitted and is ready for production use.

---

## 6. Operational Limits

### 6.1 Maximum Range

| Test | First Timeout (Bosch-Corrected) | Last Valid Reading |
|------|--------------------------------|--------------------|
| Test-01 | ~425 cm | ~406 cm |
| Test-02 | ~385 cm | ~406 cm |
| Test-03 | ~376 cm | ~354 cm |
| **Test-04** | **352.6 cm** | **344.5 cm** |

The first timeout in Test-04 occurs at BC = 352.6 cm, consistent with the intermittent reliability boundary observed in all previous tests. The reliable working ceiling is confirmed at **~350 cm**; Station-03 should be installed no further than 3.5 m from the water surface.

### 6.2 Minimum Range

| Test | Minimum Tested (BC) | Corrected Error at Min |
|------|---------------------|------------------------|
| Test-01 | 26.5 cm | — |
| Test-02 | 12.2 cm | — |
| Test-03 | 19.5 cm | — |
| **Test-04** | **5.6 cm** | **+0.4 cm (NEAR-FIELD)** |

Test-04 explored the near-field zone more aggressively than previous tests. Below 20 cm the formula diverges: errors reach +3.2 cm at 17.8 cm and the sign can flip (underestimation at < 12 cm). **Practical minimum: 30 cm** for reliable corrected output; with caution, usable down to ~20 cm.

---

## 7. Conclusions

### 7.1 Formula Validated for Production

The correction formula `Corrected = 0.925 × Raw + 1.41`, derived in Test-03, has been independently validated in Test-04:

- **MAE = 0.56 cm** (operational range, n = 36) — better than the 0.73 cm derivation performance
- **Mean error = +0.04 cm** — essentially zero systematic bias
- **MAPE = 0.58%** — compared to 7.0% raw sensor error
- **Max error = 1.5 cm** (excluding the single outlier-like row 8 at short range)

The formula **meets and exceeds all success criteria** established before the test. It is confirmed as the production correction for Station-03.

### 7.2 Production Firmware Configuration Locked

The firmware flashed immediately before Test-04 is the **production configuration**:

```cpp
// ultrasonic.cpp — production settings for Station-03

// Correction formula (Test-03 regression, validated in Test-04):
readings->correctedDistance = (int32_t)roundf(0.925f * (float)readings->distance + 1.41f);

// Rounding fix (issue #20, PR #21 — round-half-up, not truncate):
int32_t distanceCm = (distanceMm + 5) / 10;
```

### 7.3 Consistency Across All Four Tests

The proportional ~7% raw overestimation has been confirmed independently in four test sessions conducted on different dates, in different environments, and at different distance ranges:

| Test | Date | MAPE Raw | MAE Corrected | n valid |
|------|------|----------|---------------|---------|
| Test-01 | Jan 25, 2026 | 7.7% | — | 26 |
| Test-02 | Feb 15, 2026 | 7.2% | — | 45 |
| Test-03 | Feb 24, 2026 | 6.9% | 0.73 cm (derivation) | 37 |
| **Test-04** | **Feb 26, 2026** | **7.0%** | **0.56 cm (validation)** | **36** |

This consistency across 144 valid readings from four independent sessions confirms the US-100 in serial mode is a reliable and predictable sensor for the SAPI application.

### 7.4 Recommendations for Station-03 Field Installation

1. **Formula locked:** use `Corrected = 0.925 × Raw + 1.41` — do not change before field data is collected
2. **Install within 3.5 m** of the water surface to remain below the reliable range ceiling (~350 cm)
3. **Do not rely on corrected readings below 20 cm** — the formula was not designed for this zone
4. **Monitor corrected distance** in the field database; if systematic deviation from limnimetric ruler exceeds ~3 cm after installation, revisit in-situ calibration
5. **Post-outlier discard logic** (recommended in Test-03 Section 8.5) remains a future firmware improvement; it was not implemented before this test but the median filter (11 samples) already suppresses most outliers effectively

---

## 8. Firmware Reference

**File:** `firmware/station-03/src/ultrasonic.cpp`

**Production Configuration (as tested in Test-04):**

```cpp
#define US_SENSOR_TYPE US_SENSOR_US100   // Serial mode selected
#define NUM_READINGS   11                // Median of 11 samples per reading
#define MAX_RETRIES    20                // Max retries per sample

// Correction formula — validated production formula:
readings->correctedDistance = (int32_t)roundf(0.925f * (float)readings->distance + 1.41f);

// mm→cm conversion — round-half-up (issue #20):
int32_t distanceCm = (distanceMm + 5) / 10;
```

**Serial Protocol (US-100):**

| Command | Byte | Response | Formula |
|---------|------|----------|---------|
| Distance | 0x55 | 2 bytes MSB+LSB (mm) | `dist_mm = (MSB << 8) \| LSB` |
| Temperature | 0x50 | 1 byte raw | `temp_C = raw - 45` ⚠️ see Errata |
| Baud rate | — | 9600, 8N1 | — |
| Timeout | — | 500 ms (corrected) | — |

---

## 9. References

1. **US-100_datasheet-01.pdf** (Adafruit) — Serial mode protocol, jumper configuration
2. **US-100.PDF** — Basic specifications, schematic diagram
3. **Bosch GLM 20 Professional** — Reference instrument specifications
4. **US-100_Serial_Mode_Test_Report.md** (Test-01, Jan 25, 2026)
5. **US-100_Serial_Mode_Test_Report-02.md** (Test-02, Feb 15, 2026)
6. **US-100_Serial_Mode_Test_Report-03.md** (Test-03, Feb 24, 2026) — Source of the validated formula
7. SAPI system overview (docs/system-overview.md) — System Architecture Documentation
8. GitHub Issue #20 — Round-half-up rounding fix
9. GitHub Issue #22 — Test-04 report

**Datasheet location:** manufacturer datasheets (not redistributed here)
**Raw data:** `docs/tests/us-100/US-100_Serial_mode_test-04/test-04.csv`
**Photographs:** `docs/tests/us-100/US-100_Serial_mode_test-04/images/`

---

*Report generated as part of SAPI Master's thesis research — IFSC Florianópolis*
*Formula status: **PRODUCTION — locked for Station-03 field deployment***

---

## Errata — Temperature Formula Correction (Issue #24, February 28, 2026)

### E.1 Error Description

The temperature formula documented in this report as `temp_C = raw / 4.0` is **incorrect**.
The correct standard formula (consistent with the US-100 datasheet and confirmed in Test-02 and
Test-03 text descriptions) is:

```
temp_C = raw - 45
```

### E.2 Root Cause

The wrong formula was introduced because the US-100 unit used during Tests 01–04 had a
**defective internal thermistor**. The thermistor was stuck, returning a constant raw value of
**109** regardless of ambient temperature. This coincidentally produced 27.25 °C with the
incorrect `raw / 4.0` formula, which approximately matched ambient temperature during Test-02
(~27 °C room) — masking the error.

The failure was discovered after Station-03 field deployment, when the temperature reading
remained at 27.2 °C across an ambient range of 23–30 °C (Issue #24).

### E.3 Diagnostic Method

An independent test sketch (`test-us100.cpp`) was written using the reference implementation
(500 ms blocking delay after command 0x50, as documented in standard Arduino examples):

| Sensor unit | Raw byte observed | `raw - 45` result | Ambient |
|-------------|-------------------|-------------------|---------|
| Old (defective) | always 109 | **64 °C** (impossible) | ~25 °C |
| New (replacement) | 72 – 73 | **27 – 28 °C** ✓ | ~25 °C |

The constant raw=109 from the defective unit confirmed thermistor failure. The replacement
unit tracked temperature correctly.

A secondary finding: the 100 ms poll timeout in `ultrasonic.cpp` was adequate — the sensor
responds within 100 ms. The 500 ms delay was used only to isolate the diagnostic from the
normal firmware cycle.

### E.4 Corrections Applied

| Location | Was | Now |
|----------|-----|-----|
| `ultrasonic.cpp` `readTemperatureUS100()` | `raw / 4.0f` | `(float)((int)raw - 45)` |
| This report, Section 2.1 | `raw / 4.0 = °C` | `raw − 45 = °C` |
| This report, Section 8 firmware table | `temp_C = raw / 4.0` | `temp_C = raw - 45` |

**Distance measurements and the correction formula `Corrected = 0.925 × Raw + 1.41` are
unaffected.** The US-100 performs its own speed-of-sound compensation internally in serial
mode; the externally read temperature byte is used only for cross-validation, not for the
distance output.
