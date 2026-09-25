# US-100 Ultrasonic Sensor - Serial Mode Test Report

**Test Date:** January 25, 2026
**Location:** Florianópolis, Santa Catarina, Brazil
**Tester:** Alexandre Nuernberg
**Project:** SAPI - Sistema de Alerta Prévio de Inundações (Flood Early Warning System)

---

## 1. Test Objectives

- Validate US-100 ultrasonic sensor accuracy in serial mode
- Compare measurements against a reference laser meter (Bosch GLM 20)
- Determine measurement offset and systematic errors
- Identify operational range limitations
- Evaluate suitability for water level monitoring applications

---

## 2. Equipment Used

### 2.1 Device Under Test (DUT)

**US-100 Ultrasonic Sensor**

| Parameter | Value |
|-----------|-------|
| Operating Mode | Serial (UART) - **Jumper installed** |
| Measuring Range | 2 cm - 450 cm |
| Resolution | 1 mm (sensor output in mm), 1 cm (after firmware `÷10` integer division) |
| Beam Angle | ~15° total cone angle (±7.5° half-angle from center axis) |
| Operating Frequency | 40 kHz |
| Communication | 9600 baud, 8N1 |
| Command Byte | 0x55 |
| Response | 2 bytes (MSB + LSB) = distance in mm |
| Operating Voltage | 2.4V - 5.5V |
| Temperature Sensor | Built-in; raw value readable via 0x50 command (returns °C + 45 offset) |
| Auto Temp. Compensation | **Yes — automatic in serial mode.** The onboard MCU reads the internal temperature sensor and corrects the speed of sound before computing the distance output. Sending 0x55 already returns a temperature-compensated distance. The 0x50 command exposes the temperature value externally but is **not required** for the compensation to work. |

### 2.2 Reference Instrument

**Bosch GLM 20 Professional Laser Meter**

| Parameter | Value |
|-----------|-------|
| Measuring Range | 0.15 m - 20 m |
| Measuring Accuracy | ± 3.0 mm (typical) |
| Resolution | 1 mm |
| Laser Class | 2 (635 nm, < 1 mW) |
| Operating Temperature | -10°C to +40°C |

### 2.3 Microcontroller

**STM32 Nucleo L476RG**

| Parameter | Value |
|-----------|-------|
| MCU | STM32L476RG (ARM Cortex-M4) |
| Serial Port | Serial3 (PC10=RX, PC11=TX) |
| Firmware | ultrasonic.cpp (median filtering, 11 samples) |
| Development Environment | PlatformIO + VS Code |

---

## 3. Test Setup

### 3.1 Physical Configuration

- Outdoor environment (backyard)
- Clear line of sight to a flat concrete wall
- Sensor mounted on elevated platform (chair) pointing horizontally toward wall center
- Sensor and Bosch meter positioned at same reference point
- Multiple distances tested by repositioning the setup

### 3.2 Test Procedure

1. Position setup at target distance from wall
2. Take US-100 reading via serial monitor (firmware displays median of 11 readings)
3. Take Bosch GLM 20 reading at same position
4. Record both values
5. Repeat for distances ranging from ~30 cm to ~460 cm

---

## 4. Test Results

> **Correction Note:** Bosch GLM 20 measurements corrected by **-10.0 cm** to account for an instrument offset identified after testing. All Difference and Error values below use the corrected Bosch reference.

### 4.1 Raw Measurement Data

