/**
 * @file tph_sensor.h
 * @brief TPH sensor interface for Temperature, Pressure, Humidity measurements
 *
 * This module provides a unified interface for multiple TPH sensor types,
 * following the same architectural pattern as ultrasonic.cpp.
 *
 * Supported sensors:
 *  - BMP280:  I2C, Temperature + Pressure
 *  - BME280:  I2C, Temperature + Pressure + Humidity
 *  - SHT20:   I2C, Temperature + Humidity (IP65 rated)
 *
 * Hardware Connection (Nucleo L476RG - Morpho CN10):
 *   Nucleo         Sensor
 *   3V3          - VCC
 *   GND          - GND
 *   PB8 (CN10.3) - SCL
 *   PB9 (CN10.5) - SDA
 *
 * @note On STM32duino, I2C pins MUST be set using Wire.setSDA()/Wire.setSCL()
 *       before Wire.begin(). Using Wire.begin(sda, scl) does not reliably
 *       remap pins on all STM32 variants.
 *
 * Required libraries:
 *   - For BMP280/BME280: Adafruit BMP280 Library @ ^2.6.8
 *   - For SHT20: DFRobot_SHT20 @ ^1.0.0
 *
 * @author Alexandre Nuernberg
 * @date February 2026
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

#ifndef TPH_SENSOR_H
#define TPH_SENSOR_H

#include <Arduino.h>

/*******************************************************************************
 * Sensor Type Definitions
 ******************************************************************************/

/**
 * @brief Sensor type preprocessor constants for compile-time selection
 *
 * These MUST be #define macros (not just enum) so the preprocessor
 * can evaluate #if conditions for conditional compilation.
 */
#define TPH_SENSOR_BMP280  1  /**< BMP280: I2C, Temp + Pressure */
#define TPH_SENSOR_BME280  2  /**< BME280: I2C, Temp + Pressure + Humidity */
#define TPH_SENSOR_SHT20   3  /**< SHT20:  I2C, Temp + Humidity (IP65) */

/**
 * @brief TPH sensor type enumeration (for runtime use)
 */
typedef enum {
    TPH_TYPE_BMP280 = TPH_SENSOR_BMP280,
    TPH_TYPE_BME280 = TPH_SENSOR_BME280,
    TPH_TYPE_SHT20  = TPH_SENSOR_SHT20
} tph_sensor_type_t;

/**
 * @brief TPH sensor capabilities flags
 */
typedef enum {
    TPH_CAP_TEMPERATURE = 0x01,  /**< Sensor measures temperature */
    TPH_CAP_PRESSURE    = 0x02,  /**< Sensor measures pressure */
    TPH_CAP_HUMIDITY    = 0x04   /**< Sensor measures humidity */
} tph_sensor_capability_t;

/*******************************************************************************
 * Configuration Structures
 ******************************************************************************/

/**
 * @brief TPH sensor configuration structure
 *
 * Contains sensor-specific parameters for different TPH sensor models.
 */
typedef struct {
    const char *name;               /**< Sensor model name */
    tph_sensor_type_t type;         /**< Sensor type identifier */
    uint8_t capabilities;           /**< Bitmask of tph_sensor_capability_t */
    uint8_t i2cAddress;             /**< Default I2C address */
    uint8_t i2cAddressAlt;          /**< Alternate I2C address (0 if none) */
    uint16_t initDelayMs;           /**< Initialization delay (milliseconds) */
    uint16_t measurementDelayMs;    /**< Time between measurements (ms) */
} tph_sensor_config_t;

/**
 * @brief Structure to store TPH sensor readings
 */
typedef struct {
    float temperature;      /**< Temperature in Celsius (NAN if not available) */
    float pressure;         /**< Pressure in hPa (NAN if not available) */
    float humidity;         /**< Relative humidity % (NAN if not available) */
    bool readingValid;      /**< True if reading is valid */
    uint8_t errorCode;      /**< Error code (0 = no error) */
} tph_sensor_readings_t;

/*******************************************************************************
 * Error Codes
 ******************************************************************************/

#define TPH_ERROR_NONE          0   /**< No error */
#define TPH_ERROR_NOT_FOUND     1   /**< Sensor not found on I2C bus */
#define TPH_ERROR_INIT_FAILED   2   /**< Initialization failed */
#define TPH_ERROR_READ_FAILED   3   /**< Read operation failed */
#define TPH_ERROR_CRC_FAILED    4   /**< CRC check failed (SHT20) */
#define TPH_ERROR_TIMEOUT       5   /**< Communication timeout */

/*******************************************************************************
 * I2C Pin Definitions (Nucleo L476RG)
 ******************************************************************************/

#ifndef TPH_SENSOR_SDA
#define TPH_SENSOR_SDA PB9
#endif

#ifndef TPH_SENSOR_SCL
#define TPH_SENSOR_SCL PB8
#endif

/*******************************************************************************
 * Public API Functions
 ******************************************************************************/

/**
 * @brief Get current sensor configuration
 *
 * @return Pointer to current sensor configuration structure, or nullptr if
 *         sensor not initialized
 */
const tph_sensor_config_t* tph_sensor_getConfig(void);

/**
 * @brief Initialize TPH sensor
 *
 * Configures I2C and initializes communication with the selected sensor.
 * Uses the sensor type defined by TPH_SENSOR_TYPE macro.
 *
 * @return true if initialization successful, false otherwise
 */
bool tph_sensor_init(void);

/**
 * @brief Read all measurements from TPH sensor
 *
 * Reads temperature, pressure, and/or humidity based on sensor capabilities.
 * Unavailable measurements are set to NAN.
 *
 * @param readings Pointer to tph_sensor_readings_t structure to store results
 * @return true if reading was successful, false otherwise
 */
bool tph_sensor_read(tph_sensor_readings_t *readings);

/**
 * @brief Print TPH sensor readings to serial console
 *
 * @param readings Pointer to tph_sensor_readings_t structure
 */
void tph_sensor_printReadings(const tph_sensor_readings_t *readings);

/**
 * @brief Check if sensor has specific capability
 *
 * @param capability Capability to check (TPH_CAP_TEMPERATURE, TPH_CAP_PRESSURE,
 *                   or TPH_CAP_HUMIDITY)
 * @return true if sensor has capability, false otherwise
 */
bool tph_sensor_hasCapability(tph_sensor_capability_t capability);

#endif // TPH_SENSOR_H
