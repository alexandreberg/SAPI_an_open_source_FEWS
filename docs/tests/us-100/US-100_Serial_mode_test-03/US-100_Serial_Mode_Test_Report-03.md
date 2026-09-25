# US-100 Ultrasonic Sensor - Serial Mode Test Report (Test 03)

**Test Date:** February 24, 2026
**Location:** Florianopolis, Santa Catarina, Brazil
**Tester:** Alexandre Nuernberg
**Project:** SAPI - Sistema de Alerta Previo de Inundacoes (Flood Early Warning System)
**Related Issue:** #8 - Test US-100 sensor in serial mode

---

## 1. Test Objectives

- Obtain a larger dataset for regression refinement using the Bosch GLM 20 as the primary reference, validated by an independent tape meter
- Confirm the Bosch GLM 20 offset correction (−10 cm) used in Tests 01 and 02 with the tape meter as independent witness
- Re-derive the linear correction formula from Test-03 data only, using Bosch-Corrected as the authoritative reference
- Extend short-range coverage (down to ~19 cm)
- Confirm sensor outlier behavior and range limits observed in previous tests

---

## 2. Equipment Used

### 2.1 Device Under Test (DUT)

**US-100 Ultrasonic Sensor**

| Parameter | Value |
|-----------|-------|
| Operating Mode | Serial (UART) - **Jumper INSTALLED** |
| Measuring Range (datasheet) | 2 cm - 450 cm |
| Resolution | 1 mm (sensor output in mm), 1 cm (after firmware integer division) |
| Beam Angle | ~15° total cone angle (±7.5° half-angle from center axis) |
| Operating Frequency | 40 kHz |
| Communication | 9600 baud, 8N1 |
| Command Byte | 0x55 |
| Response | 2 bytes (MSB + LSB) = distance in mm |
| Power Supply | **5V** (from Nucleo USB 5V pin) |
| Temperature Sensor | Built-in; distance output is **automatically** temperature-compensated by onboard MCU in serial mode. |

### 2.2 Reference Instruments

**Bosch GLM 20 Professional Laser Meter** — Primary reference

| Parameter | Value |
|-----------|-------|
| Measuring Range | 0.15 m - 20 m |
| Measuring Accuracy | +/- 3.0 mm (typical) |
| Resolution | 1 mm |
| Offset Correction Applied | −10.0 cm (same as Tests 01 and 02) |

**Steel Tape Meter** — Secondary reference (validation only)

| Parameter | Value |
|-----------|-------|
| Measurement Method | Direct physical measurement |
| Estimated Accuracy | ±5–6 mm (positioning uncertainty) |
| Role | Independent validation of the Bosch −10 cm offset correction; not used as regression reference |

### 2.3 Microcontroller

**STM32 Nucleo L476RG**

| Parameter | Value |
|-----------|-------|
| MCU | STM32L476RG (ARM Cortex-M4, 80 MHz) |
| Serial Port | Serial3 (PC10=RX, PC11=TX) |
| Firmware | ultrasonic.cpp (median filtering, 11 samples) |
| Sensor Type | US_SENSOR_US100 (serial mode) |
| Active correction formula | `Corrected = 0.933 × Raw - 1.87` |
| Development Environment | PlatformIO + VS Code |

---

## 3. Test Setup

### 3.1 Physical Configuration

- Indoor environment, clear line of sight to flat wall
- Sensor mounted pointing horizontally toward wall
- Bosch GLM 20 and tape meter measured independently at each position
- Sensor powered from 5V (Nucleo USB 5V pin)

### 3.2 Jumper Configuration

- **Jumper INSTALLED** on the back of the US-100 sensor → activates serial (UART) mode

### 3.3 Test Procedure

