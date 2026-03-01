/**
 * @file test-us100.h
 * @brief Diagnostic test for US-100 temperature reading protocol
 *
 * Simple, standalone implementation based on the reference approach
 * found in internet examples (arduibots, ProtoSupplies, Adafruit).
 *
 * Protocol used:
 *   1. Clear RX buffer
 *   2. Send 0x50 (temperature command)
 *   3. Wait 500 ms (blocking, as specified by reference implementations)
 *   4. Read 1 byte
 *   5. Apply formula: T(°C) = raw - 45
 *
 * Output format (serial):
 *   US Test Readings:
 *   RAW = XXX | Temp = YYY C
 *
 * @note This module shares UART3 (PC10/PC11) with ultrasonic.cpp.
 *       Disable #define enableUltrasonic in main.cpp when using this test
 *       to avoid UART3 conflicts.
 *
 * @note Related issue: GitHub Issue #24
 *       (US-100 internal temperature formula investigation)
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

#ifndef TEST_US100_H
#define TEST_US100_H

#include <Arduino.h>

/**
 * @brief Initialize the US-100 test serial port.
 *
 * Configures UART3 at 9600 baud on PC10 (RX) and PC11 (TX).
 * Must be called once before us100_test_read_temperature().
 */
void us100_test_init(void);

/**
 * @brief Read and print US-100 temperature using the reference approach.
 *
 * Sends 0x50 command, waits 500 ms (blocking), reads 1 byte response,
 * and prints both the raw byte and the converted temperature using
 * formula T(°C) = raw - 45 (standard datasheet formula).
 *
 * Call this function from the main loop. The 500 ms blocking delay is
 * intentional and matches the timing used in reference implementations.
 */
void us100_test_read_temperature(void);

#endif /* TEST_US100_H */