| # | US-100 (cm) | Bosch GLM 20 (cm) | Difference (cm) | Error (%) | Notes |
|---|-------------|-------------------|-----------------|-----------|-------|
| 1 | 64 | 61.4 | +2.6 | +4.2% | |
| 2 | 98 | 91.9 | +6.1 | +6.6% | |
| 3 | 144 | 135.3 | +8.7 | +6.4% | |
| 4 | 183 | 176.3 | +6.7 | +3.8% | |
| 5 | 251 | 235.9 | +15.1 | +6.4% | |
| 6 | 287 | 266.5 | +20.5 | +7.7% | |
| 7 | 328 | 304.4 | +23.6 | +7.8% | |
| 8 | 359 | 332.6 | +26.4 | +7.9% | |
| 9 | 404 | 373.3 | +30.7 | +8.2% | |
| 10 | 419 | 389.8 | +29.2 | +7.5% | |
| 11 | 438 | 406.6 | +31.4 | +7.7% | Near max range |
| 12 | -99 | 425.4 | — | — | **TIMEOUT** (exceeded range) |
| 13 | -99 | 447.3 | — | — | **TIMEOUT** (exceeded range) |
| 14 | -99 | 413.0 | — | — | **TIMEOUT** (exceeded range) |
| 15 | 418 | 385.8 | +32.2 | +8.3% | |
| 16 | 383 | 355.5 | +27.5 | +7.7% | |
| 17 | 351 | 325.0 | +26.0 | +8.0% | |
| 18 | 317 | 295.2 | +21.8 | +7.4% | |
| 19 | 280 | 259.9 | +20.1 | +7.7% | |
| 20 | 232 | 217.4 | +14.6 | +6.7% | |
| 21 | 141 | 166.8 | -25.8 | -15.5% | **OUTLIER** (excluded) |
| 22 | 178 | 164.6 | +13.4 | +8.1% | |
| 23 | 153 | 135.7 | +17.3 | +12.8% | |
| 24 | 128 | 118.5 | +9.5 | +8.0% | |
| 25 | 109 | 101.4 | +7.6 | +7.5% | |
| 26 | 91 | 84.6 | +6.4 | +7.6% | |
| 27 | 74 | 68.6 | +5.4 | +7.9% | |
| 28 | 60 | 56.2 | +3.8 | +6.8% | |
| 29 | 44 | 40.3 | +3.7 | +9.2% | |
| 30 | 30 | 26.5 | +3.5 | +13.2% | Near min range |

### 4.2 Error Codes Explanation

| Code | Meaning | Cause |
|------|---------|-------|
| -99 | Timeout | No valid response within 100ms timeout period |
| -1 | Invalid reading | Reading outside valid range (2-450 cm) |
| -888 | Sensor failure | Startup test failed (hardware/wiring issue) |

---

## 5. Statistical Analysis

### 5.1 Valid Data Set (excluding timeouts and outlier #21)

**Number of valid measurements:** 26 (out of 30)

### 5.2 Difference Analysis (US-100 minus Bosch Reference)

All values computed from corrected Bosch reference (-10.0 cm). All 26 differences are positive.

| Statistic | Value |
|-----------|-------|
| Mean Difference | +15.92 cm |
| Standard Deviation | 10.12 cm |
| Minimum Difference | +2.6 cm |
| Maximum Difference | +32.2 cm |
| Median Difference | +14.85 cm |

### 5.3 Absolute Error Analysis

| Statistic | Value |
|-----------|-------|
| Mean Absolute Error (MAE) | 15.92 cm |
| Root Mean Square Error (RMSE) | 18.76 cm |
| Mean Absolute Percentage Error (MAPE) | 7.7% |

**Note:** With the corrected Bosch reference, all differences are positive — the US-100 consistently **overestimates** at every measured distance. MAE equals the Mean Difference since all values have the same sign.

### 5.4 Range-Dependent Error Analysis

| Distance Range (corrected) | Avg Difference | Avg Error % | Trend |
|----------------------------|----------------|-------------|-------|
| < 30 cm | +3.5 cm | +13.2% | Overestimates (high % at very short range) |
| 30 - 100 cm | +4.67 cm | +7.1% | Overestimates |
| 100 - 200 cm | +10.53 cm | +7.8% | Overestimates |
| 200 - 300 cm | +18.42 cm | +7.2% | Overestimates |
| 300 - 420 cm | +28.38 cm | +7.9% | Overestimates significantly |

**Key finding:** The corrected data shows a consistent overestimation across all ranges (~7–8% in the 30–420 cm working range). The apparent "underestimation at short range" in the original analysis was an artifact of the Bosch meter offset.

### 5.5 Linear Regression Analysis

A linear relationship exists between actual distance (corrected Bosch) and error:

```
Estimated Error (cm) ≈ 0.065 × Distance + 2.15
```

**There is no crossover point** — the regression predicts overestimation across the entire measurement range. The zero-crossing would occur at ~-33 cm, which is physically impossible.

This suggests:
- **At all measured distances:** US-100 overestimates consistently
- **Error increases with distance:** From ~+4 cm at 30 cm to ~+32 cm at 400 cm
- **Error % is remarkably stable:** ~7–8% across the 30–420 cm working range

### 5.6 Error Component Analysis

The linear regression formula `Error = 0.065 × Distance + 2.15` reveals that the systematic overestimation has **two physically distinct components** that can be separated analytically:

#### 5.6.1 Constant Component (~2.15 cm) — Physical Origin Offset

