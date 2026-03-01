/**
 * @file raingauge.h
 * @brief Rain gauge pulse counter interface
 *
 * This module implements the interface to a rain gauge system based on:
 *  - CD4040 binary counter
 *  - 74HC166 parallel-in serial-out shift register
 *
 * The system counts rain gauge pulses and converts them into precipitation (mm).
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

#ifndef RAINGAUGE_H
#define RAINGAUGE_H

#include <Arduino.h>

/**
 * @brief Structure to store rain gauge readings
 */
typedef struct {
    uint8_t pulseCount;      /**< Number of pulses counted */
    float precipitationMM;   /**< Calculated precipitation in millimeters */
    uint32_t timestampSec;   /**< Timestamp of the reading (seconds since boot) */
} raingauge_readings_t;

/**
 * @brief Initialize rain gauge GPIOs and internal state
 */
void raingauge_init();

/**
 * @brief Read pulse counter from CD4040 via 74HC166
 *
 * @param pulseCount Pointer to store the corrected pulse count
 * @return true if reading was successful, false otherwise
 */
bool raingauge_read(uint8_t *pulseCount);

/**
 * @brief Reset the CD4040 pulse counter
 */
void raingauge_resetCounter();

/**
 * @brief Read rain gauge and calculate precipitation
 *
 * @param readings Pointer to raingauge_readings_t structure
 * @return true if reading was successful, false otherwise
 */
bool raingauge_getReadings(raingauge_readings_t *readings);

/**
 * @brief Print rain gauge readings to serial console
 *
 * @param readings Pointer to raingauge_readings_t structure
 */
void raingauge_printReadings(const raingauge_readings_t *readings);

#endif // RAINGAUGE_H
