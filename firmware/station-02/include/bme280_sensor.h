/**
 * @file bme280_sensor.h
 * @brief Header file for BME280 sensor interface
 * 
 * This file contains the declarations for BME280 sensor functions
 * including initialization and reading temperature and pressure data.
 * 
 * Hardware Connection (Nucleo/STM32 <==> BME280):
 *   Nucleo - BME280
 *   3v3    - Vcc
 *   GND    - GND
 *   PB8    - SCL
 *   PB9    - SDA
 * 
 * Required libraries:
 *   - Adafruit BMP280 Library @ ^2.6.8
 *   - Adafruit Unified Sensor @ ^1.1.15
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

#ifndef BME280_SENSOR_H
#define BME280_SENSOR_H

#include <Arduino.h>

// BME280 I2C address - default is 0x76, may be 0x77 depending on sensor solder jumper
#define BMP_ADDRESS 0x76

//  BME280 I2C Pins
#define BME280_SCL PB8
#define BME280_SDA PB9

/**
 * @brief Initialize the BME280 sensor
 * @return true if initialization successful, false otherwise
 */
bool bme280_init();

/**
 * @brief Read temperature and pressure from BME280 sensor
 * @param temperature Pointer to store temperature value (°C)
 * @param pressure Pointer to store pressure value (hPa)
 * @return true if reading successful, false otherwise
 */
bool bme280_read(float *temperature, float *pressure);

/**
 * @brief Print BME280 readings to serial console
 * Reads and displays current temperature and pressure values
 */
void bme280_printReadings();

#endif // BME280_SENSOR_H