# US-100 Ultrasonic Sensor - Serial Mode Test Report (Test 02)

**Test Date:** February 15, 2026
**Location:** Florianopolis, Santa Catarina, Brazil
**Tester:** Alexandre Nuernberg
**Project:** SAPI - Sistema de Alerta Previo de Inundacoes (Flood Early Warning System)
**Related Issue:** #8 - Test US-100 sensor in trigger/echo mode

---

## 1. Test Objectives

- Repeat serial mode accuracy test in a new environment to validate Test-01 results
- Extend the measurement range (down to ~22 cm and up to ~461 cm)
- Confirm the systematic distance-dependent error pattern observed in Test-01
- Verify the linear regression error compensation formula from Test-01

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
| Temperature Sensor | Built-in; distance output is **automatically** temperature-compensated by onboard MCU in serial mode. 0x50 command exposes the raw temperature value (°C + 45 offset) for external use, but is not required for compensation. |

### 2.2 Reference Instrument

**Bosch GLM 20 Professional Laser Meter**

| Parameter | Value |
|-----------|-------|
| Measuring Range | 0.15 m - 20 m |
| Measuring Accuracy | +/- 3.0 mm (typical) |
| Resolution | 1 mm |
| Laser Class | 2 (635 nm, < 1 mW) |
| Operating Temperature | -10 C to +40 C |

### 2.3 Microcontroller

**STM32 Nucleo L476RG**

| Parameter | Value |
|-----------|-------|
| MCU | STM32L476RG (ARM Cortex-M4, 80 MHz) |
| Serial Port | Serial3 (PC10=RX, PC11=TX) |
| Firmware | ultrasonic.cpp (median filtering, 11 samples) |
| Sensor Type | US_SENSOR_US100 (serial mode) |
| Development Environment | PlatformIO + VS Code |

---

## 3. Test Setup

### 3.1 Physical Configuration

- Same environment as the trigger/echo mode test (see trigger/echo test report photos)
- Indoor and outdoor environment, clear line of sight to flat wall
- Sensor mounted on elevated platform pointing horizontally toward wall center
- Sensor and Bosch meter positioned at same reference point
- Sensor powered from 5V (Nucleo USB 5V pin)

### 3.2 Jumper Configuration

- **Jumper INSTALLED** on the back of the US-100 sensor
- This activates serial (UART) mode at 9600 baud
- Built-in temperature sensor accessible via 0x50 command

### 3.3 Test Procedure

