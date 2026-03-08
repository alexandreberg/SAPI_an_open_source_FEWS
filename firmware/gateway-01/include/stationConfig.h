/**
 * @file stationConfig.h
 * @brief Station calibration configuration for ultrasonic level sensors
 * 
 * This module provides calibration parameters for each monitoring station.
 * It converts raw ultrasonic distance readings to calibrated water level values.
 * 
 * @author Alexandre Nuernberg
 * @date 2025-12-30
 * @version 1.1.0 - Added Station-03 calibration (2026-03-01)
 *
 * Theory of Operation:
 * -------------------
 * Ultrasonic sensors measure DISTANCE from sensor to water surface.
 * When water level INCREASES, distance DECREASES.
 * We need to invert this relationship for intuitive graphs.
 *
 * Calibration Formula:
 * -------------------
 * level_calibrated = levelZero - distance_raw
 *
 * Where:
 * - levelZero: Distance when water is at reference level (0 cm)
 * - distance_raw: Current reading from ultrasonic sensor
 * - level_calibrated: Actual water level above reference
 *
 * Example (Station-01):
 * -------------------
 * levelZero = 291 cm (measured with tape when river is at zero mark)
 *
 * Scenario 1 - River empty:
 *   distance_raw = 291 cm → level = 291 - 291 = 0 cm ✓
 *
 * Scenario 2 - River medium:
 *   distance_raw = 200 cm → level = 291 - 200 = 91 cm ✓
 *
 * Scenario 3 - River full:
 *   distance_raw = 50 cm → level = 291 - 50 = 241 cm ✓
 *
 * Example (Station-03):
 * -------------------
 * levelZero = 236 cm (calibrated 2026-03-01: sensor reads 199 cm at river level 37 cm)
 *
 * Scenario 1 - River at calibration mark:
 *   distance_raw = 199 cm → level = 236 - 199 = 37 cm ✓
 *
 * Scenario 2 - River empty:
 *   distance_raw = 236 cm → level = 236 - 236 = 0 cm ✓
 *
 * @note Web interface for configuration will be implemented in Phase 2
 * @see main.cpp for usage examples
 *
 * SPDX-License-Identifier: AGPL-3.0-or-later
 * Copyright (C) 2024–2026 Alexandre Nuernberg <alexandreberg@gmail.com>
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program. If not, see <https://www.gnu.org/licenses/>.
 */

#ifndef STATION_CONFIG_H
#define STATION_CONFIG_H

#include <Arduino.h>

/**
 * @struct StationConfig
 * @brief Configuration parameters for a single monitoring station
 * 
 * Contains calibration and identification data for each station.
 * All stations must be configured here before deployment.
 */
struct StationConfig {
    uint32_t idStation;              ///< Unique station identifier (matches database)
    float levelZero;                 ///< Distance (cm) when water level is at zero reference
    bool hasUltrasonicSensor;        ///< true if station has ultrasonic level sensor
    bool hasRainGauge;               ///< true if station has precipitation sensor
    float precipitationPerPulse;     ///< Precipitation in mm per pulse (typically 0.25mm)
    const char* name;                ///< Human-readable station name (for logs)
    bool enabled;                    ///< Station is active and should be processed
};

/**
 * @brief Array of all configured stations
 * 
 * Add new stations here as they are deployed.
 * Ensure idStation matches the database configuration.
 * 
 * Calibration procedure for new stations:
 * 
 * For Ultrasonic Level Sensors:
 * 1. Install ultrasonic sensor at station
 * 2. Mark reference zero level on structure
 * 3. Measure distance from sensor to zero mark with tape
 * 4. Enter this value as levelZero
 * 5. Deploy and verify with test readings
 * 
 * For Rain Gauge Sensors:
 * 1. Install rain gauge (typically 0.25mm per pulse)
 * 2. Verify pulse rate from sensor datasheet
 * 3. Enter precipitationPerPulse value
 * 4. Test with known water volume
 */
