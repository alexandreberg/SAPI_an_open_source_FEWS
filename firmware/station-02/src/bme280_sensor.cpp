/**
 * @file bme280_sensor.cpp
 * @brief Implementation of BME280 sensor interface
 * 
 * This file contains the implementation of functions to interface
 * with the BME280 temperature and pressure sensor via I2C.
 * 
 * @note Tested with BMP280 sensor (compatible with BME280 library)
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

#include "bme280_sensor.h"
#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BMP280.h>

// Global BMP280 sensor object
static Adafruit_BMP280 bmp;

/**
 * @brief Initialize the BME280 sensor
 * 
 * Initializes I2C communication and attempts to establish
 * connection with the BME280 sensor at the defined address.
 * 
 * @return true if sensor found and initialized successfully
 * @return false if sensor not found or initialization failed
 */
bool bme280_init() {
  // Initialize I2C communication on default serial port
  // Wire.begin();
  Wire.begin(BME280_SDA, BME280_SCL);

  // Attempt to initialize communication with BMP280 sensor
  if (!bmp.begin(BMP_ADDRESS)) {
    Serial.println("ERROR: Could not find a valid BMP280 sensor, check connections!");
    return false;
  }

  // If sensor found, print confirmation
  Serial.println("BMP280 sensor found and initialized!");
  return true;
}

/**
 * @brief Read temperature and pressure from BME280 sensor
 * 
 * Reads current sensor values and stores them in the provided pointers.
 * 
 * @param temperature Pointer to float variable to store temperature (°C)
 * @param pressure Pointer to float variable to store pressure (hPa)
 * @return true if reading successful
 * @return false if pointers are null or reading failed
 */
bool bme280_read(float *temperature, float *pressure) {
  // Validate pointers
  if (temperature == nullptr || pressure == nullptr) {
    Serial.println("ERROR: Invalid pointer in bme280_read()");
    return false;
  }

  // Read measurements from sensor
  *temperature = bmp.readTemperature();      // Temperature in Celsius
  *pressure = bmp.readPressure() / 100.0F;   // Pressure in hPa

  return true;
}

/**
 * @brief Print BME280 readings to serial console
 * 
 * Convenience function that reads sensor data and prints
 * formatted output to the serial monitor.
 */
void bme280_printReadings() {
  float temperature = 0.0;
  float pressure = 0.0;

  // Read sensor data
  if (bme280_read(&temperature, &pressure)) {
    // Print results to serial monitor
    Serial.print("Temperature = ");
    Serial.print(temperature);
    Serial.println(" °C");

    Serial.print("Pressure = ");
    Serial.print(pressure);
    Serial.println(" hPa");
    
    Serial.println("--------------------");
  } else {
    Serial.println("ERROR: Failed to read BME280 sensor");
  }
}

//TODO: need to store readings in the data struct