The positive intercept represents a **distance-independent fixed error**. This is consistent with the sensor not measuring from the front face of the transducers but from a reference point located approximately 1 cm inside the housing. Since the ultrasonic pulse travels the full round-trip (sensor → target → sensor), a 1 cm physical displacement of the measurement origin translates to approximately 2 cm of additional reported distance at every range.

Neither the Adafruit product sheet nor the module datasheet documents any physical measurement origin offset for the US-100.

#### 5.6.2 Proportional Component (~6.5%) — Speed-of-Sound Calibration Error

The slope term (~6.5%) represents an error that **grows proportionally with distance** — the classic fingerprint of a wrong speed-of-sound constant in the sensor's onboard MCU. The internal distance computation is:

    distance = (echo_time × speed_of_sound) / 2

If the firmware's speed constant is approximately 6.5% higher than the actual speed of sound at the measurement conditions, every reading is inflated by that same fraction, regardless of distance.

Critically, this proportional error **persists even with temperature compensation active**. The built-in temperature correction adjusts the speed constant for temperature-dependent variations, but if the base constant is already wrong, compensation only corrects relative changes around a wrong baseline — it cannot remove the systematic bias.

Neither datasheet nor any forum source found for the US-100 documents this calibration error.

#### 5.6.3 Summary

| Component | Magnitude | Physical Origin | Documented in Datasheet? |
|-----------|-----------|----------------|--------------------------|
| Constant offset | ~2.15 cm | Measurement reference ~1 cm behind transducer face | No |
| Proportional error | ~6.5% | Wrong speed-of-sound base constant in onboard firmware | No |

The datasheet specifies accuracy as `0.3 cm + 1%`. The tested unit performs at approximately `2.15 cm + 6.5%`, significantly outside specification. Whether this reflects a characteristic of all US-100 sensors or an individual unit defect requires testing additional units.

---

## 6. Operational Limitations

### 6.1 Maximum Range

Bosch reference values corrected by -10.0 cm.

| Parameter | Datasheet | Observed (corrected) |
|-----------|-----------|----------------------|
| Maximum Range | 450 cm | ~385–406 cm (reliable, intermittent) |
| Timeout Threshold | — | ~413 cm (corrected) |

**Note:** The US-100 returned timeout errors (-99) when the corrected Bosch reference exceeded ~413 cm. The last successful outbound reading was at corrected Bosch 406.6 cm (row 11); the last return reading was at 385.8 cm (row 15). The maximum reliable operating range is approximately **385–406 cm** (corrected).

### 6.2 Minimum Range

The minimum reliable distance appears to be around **40–50 cm** (corrected Bosch). At shorter distances the error percentage increases: +9.2% at 40 cm, +13.2% at 26.5 cm (corrected minimum tested).

### 6.3 Beam Angle Considerations

The US-100 datasheet specifies **"Induction angle: not more than 15°"**. This is the **total cone angle** (full beam width), confirmed from the datasheet wording and consistent with the HC-SR04 convention. The half-angle from the center axis is therefore **±7.5°**.

At a given distance, the beam footprint diameter on the water surface is:

```
Diameter = 2 × Distance × tan(7.5°) = 2 × Distance × 0.1317
```

| Distance | Footprint diameter |
|----------|--------------------|
| 50 cm    | ~13 cm             |
| 100 cm   | ~26 cm             |
| 200 cm   | ~53 cm             |
| 350 cm   | ~92 cm             |
| 400 cm   | ~105 cm            |

This wide footprint means any bridge structure, vegetation, or debris within that circle at the measured distance can cause spurious reflections — which is the primary motivation for median filtering of multiple readings.

This wide cone can also cause:
- Reflections from nearby objects
- Edge effects near walls/obstacles
- Reduced accuracy when target is not perpendicular to the sensor axis

---

## 7. Comparison: US-100 vs Bosch GLM 20

| Parameter | US-100 (Serial Mode) | Bosch GLM 20 |
|-----------|---------------------|--------------|
| Technology | Ultrasonic (40 kHz) | Laser (635 nm) |
| Accuracy | ±5% typical | ±3.0 mm |
| Range | 2-420 cm (observed) | 15-2000 cm |
| Resolution | 1 mm | 1 mm |
| Beam Width | ~15° cone | ~9-18 mm spot |
| Temp. Sensor | Yes — distance output is **automatically** temperature-compensated internally; 0x50 cmd exposes the raw temperature value | N/A |
| Weather Affected | Less (no optical) | Yes (rain, fog) |
| Cost | ~$3-5 USD | ~$50-70 USD |
| Best Use Case | Water level monitoring | Precision measurement |