const StationConfig stationConfigs[] = {
    // Station 1: FLN Norte - Has ultrasonic sensor only
    {
        .idStation = 1,
        .levelZero = 291.0,        // Measured 2025-12-30
        .hasUltrasonicSensor = true,
        .hasRainGauge = false,     // No rain gauge
        .precipitationPerPulse = 0.0,
        .name = "FLN Norte - Estacao-01",
        .enabled = true
    },

    
    // Station 2: Meteorological - Rain gauge + weather sensors
    {
        .idStation = 2,
        .levelZero = 0.0,          // N/A - no level sensor
        .hasUltrasonicSensor = false,
        .hasRainGauge = true,      // Has rain gauge
        .precipitationPerPulse = 0.25,  // Standard 0.25mm per pulse
        .name = "FLN Norte - Estacao-02",
        .enabled = true
    },

    // Station 3: FLN Norte - Advanced water level with US-100 temperature compensation
    // Calibrated 2026-03-01: sensor reads 199 cm at river level 37 cm → levelZero = 199 + 37 = 236 cm
    {
        .idStation = 3,
        .levelZero = 236.0,
        .hasUltrasonicSensor = true,
        .hasRainGauge = false,     // No rain gauge
        .precipitationPerPulse = 0.0,
        .name = "FLN Norte - Estacao-03",
        .enabled = true
    }
};

/// Number of configured stations
const uint8_t NUM_STATIONS = sizeof(stationConfigs) / sizeof(StationConfig);

/**
 * @brief Find station configuration by ID
 * 
 * Searches the configuration array for a station with the given ID.
 * 
 * @param stationId Station identifier to search for
 * @return Pointer to StationConfig if found, nullptr if not found
 * 
 * @note Returns nullptr for unknown stations
 * @note Returned pointer is valid for program lifetime (const array)
 */
const StationConfig* getStationConfig(uint32_t stationId);

/**
 * @brief Calculate calibrated water level from raw ultrasonic reading
 * 
 * Converts raw distance measurement to calibrated water level.
 * 
 * Formula: level_calibrated = levelZero - distance_raw
 * 
 * @param stationId Station identifier
 * @param rawLevel Raw distance reading from ultrasonic sensor (cm)
 * @return Calibrated water level (cm), or rawLevel unchanged if:
 *         - Station not found
 *         - Station has no ultrasonic sensor
 *         - Station is disabled
 * 
 * @note For stations without ultrasonic sensors, returns rawLevel unchanged
 * @note For disabled stations, returns rawLevel unchanged
 * 
 * Example usage:
 * @code
 * int32_t rawDistance = 254;  // cm from ultrasonic sensor
 * int32_t calibratedLevel = calculateCalibratedLevel(1, rawDistance);
 * // Result: 291 - 254 = 37 cm
 * @endcode
 */
int32_t calculateCalibratedLevel(uint32_t stationId, int32_t rawLevel);

/**
 * @brief Calculate precipitation in mm from pulse count
 * 
 * Converts raw rain gauge pulse count to precipitation in millimeters.
 * Uses station-specific conversion factor (typically 0.25mm per pulse).
 * 
 * Formula: precipitation_mm = pulses × precipitationPerPulse
 * 
 * @param stationId Station identifier
 * @param pulses Raw pulse count from rain gauge sensor
 * @return Precipitation in mm, or -99.0 if:
 *         - Station not found
 *         - Station has no rain gauge
 *         - Station is disabled
 *         - Pulses value is invalid (<0)
 * 
 * @note Returns -99.0 for stations without rain gauge (normal behavior)
 * @note Returns 0.0 for zero pulses (no precipitation)
 * 
 * Example usage:
 * @code
 * int16_t pulses = 48;  // from rain gauge
 * float precip_mm = calculatePrecipitation(5, pulses);
 * // Result: 48 × 0.25 = 12.00 mm
 * @endcode
 */
float calculatePrecipitation(uint32_t stationId, int16_t pulses);

/**
 * @brief Print station configuration to serial (debug)
 * 
 * Outputs all configured stations and their parameters.
 * Useful for verifying configuration at startup.
 * 
 * @note Only call this if Serial is initialized
 */
void printStationConfigs();

#endif // STATION_CONFIG_H