/**
 * @file stationConfig.cpp
 * @brief Implementation of station calibration functions
 *
 * @author Alexandre Nuernberg
 * @date 2025-12-30
 * @note 2026-03-01 - Station-03 added to stationConfigs[] in stationConfig.h
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

#include "stationConfig.h"

/**
 * @brief Find station configuration by ID
 */
const StationConfig* getStationConfig(uint32_t stationId) {
    // Linear search through configuration array
    for (uint8_t i = 0; i < NUM_STATIONS; i++) {
        if (stationConfigs[i].idStation == stationId) {
            return &stationConfigs[i];
        }
    }
    
    // Station not found
    return nullptr;
}

/**
 * @brief Calculate calibrated water level from raw ultrasonic reading
 */
int32_t calculateCalibratedLevel(uint32_t stationId, int32_t rawLevel) {
    // Get station configuration
    const StationConfig* config = getStationConfig(stationId);
    
    // Station not found - return raw value unchanged
    if (config == nullptr) {
        Serial.printf("⚠️ Station %lu not found in config - using raw value\n", stationId);
        return rawLevel;
    }
    
    // Station disabled - return raw value unchanged
    if (!config->enabled) {
        Serial.printf("⚠️ Station %lu (%s) is disabled - using raw value\n", 
                     stationId, config->name);
        return rawLevel;
    }
    
    // Station has no ultrasonic sensor - return raw value unchanged
    if (!config->hasUltrasonicSensor) {
        // This is normal for meteorological stations
        return rawLevel;
    }
    
    // Calculate calibrated level
    // Formula: level_calibrated = levelZero - distance_raw
    int32_t calibratedLevel = (int32_t)(config->levelZero - rawLevel);
    
    // Log calibration (only if value changed significantly)
    static int32_t lastRaw[10] = {0};  // Cache last raw values per station
    static uint8_t stationIndex = 0;
    
    // Find station index for caching (simple approach)
    for (uint8_t i = 0; i < NUM_STATIONS; i++) {
        if (stationConfigs[i].idStation == stationId) {
            stationIndex = i;
            break;
        }
    }
    
    // Only log if value changed by more than 1 cm
    if (abs(rawLevel - lastRaw[stationIndex]) > 1) {
        Serial.printf("📏 Station %lu (%s): Raw=%d cm → Calibrated=%d cm (Zero=%.1f)\n",
                     stationId, config->name, rawLevel, calibratedLevel, config->levelZero);
        lastRaw[stationIndex] = rawLevel;
    }
    
    return calibratedLevel;
}

/**
 * @brief Calculate precipitation in mm from pulse count
 */
float calculatePrecipitation(uint32_t stationId, int16_t pulses) {
    // Invalid pulse count
    if (pulses < 0) {
        return -99.0;
    }
    
    // Get station configuration
    const StationConfig* config = getStationConfig(stationId);
    
    // Station not found
    if (config == nullptr) {
        Serial.printf("⚠️ Station %lu not found - cannot calculate precipitation\n", stationId);
        return -99.0;
    }
    
    // Station disabled
    if (!config->enabled) {
        return -99.0;
    }
    
    // Station has no rain gauge
    if (!config->hasRainGauge) {
        // This is normal for stations without precipitation sensor
        return -99.0;
    }
    
    // Calculate precipitation in mm
    // Formula: precipitation_mm = pulses × precipitationPerPulse
    float precipitation_mm = pulses * config->precipitationPerPulse;
    
    // Log conversion (only if pulses > 0)
    static int16_t lastPulses[10] = {0};  // Cache last pulse values
    static uint8_t stationIndex = 0;
    
    // Find station index for caching
    for (uint8_t i = 0; i < NUM_STATIONS; i++) {
        if (stationConfigs[i].idStation == stationId) {
            stationIndex = i;
            break;
        }
    }
    
    // Only log if value changed
    if (pulses != lastPulses[stationIndex]) {
        if (pulses > 0) {
            Serial.printf("🌧️ Station %lu (%s): %d pulses × %.2f mm/pulse = %.2f mm\n",
                         stationId, config->name, pulses, 
                         config->precipitationPerPulse, precipitation_mm);
        }
        lastPulses[stationIndex] = pulses;
    }
    
    return precipitation_mm;
}

/**
 * @brief Print station configuration to serial (debug)
 */
void printStationConfigs() {
    Serial.println("\n========================================");
    Serial.println("📊 STATION CONFIGURATIONS");
    Serial.println("========================================");
    
    for (uint8_t i = 0; i < NUM_STATIONS; i++) {
        const StationConfig* cfg = &stationConfigs[i];
        
        Serial.printf("\n📍 Station %lu: %s\n", cfg->idStation, cfg->name);
        Serial.printf("   Status: %s\n", cfg->enabled ? "✅ Enabled" : "❌ Disabled");
        
        // Ultrasonic sensor info
        if (cfg->hasUltrasonicSensor) {
            Serial.printf("   Level Sensor: Ultrasonic\n");
            Serial.printf("   Level Zero: %.1f cm\n", cfg->levelZero);
            Serial.printf("   Formula: level = %.1f - distance_raw\n", cfg->levelZero);
        } else {
            Serial.printf("   Level Sensor: None\n");
        }
        
        // Rain gauge info
        if (cfg->hasRainGauge) {
            Serial.printf("   Rain Gauge: Yes\n");
            Serial.printf("   Conversion: %.2f mm per pulse\n", cfg->precipitationPerPulse);
            Serial.printf("   Formula: precipitation = pulses × %.2f\n", cfg->precipitationPerPulse);
        } else {
            Serial.printf("   Rain Gauge: None\n");
        }
    }
    
    Serial.println("\n========================================");
    Serial.printf("Total stations configured: %d\n", NUM_STATIONS);
    Serial.println("========================================\n");
}