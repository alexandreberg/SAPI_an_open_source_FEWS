/**
 * @file raingauge.cpp
 * @brief Implementation of rain gauge pulse counter functions
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


 // TODO: Need to improve debouncing logic, sometimes it counts more pulses than the real value.

#include "raingauge.h"

/* GPIO pin definitions */
static const uint8_t PIN_COUNTER_RESET = PA8;   // CD4040 reset (active HIGH)
static const uint8_t PIN_CLOCK         = PB10;  // 74HC166 clock (CLK)
static const uint8_t PIN_SHIFT_LOAD    = PB4;   // 74HC166 SH/!LD
static const uint8_t PIN_SERIAL_OUT    = PB5;   // 74HC166 QH (serial output)

/* Timing configuration */
static const uint16_t PULSE_DELAY_US = 100;

/* Rain gauge calibration */
static const float MM_PER_PULSE = 0.25f;

/**
 * @brief Initialize rain gauge hardware
 */
void raingauge_init() {
    pinMode(PIN_COUNTER_RESET, OUTPUT);
    pinMode(PIN_CLOCK, OUTPUT);
    pinMode(PIN_SHIFT_LOAD, OUTPUT);
    pinMode(PIN_SERIAL_OUT, INPUT);

    /* Initial states */
    digitalWrite(PIN_COUNTER_RESET, LOW);
    digitalWrite(PIN_CLOCK, HIGH);
    digitalWrite(PIN_SHIFT_LOAD, HIGH);

    Serial.println("Rain gauge interface initialized");
}

/**
 * @brief Read pulse counter value
 *
 * Implements the same logic validated in Proteus simulation.
 */
bool raingauge_read(uint8_t *pulseCount) {
    if (pulseCount == nullptr) {
        Serial.println("ERROR: Invalid pointer in raingauge_read()");
        return false;
    }

    uint8_t count = 0;

    /* Initial state: CLK = HIGH, SH/!LD = HIGH */
    digitalWrite(PIN_CLOCK, HIGH);
    digitalWrite(PIN_SHIFT_LOAD, HIGH);
    delayMicroseconds(PULSE_DELAY_US);

    /* Load parallel data */
    digitalWrite(PIN_SHIFT_LOAD, LOW);
    delayMicroseconds(PULSE_DELAY_US);

    digitalWrite(PIN_CLOCK, LOW);
    delayMicroseconds(PULSE_DELAY_US);
    digitalWrite(PIN_CLOCK, HIGH);
    delayMicroseconds(PULSE_DELAY_US);

    /* Shift mode */
    digitalWrite(PIN_SHIFT_LOAD, HIGH);
    delayMicroseconds(PULSE_DELAY_US);

    /* Read 8 bits (MSB first) */
    for (int i = 0; i < 8; i++) {
        digitalWrite(PIN_CLOCK, LOW);
        delayMicroseconds(PULSE_DELAY_US);
        digitalWrite(PIN_CLOCK, HIGH);
        delayMicroseconds(PULSE_DELAY_US);

        bool bitValue = digitalRead(PIN_SERIAL_OUT);
        if (bitValue) {
            count |= (1 << (7 - i));
        }
    }

    /*
     * CD4040 does not provide Q0.
     * Q1..Q8 are mapped to A..H of 74HC166.
     * Correction: shift right by one bit.
     */
    count >>= 1;

    *pulseCount = count;
    return true;
}

/**
 * @brief Reset CD4040 pulse counter
 */
void raingauge_resetCounter() {
    digitalWrite(PIN_COUNTER_RESET, HIGH);
    delayMicroseconds(PULSE_DELAY_US * 5);
    digitalWrite(PIN_COUNTER_RESET, LOW);
}

/**
 * @brief Read rain gauge pulses and calculate precipitation
 */
bool raingauge_getReadings(raingauge_readings_t *readings) {
    if (readings == nullptr) {
        Serial.println("ERROR: Invalid pointer in raingauge_getReadings()");
        return false;
    }

    uint8_t pulses = 0;
    if (!raingauge_read(&pulses)) {
        return false;
    }

    readings->pulseCount = pulses;
    readings->precipitationMM = pulses * MM_PER_PULSE;
    readings->timestampSec = millis() / 1000;

    return true;
}

/**
 * @brief Print rain gauge readings to serial console
 */
void raingauge_printReadings(const raingauge_readings_t *readings) {
    if (readings == nullptr) {
        Serial.println("ERROR: Invalid pointer in raingauge_printReadings()");
        return;
    }

    Serial.print("[");
    Serial.print(readings->timestampSec);
    Serial.print(" s] Pulses: ");
    Serial.print(readings->pulseCount);

    Serial.print(" | Precipitation: ");
    Serial.print(readings->precipitationMM, 2);
    Serial.println(" mm");
}