1. Position setup at target distance from wall
2. Take US-100 reading via serial monitor (firmware displays median of 11 readings)
3. Take Bosch GLM 20 reading at same position
4. Record both values
5. Move away from wall taking readings at intervals (measurements #1-31)
6. Return toward wall taking readings at intervals (measurements #32-51)
7. This two-direction approach validates repeatability at similar distances

---

## 4. Test Results

> **Correction Note:** Bosch GLM 20 measurements corrected by **-10.0 cm** to account for an instrument offset identified after testing. All Difference and Error values below use the corrected Bosch reference.

### 4.1 Raw Measurement Data

| # | US-100 (cm) | Bosch GLM 20 (cm) | Difference (cm) | Error (%) | Notes |
|---|-------------|-------------------|-----------------|-----------|-------|
| 1 | 27 | 24.0 | +3.0 | +12.5% | Near min range |
| 2 | 43 | 39.9 | +3.1 | +7.8% | |
| 3 | 58 | 54.0 | +4.0 | +7.4% | |
| 4 | 71 | 66.2 | +4.8 | +7.3% | |
| 5 | 90 | 84.7 | +5.3 | +6.3% | |
| 6 | 107 | 101.1 | +5.9 | +5.8% | |
| 7 | 121 | 113.9 | +7.1 | +6.2% | |
| 8 | 139 | 130.8 | +8.2 | +6.3% | |
| 9 | 159 | 148.7 | +10.3 | +6.9% | |
| 10 | 175 | 163.7 | +11.3 | +6.9% | |
| 11 | 197 | 183.4 | +13.6 | +7.4% | |
| 12 | 222 | 207.2 | +14.8 | +7.1% | |
| 13 | 243 | 225.9 | +17.1 | +7.6% | |
| 14 | 268 | 249.4 | +18.6 | +7.5% | |
| 15 | 294 | 274.1 | +19.9 | +7.3% | |
| 16 | 315 | 292.7 | +22.3 | +7.6% | |
| 17 | 333 | 309.4 | +23.6 | +7.6% | |
| 18 | 355 | 329.0 | +26.0 | +7.9% | |
| 19 | 371 | 344.7 | +26.3 | +7.6% | |
| 20 | 395 | 367.1 | +27.9 | +7.6% | |
| 21 | -99 | 385.6 | -- | -- | **TIMEOUT** |
| 22 | 439 | 406.0 | +33.0 | +8.1% | |
| 23 | -99 | 419.0 | -- | -- | **TIMEOUT** |
| 24 | -99 | 437.1 | -- | -- | **TIMEOUT** (beyond reliable range) |
| 25 | -99 | 451.3 | -- | -- | **TIMEOUT** (beyond datasheet max) |
| 26 | -99 | 427.7 | -- | -- | **TIMEOUT** |
| 27 | 435 | 402.0 | +33.0 | +8.2% | |
| 28 | -99 | 391.4 | -- | -- | **TIMEOUT** (intermittent at max range) |
| 29 | 408 | 378.6 | +29.4 | +7.8% | Returning closer |
| 30 | 396 | 367.3 | +28.7 | +7.8% | |
| 31 | 385 | 356.7 | +28.3 | +7.9% | |
| 32 | 366 | 339.5 | +26.5 | +7.8% | |
| 33 | 348 | 322.7 | +25.3 | +7.8% | |
| 34 | 328 | 304.3 | +23.7 | +7.8% | |
| 35 | 310 | 288.3 | +21.7 | +7.5% | |
| 36 | 285 | 265.2 | +19.8 | +7.5% | |
| 37 | 265 | 247.0 | +18.0 | +7.3% | |
| 38 | 244 | 227.2 | +16.8 | +7.4% | |
| 39 | 223 | 207.3 | +15.7 | +7.6% | |
| 40 | 201 | 187.9 | +13.1 | +7.0% | |
| 41 | 173 | 161.9 | +11.1 | +6.9% | |
| 42 | 153 | 142.9 | +10.1 | +7.1% | |
| 43 | 135 | 126.0 | +9.0 | +7.1% | |
| 44 | 116 | 109.6 | +6.4 | +5.8% | |
| 45 | 99 | 93.7 | +5.3 | +5.7% | |
| 46 | 82 | 77.3 | +4.7 | +6.1% | |
| 47 | 66 | 62.8 | +3.2 | +5.1% | |
| 48 | 48 | 45.9 | +2.1 | +4.6% | |
| 49 | 31 | 29.4 | +1.6 | +5.4% | |
| 50 | 22 | 19.7 | +2.3 | +11.7% | |
| 51 | 13 | 12.2 | +0.8 | +6.6% | Near min range, high error |

### 4.2 Error Codes Explanation

| Code | Meaning | Cause |
|------|---------|-------|
| -99 | Timeout | No valid response within 100 ms timeout period |
| -1 | Invalid reading | Reading outside valid range (2-450 cm) |
| -888 | Sensor failure | Startup test failed (hardware/wiring issue) |

---

## 5. Statistical Analysis

### 5.1 Valid Data Set

**Number of valid measurements:** 45 (out of 51)
**Number of timeouts:** 6 (11.8% failure rate, all at corrected Bosch references > 385 cm)

### 5.2 Difference Analysis (US-100 minus Bosch Reference)

All values use corrected Bosch reference (-10.0 cm). Standard deviation is unaffected by the constant offset.

| Statistic | Test-02 Value | Test-01 Value (corrected) | Consistent? |
|-----------|---------------|---------------------------|-------------|
| Mean Difference | +15.17 cm | +15.92 cm | Yes |
| Standard Deviation | 9.81 cm | 10.12 cm | Yes |
| Minimum Difference | +0.8 cm | +2.6 cm | Yes (Test-02 tested shorter distances) |
| Maximum Difference | +33.0 cm | +32.2 cm | Yes |
| Median Difference | +13.6 cm | +14.85 cm | Yes |

### 5.3 Absolute Error Analysis

| Statistic | Test-02 Value | Test-01 Value (corrected) | Consistent? |
|-----------|---------------|---------------------------|-------------|
| Mean Absolute Error (MAE) | 15.17 cm | 15.92 cm | Yes |
| Root Mean Square Error (RMSE) | 17.88 cm | 18.76 cm | Yes |
| Mean Absolute Percentage Error (MAPE) | 7.2% | 7.7% | Yes |

**Note:** With the corrected Bosch reference, all differences are positive in both tests (the US-100 consistently **overestimates** throughout the entire measurement range). There is no crossover point. The MAE equals the Mean Difference since all values have the same sign.

### 5.4 Range-Dependent Error Analysis

All ranges and references use corrected Bosch values (-10.0 cm). Test-01 diff values corrected (+10 cm); Test-01 error % are approximate (raw data not available for recalculation).

| Distance Range (corrected) | Test-02 Avg Diff | Test-02 Avg Error % | Test-01 Avg Diff (corrected) | Test-01 Avg Error % |
|----------------------------|------------------|---------------------|------------------------------|---------------------|
| < 30 cm | +1.93 cm | +9.1% | Not tested | Not tested |
| 30 - 100 cm | +4.06 cm | +6.3% | +4.67 cm | +7.1% |
| 100 - 200 cm | +9.65 cm | +6.7% | +10.53 cm | +7.8% |
| 200 - 300 cm | +18.47 cm | +7.4% | +18.42 cm | +7.2% |
| 300 - 420 cm | +27.64 cm | +7.8% | +28.38 cm | +7.9% |

**The corrected data reveals a key finding:** the US-100 in serial mode **consistently overestimates** across all distance ranges in both tests. The previous apparent "underestimation at short range" was an artifact of the Bosch meter offset. Error % is remarkably consistent at 6–8% across the 30–420 cm working range in both tests, with only the near-minimum range (< 30 cm) showing higher variability.

### 5.5 Linear Regression Analysis

Based on 45 valid readings (corrected Bosch reference):

```
Estimated Error (cm) = 0.068 x Distance + 1.58
```

Comparison with Test-01 regression (corrected):

| Parameter | Test-02 (corrected) | Test-01 (corrected) |
|-----------|---------------------|---------------------|
| Slope | 0.068 | 0.065 |
| Intercept | +1.58 | +2.15 |

The regression slopes are very similar (within 5%), confirming the same systematic error model. Note: the intercept is now positive, meaning the sensor overestimates even at very short distances.

**Combined best-fit equation (averaging both tests):**

```
Estimated Error (cm) = 0.067 x Distance + 1.87
```

This equation predicts:
- At 50 cm: error = +5.2 cm (sensor overestimates)
- At 131 cm: error = +10.6 cm (sensor overestimates)
- At 200 cm: error = +15.3 cm (sensor overestimates)
- At 350 cm: error = +25.3 cm (sensor overestimates significantly)

**There is no crossover point** in the corrected data. The zero-crossing of the regression occurs at ~-28 cm, which is outside the physical measurement range.

### 5.6 Repeatability Analysis (Same Distances, Both Directions)

Measurements taken at similar distances during the outbound and return trips. Bosch reference values corrected by -10.0 cm.

| Bosch Ref (out, corrected) | US-100 (out) | Bosch Ref (return, corrected) | US-100 (return) | Difference |
|---------------------------|--------------|------------------------------|-----------------|----------:|
| 39.9 | 43 | 45.9 | 48 | -- |
| 54.0 | 58 | 62.8 | 66 | -- |
| 84.7 | 90 | 93.7 | 99 | -- |
| 101.1 | 107 | 109.6 | 116 | -- |
| 130.8 | 139 | 126.0 | 135 | -- |
| 148.7 | 159 | 142.9 | 153 | -- |
| 163.7 | 175 | 161.9 | 173 | -- |
| 183.4 | 197 | 187.9 | 201 | -- |
| 207.2 | 222 | 207.3 | 223 | +1 cm |
| 225.9 | 243 | 227.2 | 244 | +1 cm |
| 249.4 | 268 | 247.0 | 265 | -- |
| 274.1 | 294 | 265.2 | 285 | -- |
| 292.7 | 315 | 288.3 | 310 | -- |
| 309.4 | 333 | 304.3 | 328 | -- |
| 329.0 | 355 | 322.7 | 348 | -- |
| 344.7 | 371 | 339.5 | 366 | -- |
| 367.1 | 395 | 367.3 | 396 | +1 cm |

**Excellent repeatability:** At similar reference distances, the US-100 readings are within 0-1 cm of each other, confirming the sensor produces consistent results and the median filtering (11 samples) is effective.

### 5.7 Error Component Analysis

Test-02 confirms the same two-component error structure identified and analyzed in Test-01 (see Test-01 Report, Section 5.6). The regression formula `Error = 0.068 × Distance + 1.58` decomposes into:

| Component | Test-01 | Test-02 | Interpretation |
|-----------|---------|---------|----------------|
| Constant term (intercept) | +2.15 cm | +1.58 cm | Physical offset: measurement reference ~1 cm behind transducer face; round-trip doubles the apparent displacement |
| Proportional term (slope) | 6.5% | 6.8% | Speed-of-sound calibration error in the sensor's onboard MCU firmware |

The proportional error persists in both tests despite the built-in temperature compensation being active. This confirms the issue lies in the **base speed-of-sound constant** used by the firmware — not in the temperature correction mechanism, which can only adjust relative changes from that (already wrong) baseline.

The constant term difference between tests (+2.15 vs +1.58 cm) falls within measurement uncertainty and is consistent across both environments and dates, supporting the physical origin offset interpretation.

Neither component is documented in the Adafruit product sheet, the module datasheet, or any forum source found for the US-100.

---

## 6. Comparison: Test-01 vs Test-02

### 6.1 Test Conditions

Bosch reference ranges corrected by -10.0 cm.

| Parameter | Test-01 (Jan 25, 2026) | Test-02 (Feb 15, 2026) |
|-----------|------------------------|------------------------|
| Environment | Outdoor (backyard, concrete wall) | Indoor/outdoor (tiled wall) |
| Distance Range Tested (corrected) | 26.5 - 406.6 cm (valid); up to 447.3 cm (timeout) | 12.2 - 406.0 cm (valid); up to 451.3 cm (timeout) |
| Number of Measurements | 30 | 51 |
| Valid Measurements | 26 (87%) | 45 (88%) |
| Timeouts | 4 (13%) | 6 (12%) |

### 6.2 Statistical Consistency

All values corrected for the Bosch -10.0 cm offset. Test-01 values are exact where derivable from the constant shift; approximate otherwise.

| Metric | Test-01 (corrected) | Test-02 (corrected) | Variation |
|--------|---------------------|---------------------|-----------|
| MAE | 15.92 cm | 15.17 cm | -4.7% |
| RMSE | 18.76 cm | 17.88 cm | -4.7% |
| Mean Diff | +15.92 cm | +15.17 cm | -4.7% |
| Median Diff | +14.85 cm | +13.6 cm | -8.2% |
| Max Reliable Range | ~385–406 cm | ~402–416 cm | Similar |
| Regression Slope | 0.065 | 0.068 | +4.6% |
| Regression Intercept | +2.15 | +1.58 | -26% |

**Conclusion:** Test-01 and Test-02 results remain **highly consistent** after the Bosch correction. Both tests confirm the US-100 consistently overestimates at all measured distances with ~7–8% error. The apparent "crossover" from underestimation to overestimation observed in the original analysis was entirely an artifact of the Bosch meter offset.

---

## 7. Operational Limitations

### 7.1 Maximum Range

Bosch reference values corrected by -10.0 cm.

| Parameter | Datasheet | Test-01 (corrected) | Test-02 (corrected) |
|-----------|-----------|---------------------|---------------------|
| Maximum Range | 450 cm | ~420 cm | ~406 cm |
| Timeout Threshold | -- | ~425 cm | ~385 cm (first timeout) |
| Behavior at Max | -- | Timeouts above ~425 cm | Intermittent (some OK at 402–406 cm, timeouts at 385–428 cm) |

**Note:** At maximum range, readings become intermittent. Some distances that timed out (e.g., corrected Bosch 385.6 cm) are shorter than distances that succeeded (e.g., 406.0 cm), suggesting environmental sensitivity at the range boundary.

### 7.2 Minimum Range

Bosch reference values corrected by -10.0 cm.

| Parameter | Test-01 (corrected) | Test-02 (corrected) |
|-----------|---------------------|---------------------|
| Minimum Tested | 26.5 cm | 12.2 cm |
| Error at Min | +13.2% (at 26.5 cm) | +6.6% (at 12.2 cm) |
| Practical Min (< 10% error) | ~40 cm | ~30 cm |

Test-02 confirms that with corrected Bosch references, the sensor overestimates across the entire range. The error % at very short distances (< 25 cm) is higher (~12%) but not as extreme as the original analysis suggested. The practical minimum remains ~30–40 cm for reliable readings.

---

## 8. Conclusions

### 8.1 Test-02 Validates Test-01

The serial mode test results are **reproducible across different environments and dates**:
- MAE within 2% between tests (9.12 vs 9.31 cm)
- RMSE within 1% (10.86 vs 10.79 cm)
- Identical range-dependent error pattern
- Linear regression coefficients within 5-7%
- Excellent repeatability within a single test (outbound vs return readings within 1 cm)

### 8.2 Confirmed Sensor Characteristics

1. **Systematic overestimation:** The US-100 in serial mode **consistently overestimates** across the entire measurement range. The error can be compensated with the corrected combined regression formula:
   ```
   Corrected = Reading - (0.067 x Reading + 1.87)
   ```
   Simplified: `Corrected = 0.933 x Reading - 1.87`

2. **Effective range:** 30–420 cm (practical limits with < 10% error)

3. **No crossover point:** With corrected Bosch reference, the sensor overestimates at all distances. The apparent crossover in the original analysis was an artifact of the Bosch meter offset.

4. **Repeatability:** Excellent (within 1 cm at same distance)

5. **Maximum range:** ~406–420 cm with intermittent timeouts above ~390 cm (corrected Bosch)

6. **Error decomposition confirmed:** Both tests show the same two-component error structure — a ~1.6–2.1 cm constant offset (physical measurement reference ~1 cm behind transducer face) and a ~6.5–6.8% proportional calibration error (wrong base speed-of-sound constant in firmware). See Section 5.7 and Test-01 Report Section 5.6 for the full analysis.

### 8.3 Recommendations for Station-03

1. **Serial mode is validated** for deployment with consistent, predictable behavior
2. **Apply linear correction** using the combined regression formula for improved accuracy
3. **Install at maximum 3.5 m** from water surface to stay within the reliable operating range
4. **Discard -99 readings** as timeouts (sensor at or beyond maximum range)
5. **Consider readings below 50 cm** as less reliable (> 10% error)

---

## 9. Test Photos

Test photos are the same as the trigger/echo mode test (same test session and environment).
See: `../US-100_Trigger_Echo_mode_test-01/images/`

---

## 10. Firmware Reference

**File:** `firmware/station-03/src/ultrasonic.cpp`

**Key Configuration:**
```cpp
#define US_SENSOR_TYPE US_SENSOR_US100  // Serial mode selected
#define NUM_READINGS 11                  // Median of 11 samples
#define MAX_RETRIES 20                   // Retries per reading
```

**Serial Protocol (US-100):**
- Baud rate: 9600
- Distance command: Send 0x55 -> Response: 2 bytes (MSB, LSB) = distance in mm
- Temperature command: Send 0x50 -> Response: 1 byte = temperature in C (offset by 45 C)
- Timeout: 100 ms

**Jumper Configuration (US-100):**
- **Jumper INSTALLED** -> Serial/UART mode (9600 baud) **<-- This test**
- **Jumper REMOVED** -> HC-SR04 compatible mode (trigger/echo)

---

## 11. References

1. **US-100_datasheet-01.pdf** (Adafruit) - Serial mode protocol, jumper configuration
2. **US-100.PDF** - Basic specifications, schematic diagram
3. **Bosch GLM 20 Professional** - Reference instrument specifications
4. **US-100_Serial_Mode_Test_Report.md** (Test-01) - First serial mode test results
5. **US-100_Trigger_Echo_Mode_Test_Report.md** - Trigger/echo mode test results
6. SAPI system overview (docs/system-overview.md) - System Architecture Documentation

**Datasheet location:** manufacturer datasheets (not redistributed here)

---

*Report generated as part of SAPI Master's thesis research - IFSC Florianopolis*