---

## 8. Conclusions

### 8.1 Accuracy Assessment

1. **Overall accuracy:** The US-100 shows approximately 7–8% overestimation error across the 30–420 cm working range. Within the practical range (50–380 cm), MAPE is ~7%, which is acceptable for water level monitoring where trends and significant changes are more important than absolute precision.

2. **Systematic overestimation:** With the corrected Bosch reference, the US-100 **consistently overestimates** at all measured distances. There is no crossover point. The original analysis showing "underestimation at short range / overestimation at long range" was entirely an artifact of the Bosch meter offset.

3. **Precision:** The firmware's median filtering (11 samples) helps eliminate outliers, but individual readings can still vary by several centimeters.

4. **Error decomposition:** The systematic error separates into two physically distinct components — a ~2.15 cm constant offset (measurement reference point ~1 cm behind transducer face) and a ~6.5% proportional term (wrong base speed-of-sound constant in firmware). Neither is documented by the manufacturer. The tested unit performs at approximately `2.15 cm + 6.5%`, far outside the datasheet spec of `0.3 cm + 1%`. See Section 5.6 for the full analysis.

### 8.2 Suitability for SAPI Project

| Criterion | Assessment |
|-----------|------------|
| Range for bridge installations (3-5m) | **Marginal** - Near maximum range limit |
| Reliability | **Good** - Consistent readings when within range |
| Accuracy for flood alerts | **Acceptable** - ±10-20 cm at max range |
| Temperature sensor | **Yes — automatic.** Distance output is temperature-compensated internally by the onboard MCU. Use 0x50 to log/display the temperature value. |
| Power consumption | **To be tested** - Important for solar operation |

### 8.3 Recommendations

1. **For Station-03 deployment:**
   - Install sensor at maximum 3.5m from water surface to maintain reliable operation
   - Consider AJ-SR04M as alternative for longer range requirements (up to 8m)
   - Implement software calibration offset based on installation distance

2. **Calibration procedure:**
   - Apply linear regression correction based on corrected test data:
     `Corrected = Reading - (0.065 × Reading + 2.15)`
     Simplified: `Corrected = 0.935 × Reading - 2.15`
   - Alternatively, after installation take a reference measurement with tape/laser, calculate the offset at that specific distance, and apply it in firmware.

3. **Error handling:**
   - Treat -99 (timeout) as sensor failure, not valid reading
   - Consider installing backup sensor for redundancy
   - Log all readings including failures for quality analysis

---

## 9. Test Photos

| Photo | Description |
|-------|-------------|
| US-100_Serial_Mode_Test-01.JPG | Test setup overview - outdoor environment |
| US-100_Serial_Mode_Test-02.JPG | Setup with power supply and laptop |
| US-100_Serial_Mode_Test-03.JPG | Elevated platform pointing to wall |
| US-100_Serial_Mode_Test-04.JPG | Bosch GLM 20 displaying 3.145m |
| US-100_Serial_Mode_Test-07.JPG | Sensor pointing at concrete wall target |

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
- **Distance command:** Send `0x55` → Response: 2 bytes (MSB, LSB) = distance in millimeters
- **Temperature command:** Send `0x50` → Response: 1 byte = temperature in °C (offset by 45°C, so value 45 = 0°C)
- Timeout: 100 ms

**Mode Selection (Jumper on back of sensor):**
- **Jumper installed** → Serial/UART mode (9600 baud)
- **Jumper removed** → HC-SR04 compatible mode (trigger/echo)

---

## 11. References

1. **US-100_datasheet-01.pdf** (Adafruit) - Serial mode protocol, jumper configuration, command bytes (0x55 for distance, 0x50 for temperature)
2. **US-100.PDF** - Basic specifications, schematic diagram, wiring diagram
3. **US_100_ULTRASONIC_SENSOR_MODULE.pdf** - Specifications (precision up to 1mm), HC-SR04 mode example sketch
4. **Bosch GLM 20 Professional** - Reference instrument specifications (±3.0mm accuracy)
5. SAPI system overview (docs/system-overview.md) - System Architecture Documentation

**Datasheet location:** manufacturer datasheets (not redistributed here)

---

*Report generated as part of SAPI Master's thesis research - IFSC Florianópolis*
