/**
 * @file adc.h
 * @brief ADC interface for battery and solar panel voltage measurements
 *
 * This module provides functions to initialize the ADC subsystem
 * and to read battery and solar panel voltages using voltage dividers.
 *
 * Hardware (STM32 Nucleo F103RB):
 *  - Battery voltage (12V): PC1 (ADC A4)
 *  - Solar panel voltage (20V): PC0 (ADC A5)
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

#ifndef ADC_H
#define ADC_H

#include <Arduino.h>

/**
 * @brief Structure to store ADC voltage readings
 */
typedef struct {
    float batteryVoltage;     /**< Calculated battery voltage (V) */
    float panelVoltage;       /**< Calculated solar panel voltage (V) */
    float adcVoltageBattery;  /**< Voltage at ADC pin for battery (V) */
    float adcVoltagePanel;    /**< Voltage at ADC pin for panel (V) */
    uint16_t rawBattery;      /**< Raw ADC value for battery */
    uint16_t rawPanel;        /**< Raw ADC value for panel */
} adc_readings_t;

/**
 * @brief Initialize ADC configuration
 *
 * Sets ADC resolution and prepares the pins.
 */
void adc_init();

/**
 * @brief Read battery and solar panel voltages
 *
 * @param readings Pointer to adc_readings_t structure to store results
 * @return true if reading was successful, false otherwise
 */
bool adc_read(adc_readings_t *readings);

/**
 * @brief Print ADC readings to serial console
 *
 * @param readings Pointer to adc_readings_t structure
 */
void adc_printReadings(const adc_readings_t *readings);

#endif // ADC_H
