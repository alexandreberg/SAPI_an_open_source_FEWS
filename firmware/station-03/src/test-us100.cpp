/**
 * @file test-us100.cpp
 * @brief Diagnostic test for US-100 temperature reading protocol
 *
 * This is an independent, minimal implementation of the US-100 temperature
 * reading protocol, based on the standard reference approach documented in:
 *   - https://arduibots.wordpress.com/2014/10/12/us-100-ultrasonic-sensor-in-serial-mode/
 *   - https://protosupplies.com/product/us-100-ultrasonic-range-finder-module/
 *
 * The goal is to diagnose GitHub Issue #24: the US-100 internal temperature
 * reads a constant 27.2 °C (raw = 109) regardless of ambient temperature.
 *
 * This sketch tests whether the constant raw value is caused by:
 *   (a) Incorrect read timing in ultrasonic.cpp (reading too early, < 100 ms),
 *       which is fixed here by using a 500 ms blocking delay before reading.
 *   (b) A formula error (raw/4.0 vs raw-45), which is tested by printing
 *       raw-45 here instead of raw/4.0.
 *   (c) A hardware/thermistor issue (raw value genuinely does not change).
 *
 * Expected outcome if (a) is the root cause:
 *   raw byte will differ from 109 and raw-45 will match ambient temperature.
 *
 * Expected outcome if (c) is the root cause:
 *   raw byte will still be 109 and Temp will display 64 °C (impossible).
 *
 * @note Disable #define enableUltrasonic in main.cpp before using this test.
 * @note Related issue: GitHub Issue #24
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

#include "test-us100.h"
#include <HardwareSerial.h>

/** @brief US-100 serial port: PC10 = RX (from sensor TX), PC11 = TX (to sensor RX) */
static HardwareSerial us100TestSerial(PC10, PC11);

/**
 * @brief Initialize the US-100 test serial port
 */
void us100_test_init(void) {
    us100TestSerial.begin(9600);

    /* Let sensor stabilize after power-on / serial init */
    delay(500);

    Serial.println("[US100-TEST] Initialized: 9600 baud, PC10=RX, PC11=TX");
    Serial.println("[US100-TEST] Formula under test: T(C) = raw - 45");
    Serial.println("[US100-TEST] Delay after 0x50 command: 500 ms");
}

/**
 * @brief Read and print US-100 temperature using the reference approach
 */
void us100_test_read_temperature(void) {

    /* Step 1: Clear any pending bytes in the RX buffer */
    while (us100TestSerial.available()) {
        us100TestSerial.read();
    }

    /* Step 2: Send temperature request command */
    us100TestSerial.write((uint8_t)0x50);

    /* Step 3: Wait 500 ms (blocking) as per all reference implementations.
     * This is the key difference from the ultrasonic.cpp approach which
     * polls with a 100 ms timeout and reads the first arriving byte. */
    delay(500);

    /* Step 4: Read response and print result */
    Serial.println("US Test Readings:");

    if (us100TestSerial.available() >= 1) {
        uint8_t raw = (uint8_t)us100TestSerial.read();
        int temp    = (int)raw - 45;

        Serial.print("RAW = ");
        Serial.print(raw);
        Serial.print(" | Temp = ");
        Serial.print(temp);
        Serial.println(" C");
    } else {
        Serial.println("RAW = --- | Temp = TIMEOUT (no response in 500 ms)");
    }
}