1. Position setup at target distance from wall
2. Record US-100 raw reading and corrected reading as displayed by firmware
3. Record Bosch GLM 20 reading and apply −10 cm offset (same correction as Tests 01 and 02)
4. Record tape meter reading at the same position for cross-validation
5. Move away from wall taking readings at intervals (measurements #1–22, outbound)
6. Return toward wall taking readings at intervals (measurements #23–42, return)
7. The two-direction approach validates repeatability

---

## 4. Test Results

> **Primary Reference:** All error calculations and regression use the `Bosch-Corrected` column (−10.0 cm offset already applied). The `Tape Meter` column is provided for cross-validation only — see Section 5.9.

### 4.1 Raw Measurement Data

| # | US-100 Raw (cm) | US-100 Corrected (cm) | Bosch-Corrected (cm) | Tape Meter (cm) | Error Raw−Bosch (cm) | Error % | Notes |
|---|-----------------|-----------------------|----------------------|-----------------|----------------------|---------|-------|
| 1  | 25  | 21  | 23.2  | 22.7  | +1.8  | +7.8%  | Near min range |
| 2  | 39  | 35  | 35.7  | 35.2  | +3.3  | +9.2%  | |
| 3  | 54  | 49  | 51.3  | 50.9  | +2.7  | +5.3%  | |
| 4  | 69  | 63  | 65.9  | 65.5  | +3.1  | +4.7%  | |
| 5  | 88  | 80  | 83.3  | 83.2  | +4.7  | +5.6%  | |
| 6  | 108 | 99  | 101.0 | 101.2 | +7.0  | +6.9%  | |
| 7  | 124 | 114 | 116.9 | 116.6 | +7.1  | +6.1%  | |
| 8  | 136 | 125 | 128.0 | 128.0 | +8.0  | +6.3%  | |
| 9  | 154 | 142 | 143.6 | 143.3 | +10.4 | +7.2%  | |
| 10 | 176 | 162 | 164.2 | 164.3 | +11.8 | +7.2%  | |
| 11 | 199 | 184 | 185.5 | 185.7 | +13.5 | +7.3%  | |
| 12 | 143 | 133 | 200.2 | 200.3 | --    | --     | **OUTLIER** – sensor gave erroneous 143 cm at true ~200 cm |
| 13 | 214 | 198 | 221.4 | 221.6 | --    | --     | **ANOMALOUS** – see Section 4.2 |
| 14 | 237 | 219 | 243.0 | 243.3 | --    | --     | **ANOMALOUS** – see Section 4.2 |
| 15 | 279 | 258 | 260.1 | 260.7 | +18.9 | +7.3%  | Sensor recovered |
| 16 | 298 | 276 | 277.8 | 278.3 | +20.2 | +7.3%  | |
| 17 | 320 | 297 | 298.1 | 298.5 | +21.9 | +7.3%  | |
| 18 | 342 | 317 | 317.7 | 318.2 | +24.3 | +7.6%  | |
| 19 | 361 | 335 | 333.3 | 333.7 | +27.7 | +8.3%  | |
| 20 | 383 | 355 | 353.7 | 353.5 | +29.3 | +8.3%  | |
| 21 | FAIL | FAIL | 376.5 | 376.5 | --    | --     | **FAIL** – sensor timeout (beyond reliable range) |
| 22 | FAIL | FAIL | 355.5 | 355.7 | --    | --     | **FAIL** – timeout on return (intermittent at range boundary) |
| 23 | 367 | 341 | 340.7 | 340.7 | +26.3 | +7.7%  | Return path begins |
| 24 | 349 | 324 | 324.8 | 325.3 | +24.2 | +7.5%  | |
| 25 | 322 | 299 | 297.5 | 297.7 | +24.5 | +8.2%  | |
| 26 | 302 | 280 | 281.8 | 282.1 | +20.2 | +7.2%  | |
| 27 | 289 | 268 | 269.5 | 269.8 | +19.5 | +7.2%  | |
| 28 | 271 | 251 | 253.1 | 253.1 | +17.9 | +7.1%  | |
| 29 | 256 | 237 | 238.7 | 238.7 | +17.3 | +7.2%  | |
| 30 | 237 | 219 | 220.9 | 221.1 | +16.1 | +7.3%  | |
| 31 | 218 | 202 | 203.6 | 203.5 | +14.4 | +7.1%  | |
| 32 | 196 | 181 | 183.4 | 183.7 | +12.6 | +6.9%  | |
| 33 | 175 | 161 | 164.0 | 164.3 | +11.0 | +6.7%  | |
| 34 | 149 | 137 | 139.8 | 140.1 | +9.2  | +6.6%  | |
| 35 | 123 | 113 | 116.1 | 116.0 | +6.9  | +5.9%  | |
| 36 | 104 | 95  | 98.2  | 98.0  | +5.8  | +5.9%  | |
| 37 | 87  | 79  | 82.2  | 81.9  | +4.8  | +5.8%  | |
| 38 | 73  | 66  | 69.3  | 69.0  | +3.7  | +5.3%  | |
| 39 | 60  | 54  | 57.7  | 57.4  | +2.3  | +4.0%  | |
| 40 | 48  | 43  | 45.8  | 45.3  | +2.2  | +4.8%  | |
| 41 | 34  | 30  | 31.3  | 31.0  | +2.7  | +8.6%  | |
| 42 | 21  | 18  | 19.5  | 19.1  | +1.5  | +7.7%  | Near min range |

### 4.2 Anomalous Rows 12–14

Row 12 is a clear **outlier**: the US-100 returned 143 cm while both references place the true distance at ~200 cm. This type of erroneous low reading (likely caused by a multipath reflection or transient acoustic interference) was also observed in previous tests.

Rows 13 and 14 are **anomalous**: the US-100 reads 214 and 237 cm respectively, while the true distances (Bosch-Corrected) are ~221 and ~243 cm. In all other 37 valid readings the sensor consistently **overestimates** (raw > reference). These two are the only positions where raw < reference, and both occur immediately after the row 12 outlier event.

Two possible explanations are considered:

1. **Post-outlier sensor recovery**: after returning an erroneous echo at row 12, the sensor's internal acoustic timing may not have fully recovered, causing the next 1–2 readings to be erroneously low.
2. **Tape-measure interference during positioning**: while measuring with the tape meter at these positions, the tape itself could have introduced a spurious acoustic reflection inside the beam cone (~15° total angle), momentarily biasing the US-100 reading downward. This would not be a sensor failure but a measurement procedure artifact.

Both explanations are plausible. In either case, by row 15 (~260 cm Bosch) the sensor is back to the normal +7–8% overestimation pattern and the anomaly does not recur.

These three rows are **excluded from all statistical and regression calculations**.

### 4.3 Error Codes

| Code | Meaning | Cause |
|------|---------|-------|
| FAIL | Timeout | No valid response within firmware timeout period |
| OUTLIER | Erroneous reading | Sensor returned a value far from any plausible true distance |
| ANOMALOUS | Suspect reading | Sensor underestimating; possible sensor recovery or tape-meter reflection artifact |

---

## 5. Statistical Analysis

### 5.1 Valid Data Set

| Parameter | Value |
|-----------|-------|
| Total rows (excluding empty) | 42 |
| Fail (timeout) | 2 (rows 21–22) |
| Outlier | 1 (row 12) |
| Anomalous | 2 (rows 13–14) |
| **Valid readings for analysis** | **37** |
| Valid rate | 88.1% |
| Distance range (Bosch-Corrected) | 19.5 – 353.7 cm |

### 5.2 Error Analysis (US-100 Raw vs Bosch-Corrected)

All differences are positive: the US-100 **consistently overestimates** at all valid measurement points, confirming the pattern from Tests 01 and 02.

| Statistic | Test-03 Value |
|-----------|---------------|
| Mean Error (Raw − Bosch) | +12.40 cm |
| Median Error | +11.00 cm |
| Min Error | +1.5 cm (at 19.5 cm Bosch) |
| Max Error | +29.3 cm (at 353.7 cm Bosch) |
| MAE (= Mean, since all positive) | 12.40 cm |
| RMSE | 15.03 cm |
| MAPE | 6.88% |
| Std Dev of errors | 8.62 cm |

### 5.3 Current Correction Formula Performance (Corrected vs Bosch-Corrected)

The firmware's active formula `Corrected = 0.933 × Raw - 1.87` was evaluated against the Bosch-Corrected reference.

| Statistic | Value |
|-----------|-------|
| Mean Error (Corrected − Bosch) | **−1.85 cm** (slight systematic underestimation) |
| MAE | **2.09 cm** |
| RMSE | **2.24 cm** |
| MAPE | **2.39%** |

The current formula remains **effective** on Test-03 data. The small negative mean error (−1.85 cm) indicates the formula slightly over-corrects relative to this test's Bosch reference.

### 5.4 Range-Dependent Error Analysis (Raw vs Bosch-Corrected)

| Distance Range (Bosch) | n | Avg Error (cm) | Avg Error % |
|------------------------|---|----------------|-------------|
| < 30 cm                | 2 | +1.65          | +7.7%       |
| 30 – 100 cm            | 10| +3.53          | +5.9%       |
| 100 – 200 cm           | 10| +9.75          | +6.7%       |
| 200 – 300 cm           | 10| +19.09         | +7.3%       |
| 300 – 400 cm           | 5 | +26.36         | +7.9%       |

The pattern is **consistent with Tests 01 and 02**: error % increases slightly with distance but remains stable at 5.9–7.9% across the 30–354 cm working range.

### 5.5 Linear Regression Analysis (Test-03 Only)

Linear regression was performed using Bosch-Corrected as the reference (x-axis) and error (Raw − Bosch) as the dependent variable.

**Test-03 regression:**

```
Error (cm) = 0.0807 × Distance − 1.5135
R² = 0.9866
```

Converting to correction formula (direct regression, Bosch vs Raw):

```
Corrected = 0.925 × Raw + 1.41
```

Performance on Test-03 data:

| Formula | MAE (cm) | RMSE (cm) | Mean Error (cm) |
|---------|----------|-----------|-----------------|
| **Test-03 formula** (`0.925 × Raw + 1.41`) | **0.73** | **0.91** | **−0.05** |
| Previous formula (`0.933 × Raw − 1.87`) | 2.09 | 2.24 | −1.85 |

The new formula nearly eliminates the systematic bias (mean error −0.05 cm) and reduces MAE by 65% compared to the previous formula.

**Predicted corrections with new formula:**

| True Distance (Bosch) | Expected Raw | New Corrected | Old Corrected | Difference |
|-----------------------|-------------|---------------|---------------|------------|
| ~50 cm                | ~53 cm      | ~50.0 cm      | ~47.6 cm      | +2.4 cm    |
| ~131 cm               | ~140 cm     | ~131.1 cm     | ~128.6 cm     | +2.5 cm    |
| ~200 cm               | ~215 cm     | ~199.9 cm     | ~198.8 cm     | +1.1 cm    |
| ~350 cm               | ~377 cm     | ~349.9 cm     | ~349.9 cm     | +0.0 cm    |

### 5.6 Error Component Analysis

| Component | Test-01 | Test-02 | Test-03 | Interpretation |
|-----------|---------|---------|---------|----------------|
| Proportional (slope) | 6.5% | 6.8% | 8.1% | Calibration error in sensor's speed-of-sound constant |
| Constant (intercept) | +2.15 cm | +1.58 cm | −1.51 cm | Physical offset + regression anchor from data distribution |

The proportional ~7–8% error persists across all three tests, confirming it originates in the sensor firmware's base speed-of-sound constant. The intercept variation between tests reflects differences in data density at short range (Test-03 has more short-distance points which pull the intercept down) and does not change the physical interpretation.

### 5.7 Repeatability Analysis (Outbound vs Return)

Measurements taken at similar Bosch-Corrected distances during outbound and return trips:

| Bosch (out, cm) | Raw (out) | Bosch (ret, cm) | Raw (ret) | Bosch diff | Raw diff |
|-----------------|-----------|-----------------|-----------|------------|----------|
| 83.3            | 88        | 82.2            | 87        | +1.1       | +1       |
| 116.9           | 124       | 116.1           | 123       | +0.8       | +1       |
| 164.2           | 176       | 164.0           | 175       | +0.2       | +1       |
| 185.5           | 199       | 183.4           | 196       | +2.1       | +3       |

At essentially the same reference distance the US-100 readings differ by only **1–3 cm**, confirming excellent repeatability. The median filtering (11 samples) is effective.

### 5.8 Bosch vs Tape Meter Cross-Validation

| Statistic | Value |
|-----------|-------|
| Mean difference (Bosch − Tape) across all valid rows | −0.04 cm |
| Maximum absolute difference | 0.60 cm |
| Minimum absolute difference | 0.00 cm |

The near-zero mean difference **independently validates the −10.0 cm Bosch offset correction** applied throughout all three test reports. The tape meter confirms the Bosch is the correct reference; the small tape meter discrepancies (~5–6 mm) reflect normal positioning uncertainty during manual measurement and do not affect the Bosch-based regression.

---

## 6. Comparison: Tests 01, 02, and 03

### 6.1 Test Conditions

| Parameter | Test-01 | Test-02 | Test-03 |
|-----------|---------|---------|---------|
| Date | Jan 25, 2026 | Feb 15, 2026 | Feb 24, 2026 |
| Environment | Outdoor (concrete wall) | Indoor/outdoor (tiled wall) | Indoor (flat wall) |
| Reference | Bosch-Corrected | Bosch-Corrected | Bosch-Corrected (+ tape validation) |
| Distance Range (valid) | 26.5 – 406.6 cm | 12.2 – 406.0 cm | 19.5 – 353.7 cm |
| Total measurements | 30 | 51 | 42 |
| Valid measurements | 26 (87%) | 45 (88%) | 37 (88%) |
| Timeouts | 4 (13%) | 6 (12%) | 2 (5%) |
| Outlier/anomalous | 0 | 0 | 3 (7%) |

### 6.2 Statistical Consistency

| Metric | Test-01 | Test-02 | Test-03 | Trend |
|--------|---------|---------|---------|-------|
| MAE (raw vs Bosch) | 15.92 cm | 15.17 cm | 12.40 cm | Consistent (Test-03 shorter max range) |
| MAPE | 7.7% | 7.2% | 6.9% | Very consistent |
| Regression slope | 0.065 | 0.068 | 0.081 | Consistent ~7–8% |
| New corrected formula MAE | — | — | 0.73 cm | Excellent |

The error percentage (~7%) is **highly consistent across all three tests**, independently conducted on different dates and surfaces.

---

## 7. Operational Limits

### 7.1 Maximum Range

| Test | First Timeout (Bosch-Corrected) | Last Valid Reading |
|------|--------------------------------|-------------------|
| Test-01 | ~425 cm | ~406 cm |
| Test-02 | ~385 cm | ~406 cm |
| Test-03 | ~376 cm (outbound) | ~354 cm |

Test-03 did not push the range as aggressively as Tests 01/02. The first timeout at ~376 cm and a second at ~356 cm on the return are consistent with the intermittent behavior at range limits observed before.

### 7.2 Minimum Range

| Test | Minimum Tested (Bosch) | Error at Min |
|------|----------------------|--------------|
| Test-01 | 26.5 cm | +13.2% |
| Test-02 | 12.2 cm | +6.6% |
| Test-03 | 19.5 cm | +7.7% |

Readings below ~30 cm show slightly elevated percentage error. Practical minimum recommended: **30 cm** for < 10% raw error; with correction applied, usable down to ~20 cm.

---

## 8. Conclusions

### 8.1 Test-03 Validates Tests 01 and 02

Test-03 independently confirms all major findings:
- US-100 in serial mode **consistently overestimates** across the entire valid range
- Error % is **stable at ~6–8%** in the 30–350 cm range across all three tests
- **Excellent repeatability** (within 1–3 cm at the same distance, outbound vs return)

### 8.2 Dual Reference Validation

For the first time, both a laser meter (Bosch GLM 20) and a tape meter were used simultaneously. Their agreement (< 0.6 cm) across all positions **validates the −10.0 cm Bosch offset correction** applied retroactively to Tests 01 and 02. The Bosch meter is confirmed as the authoritative reference for all test campaigns.

### 8.3 Post-Outlier Anomaly (Rows 12–14)

Three consecutive rows showed anomalous behavior: one clear outlier (row 12) followed by two readings where the sensor underestimated (rows 13–14). These are the only underestimation events across the full three-test campaign (108 valid readings combined). Two causes are considered: sensor acoustic-timing recovery after the erroneous echo, or an accidental reflection from the tape measure inside the sensor beam cone during positioning. In either case the anomaly is transient and the sensor recovers by the next measurement. The firmware recommendation is to **discard 1–2 readings after any detected outlier** before resuming normal operation.

### 8.4 New Correction Formula (Test-03)

Test-03 regression using Bosch-Corrected as reference (37 valid points):

```
Error = 0.0807 × Distance − 1.5135  (R² = 0.99)
→ Corrected = 0.925 × Raw + 1.41
```

Performance comparison on Test-03 data:

| Formula | MAE | RMSE | Mean Error |
|---------|-----|------|------------|
| New formula `0.925 × Raw + 1.41` | **0.73 cm** | **0.91 cm** | **−0.05 cm** |
| Previous formula `0.933 × Raw − 1.87` | 2.09 cm | 2.24 cm | −1.85 cm |

The new formula reduces MAE by 65% and nearly eliminates systematic bias.

### 8.5 Recommendations for Station-03

1. **Serial mode validated** for deployment across three independent test sessions
2. **Apply new correction formula** `Corrected = 0.925 × Raw + 1.41` derived from Test-03 Bosch reference data
3. **Install at maximum 3.5 m** from water surface to stay within the reliable operating range
4. **Discard readings after an outlier**: add firmware logic to skip 1–2 readings following an out-of-range event
5. **Readings below 30 cm** have slightly elevated error (~7–8%); with correction applied, reliable down to ~20 cm

---

## 9. Firmware Reference

**File:** `firmware/station-03/src/ultrasonic.cpp`

**Current Configuration:**
```cpp
#define US_SENSOR_TYPE US_SENSOR_US100  // Serial mode selected
#define NUM_READINGS 11                  // Median of 11 samples
#define MAX_RETRIES 20                   // Retries per reading
// Active correction: Corrected = 0.933 × Raw - 1.87
```

**Proposed Update (not yet applied — pending review):**
```cpp
// New formula derived from Test-03 (Bosch-Corrected reference, 37 valid points):
// Corrected = 0.925 × Raw + 1.41
```

**Serial Protocol (US-100):**
- Baud rate: 9600
- Distance command: Send 0x55 → Response: 2 bytes (MSB, LSB) = distance in mm
- Temperature command: Send 0x50 → Response: 1 byte = temperature in °C (offset by 45 °C)
- Timeout: 100 ms

---

## 10. References

1. **US-100_datasheet-01.pdf** (Adafruit) - Serial mode protocol, jumper configuration
2. **US-100.PDF** - Basic specifications, schematic diagram
3. **Bosch GLM 20 Professional** - Reference instrument specifications
4. **US-100_Serial_Mode_Test_Report.md** (Test-01, Jan 25, 2026) - First serial mode test
5. **US-100_Serial_Mode_Test_Report-02.md** (Test-02, Feb 15, 2026) - Second serial mode test
6. **US-100_Trigger_Echo_Mode_Test_Report.md** - Trigger/echo mode test results
7. SAPI system overview (docs/system-overview.md) - System Architecture Documentation

**Datasheet location:** manufacturer datasheets (not redistributed here)
**Raw data:** `docs/tests/us-100/US-100_Serial_mode_test-03/test-03.csv`

---

*Report generated as part of SAPI Master's thesis research - IFSC Florianopolis*
