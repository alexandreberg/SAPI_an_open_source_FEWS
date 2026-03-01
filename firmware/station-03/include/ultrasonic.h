/**
 * @file ultrasonic.h
 * @brief Ultrasonic distance sensor interface for water level measurements
 *
 * This module provides functions to initialize and read distance measurements
 * from multiple ultrasonic sensor types. Uses median filtering of multiple
 * readings to eliminate outliers and improve measurement reliability.
 *
 * Supported sensors:
 *  - HC-SR04:   Echo mode (trigger/echo pulse timing)
 *  - US-100:    Serial mode (UART communication)
 *  - AJ-SR04M:  Serial mode 2 (with 120K resistor on R19)
 *
 * Hardware (STM32 Nucleo L476RG):
 *  - Echo mode:   Trigger pin PC11, Echo pin PC10
 *  - Serial mode: TX pin PC10, RX pin PC11 (directly connected to sensor)
 *
 * @note Sensor range: 2cm to 500cm (varies by sensor model)
 * @note Uses 11 consecutive readings to calculate median value
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

#ifndef ULTRASONIC_H
#define ULTRASONIC_H

#include <Arduino.h>

/**
 * @brief Failure code for sensor hardware failure
 *
 * This value is returned when the ultrasonic sensor fails the startup test
 * or is completely unresponsive. The value -888 is chosen to be clearly
 * distinguishable from valid readings (2-450 cm) and other error codes (-1, -99).
 *
 * @note MySQL table uses smallint(5) UNSIGNED, so this value needs to be
 *       handled appropriately before database insertion (e.g., store as NULL
 *       or convert to a positive sentinel value, or change column to signed).
 */
#define US_SENSOR_FAILURE_CODE -888

/**
 * @brief Ultrasonic sensor type enumeration
 */
typedef enum {
    US_SENSOR_HC_SR04  = 1,  /**< HC-SR04: Echo mode (trigger/echo pulses) */
    US_SENSOR_US100    = 2,  /**< US-100: Serial mode (UART) */
    US_SENSOR_AJ_SR04M = 3   /**< AJ-SR04M: Serial mode 2 (120K on R19) */
} ultrasonic_sensor_type_t;

/**
 * @brief Ultrasonic sensor operation mode
 */
typedef enum {
    US_MODE_ECHO   = 0,  /**< Trigger/Echo pulse timing mode */
    US_MODE_SERIAL = 1   /**< UART serial communication mode */
} ultrasonic_mode_t;

/**
 * @brief Ultrasonic sensor configuration structure
 *
 * Contains sensor-specific parameters for different ultrasonic models.
 */
typedef struct {
    const char *name;           /**< Sensor model name */
    ultrasonic_sensor_type_t type;  /**< Sensor type identifier */
    ultrasonic_mode_t mode;     /**< Operation mode (Echo or Serial) */
    uint16_t minDistance;       /**< Minimum valid distance (cm) */
    uint16_t maxDistance;       /**< Maximum valid distance (cm) */
    uint16_t triggerPulseUs;    /**< Trigger pulse duration (microseconds) */
    uint32_t serialBaudRate;    /**< Serial baud rate (for serial mode) */
    uint8_t serialCommand;      /**< Command byte to request reading */
    uint8_t responseBytes;      /**< Expected response size in bytes */
    uint16_t timeoutMs;         /**< Reading timeout (milliseconds) */
} ultrasonic_config_t;

/**
 * @brief Structure to store ultrasonic sensor readings
 *
 * For the US-100 in serial mode, two extra fields are populated after each call
 * to ultrasonic_read():
 *  - correctedDistance: raw median with the combined regression correction applied
 *    (Test-01 + Test-02 best-fit: Corrected = 0.933 * Raw - 1.87 cm)
 *  - internalTemperature: US-100 built-in thermistor value read via 0x50 command,
 *    useful for cross-checking against an external probe (e.g. SHT20).
 *    Set to NAN for non-US-100 sensor types.
 */
typedef struct {
    int32_t distance;              /**< Raw median distance in cm (uncorrected) */
    int32_t correctedDistance;     /**< Regression-corrected distance in cm (= 0.933 * raw - 1.87) */
    float   internalTemperature;   /**< US-100 internal temperature in C (NAN if unavailable) */
    bool    readingValid;          /**< True if distance reading is within valid range */
    uint8_t validReadingsCount;    /**< Number of valid readings obtained out of NUM_READINGS */
} ultrasonic_readings_t;

/**
 * @brief Get current sensor configuration
 *
 * @return Pointer to current sensor configuration structure
 */
const ultrasonic_config_t* ultrasonic_getConfig(void);

/**
 * @brief Initialize ultrasonic sensor
 *
 * Configures GPIO pins or serial port based on sensor type.
 * Uses the sensor type defined by US_SENSOR_TYPE macro.
 */
void ultrasonic_init(void);

/**
 * @brief Read distance from ultrasonic sensor
 *
 * Takes multiple consecutive readings, filters invalid values,
 * and calculates the median to eliminate outliers.
 * Works with both Echo and Serial mode sensors.
 *
 * @param readings Pointer to ultrasonic_readings_t structure to store results
 * @return true if reading was successful, false otherwise
 */
bool ultrasonic_read(ultrasonic_readings_t *readings);

/**
 * @brief Print ultrasonic readings to serial console
 *
 * @param readings Pointer to ultrasonic_readings_t structure
 */
void ultrasonic_printReadings(const ultrasonic_readings_t *readings);

#endif // ULTRASONIC_H
