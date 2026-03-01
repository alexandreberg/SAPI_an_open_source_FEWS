/**
 * @file adc.cpp
 * @brief Implementation of ADC voltage measurement functions
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

#include "adc.h"

/* ADC pins */
#define PIN_VBAT PC1 // ADC A4
#define PIN_PANEL PC0 // ADC A5

/* ADC configuration */
static const float ADC_MAX = 4095.0f;   // 12-bit ADC
static const float VREF    = 3.287f;  /* Measured reference voltage (3.3V rail)
                                         This value should be measured on the board with a multimeter */

/* Voltage divider resistors (measured values) 
The resistor values in the board should be measured with a multimeter and updated here for better precision */
// Battery measurement (12V)
static const float R1_VBAT = 472100.0f; // High-side resistor (470k Ohms)
static const float R2_VBAT = 148710.0f; // Low-side resistor (150k Ohms)

// Solar panel measurement (20V)
static const float R1_PANEL = 684300.0f; // High-side resistor (680k Ohms)
static const float R2_PANEL = 101530.0f; // Low-side resistor (100k Ohms)

/**
 * @brief Initialize ADC subsystem
 */
void adc_init() {
    analogReadResolution(12);   // ADC resolution 12 bits (0 to 4095)
}

/**
 * @brief Read battery and solar panel voltages
 */
bool adc_read(adc_readings_t *readings) {
    if (readings == nullptr) {
        Serial.println("ERROR: Invalid pointer in adc_read()");
        return false;
    }

    /* Raw ADC readings */
    readings->rawBattery = analogRead(PIN_VBAT);
    readings->rawPanel   = analogRead(PIN_PANEL);

    /* Voltage at ADC pins */
    readings->adcVoltageBattery =
        (readings->rawBattery / ADC_MAX) * VREF;

    readings->adcVoltagePanel =
        (readings->rawPanel / ADC_MAX) * VREF;

    /* Voltage divider ratios */
    const float dividerBattery = (R1_VBAT + R2_VBAT) / R2_VBAT;
    const float dividerPanel  = (R1_PANEL + R2_PANEL) / R2_PANEL;

    /* Calculated real voltages */
    readings->batteryVoltage =
        readings->adcVoltageBattery * dividerBattery;

    readings->panelVoltage =
        readings->adcVoltagePanel * dividerPanel;

    return true;
}

/**
 * @brief Print ADC readings to serial output
 */
void adc_printReadings(const adc_readings_t *readings) {
    if (readings == nullptr) {
        Serial.println("ERROR: Invalid pointer in adc_printReadings()");
        return;
    }

    // Serial.print("ADC Raw Value (Battery): ");
    // Serial.println(readings->rawBattery);

    // Serial.print("Voltage at Battery ADC Pin: ");
    // Serial.print(readings->adcVoltageBattery, 3);
    // Serial.println(" V");

    Serial.print("Battery Voltage (calculated): ");
    Serial.print(readings->batteryVoltage, 2);
    Serial.println(" V");

    // Serial.print("ADC Raw Value (Solar Panel): ");
    // Serial.println(readings->rawPanel);

    // Serial.print("Voltage at Panel ADC Pin: ");
    // Serial.print(readings->adcVoltagePanel, 3);
    // Serial.println(" V");

    Serial.print("Solar Panel Voltage (calculated): ");
    Serial.print(readings->panelVoltage, 2);
    Serial.println(" V");

    Serial.println("---------------------------------------------");
}
