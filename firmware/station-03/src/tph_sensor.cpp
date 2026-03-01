/**
 * @file tph_sensor.cpp
 * @brief Implementation of TPH (Temperature, Pressure, Humidity) sensor functions
 *
 * Supports multiple sensor types with compile-time selection.
 * Uses same architectural pattern as ultrasonic.cpp for consistency.
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

#include "tph_sensor.h"
#include <Wire.h>

/*******************************************************************************
 * Configuration - Select sensor type here
 ******************************************************************************/

/**
 * @brief Select the TPH sensor type to use
 *
 * Options:
 *   TPH_SENSOR_BMP280 (1) - BMP280: Temp + Pressure
 *   TPH_SENSOR_BME280 (2) - BME280: Temp + Pressure + Humidity
 *   TPH_SENSOR_SHT20  (3) - SHT20:  Temp + Humidity (IP65)
 */
#ifndef TPH_SENSOR_TYPE
// #define TPH_SENSOR_TYPE TPH_SENSOR_BMP280
#define TPH_SENSOR_TYPE TPH_SENSOR_SHT20
#endif

/** @brief Enable serial debug output */
#define enableSerialLog

/*******************************************************************************
 * Include sensor-specific libraries based on selection
 ******************************************************************************/

#if (TPH_SENSOR_TYPE == TPH_SENSOR_BMP280) || (TPH_SENSOR_TYPE == TPH_SENSOR_BME280)
#include <Adafruit_Sensor.h>
#include <Adafruit_BMP280.h>
#endif

#if (TPH_SENSOR_TYPE == TPH_SENSOR_SHT20)
#include <DFRobot_SHT20.h>
#endif

/*******************************************************************************
 * Sensor Configuration Definitions
 ******************************************************************************/

/**
 * @brief Predefined sensor configurations
 */
static const tph_sensor_config_t sensorConfigs[] = {
    /* BMP280: Temperature + Pressure */
    {
        .name               = "BMP280",
        .type               = TPH_TYPE_BMP280,
        .capabilities       = TPH_CAP_TEMPERATURE | TPH_CAP_PRESSURE,
        .i2cAddress         = 0x76,
        .i2cAddressAlt      = 0x77,
        .initDelayMs        = 50,
        .measurementDelayMs = 10
    },
    /* BME280: Temperature + Pressure + Humidity */
    {
        .name               = "BME280",
        .type               = TPH_TYPE_BME280,
        .capabilities       = TPH_CAP_TEMPERATURE | TPH_CAP_PRESSURE | TPH_CAP_HUMIDITY,
        .i2cAddress         = 0x76,
        .i2cAddressAlt      = 0x77,
        .initDelayMs        = 50,
        .measurementDelayMs = 10
    },
    /* SHT20: Temperature + Humidity (IP65) */
    {
        .name               = "SHT20",
        .type               = TPH_TYPE_SHT20,
        .capabilities       = TPH_CAP_TEMPERATURE | TPH_CAP_HUMIDITY,
        .i2cAddress         = 0x40,
        .i2cAddressAlt      = 0x00,  /* No alternate address */
        .initDelayMs        = 100,
        .measurementDelayMs = 85     /* Max measurement time for SHT20 */
    }
};

/** @brief Current sensor configuration pointer */
static const tph_sensor_config_t *currentConfig = nullptr;

/** @brief Sensor initialization status */
static bool sensorInitialized = false;

/*******************************************************************************
 * Sensor Objects (only one will be compiled based on #define)
 ******************************************************************************/

#if (TPH_SENSOR_TYPE == TPH_SENSOR_BMP280) || (TPH_SENSOR_TYPE == TPH_SENSOR_BME280)
static Adafruit_BMP280 bmp;
#endif

#if (TPH_SENSOR_TYPE == TPH_SENSOR_SHT20)
static DFRobot_SHT20 sht20;
#endif

/*******************************************************************************
 * Private Helper Functions
 ******************************************************************************/

/**
 * @brief Get sensor configuration by type
 *
 * @param type Sensor type to look up
 * @return Pointer to configuration, or nullptr if not found
 */
static const tph_sensor_config_t* getConfigByType(tph_sensor_type_t type) {
    for (size_t i = 0; i < sizeof(sensorConfigs) / sizeof(sensorConfigs[0]); i++) {
        if (sensorConfigs[i].type == type) {
            return &sensorConfigs[i];
        }
    }
    return nullptr;
}

/*******************************************************************************
 * Sensor-Specific Read Functions
 ******************************************************************************/

#if (TPH_SENSOR_TYPE == TPH_SENSOR_BMP280)
/**
 * @brief Read measurements from BMP280 sensor
 *
 * @param readings Pointer to readings structure
 * @return true if successful
 */
static bool readBMP280(tph_sensor_readings_t *readings) {
    readings->temperature = bmp.readTemperature();
    readings->pressure = bmp.readPressure() / 100.0F;  /* Convert Pa to hPa */
    readings->humidity = NAN;  /* Not available on BMP280 */
    readings->readingValid = true;
    readings->errorCode = TPH_ERROR_NONE;
    return true;
}
#endif

#if (TPH_SENSOR_TYPE == TPH_SENSOR_BME280)
/**
 * @brief Read measurements from BME280 sensor
 *
 * @note Currently uses BMP280 library which doesn't support humidity.
 *       TODO: Migrate to Adafruit_BME280 library for full support.
 *
 * @param readings Pointer to readings structure
 * @return true if successful
 */
static bool readBME280(tph_sensor_readings_t *readings) {
    readings->temperature = bmp.readTemperature();
    readings->pressure = bmp.readPressure() / 100.0F;  /* Convert Pa to hPa */
    /* TODO: BME280 humidity requires Adafruit_BME280 library */
    readings->humidity = NAN;
    readings->readingValid = true;
    readings->errorCode = TPH_ERROR_NONE;
    return true;
}
#endif

#if (TPH_SENSOR_TYPE == TPH_SENSOR_SHT20)
/**
 * @brief Read measurements from SHT20 sensor
 *
 * @param readings Pointer to readings structure
 * @return true if successful
 */
static bool readSHT20(tph_sensor_readings_t *readings) {
    readings->temperature = sht20.readTemperature();
    readings->humidity = sht20.readHumidity();
    readings->pressure = NAN;  /* Not available on SHT20 */

    /* Check for valid readings */
    if (isnan(readings->temperature) || isnan(readings->humidity)) {
        readings->readingValid = false;
        readings->errorCode = TPH_ERROR_READ_FAILED;
        return false;
    }

    readings->readingValid = true;
    readings->errorCode = TPH_ERROR_NONE;
    return true;
}
#endif

/*******************************************************************************
 * Public API Functions
 ******************************************************************************/

/**
 * @brief Get current sensor configuration
 */
const tph_sensor_config_t* tph_sensor_getConfig(void) {
    return currentConfig;
}

/**
 * @brief Initialize TPH sensor
 */
bool tph_sensor_init(void) {
    /* Get configuration for selected sensor type */
    currentConfig = getConfigByType((tph_sensor_type_t)TPH_SENSOR_TYPE);

    if (currentConfig == nullptr) {
        Serial.println("ERROR: Invalid TPH sensor type!");
        return false;
    }

    Serial.print("Initializing TPH sensor: ");
    Serial.println(currentConfig->name);

    /*
     * Initialize I2C with configured pins.
     * On STM32duino, Wire.begin(sda, scl) does not reliably remap I2C pins.
     * Using Wire.setSDA()/Wire.setSCL() before Wire.begin() is the correct
     * approach for custom pin assignment on STM32 variants.
     */
    Wire.setSDA(TPH_SENSOR_SDA);
    Wire.setSCL(TPH_SENSOR_SCL);
    Wire.begin();

    delay(currentConfig->initDelayMs);

#if (TPH_SENSOR_TYPE == TPH_SENSOR_BMP280) || (TPH_SENSOR_TYPE == TPH_SENSOR_BME280)
    /* Try primary I2C address */
    if (!bmp.begin(currentConfig->i2cAddress)) {
        /* Try alternate address if available */
        if (currentConfig->i2cAddressAlt != 0) {
            Serial.print("  Not found at 0x");
            Serial.print(currentConfig->i2cAddress, HEX);
            Serial.print(", trying 0x");
            Serial.println(currentConfig->i2cAddressAlt, HEX);

            if (!bmp.begin(currentConfig->i2cAddressAlt)) {
                Serial.println("ERROR: Sensor not found at any address!");
                Serial.println("  Check wiring: SDA=PB9, SCL=PB8");
                return false;
            }
        } else {
            Serial.println("ERROR: Sensor not found!");
            Serial.println("  Check wiring: SDA=PB9, SCL=PB8");
            return false;
        }
    }
#endif

#if (TPH_SENSOR_TYPE == TPH_SENSOR_SHT20)
    /*
     * Note: We do NOT call sht20.initSHT20() because it calls
     * Wire.begin() without parameters, which would override the
     * custom SDA/SCL pin configuration set above.
     */
    delay(100);

    /* I2C bus scan to verify sensor connectivity */
    Serial.println("  Scanning I2C bus...");
    int nDevices = 0;
    for (byte address = 1; address < 127; address++) {
        Wire.beginTransmission(address);
        byte error = Wire.endTransmission();
        if (error == 0) {
            Serial.print("  I2C device found at 0x");
            if (address < 16) Serial.print("0");
            Serial.println(address, HEX);
            nDevices++;
        }
    }
    if (nDevices == 0) {
        Serial.println("  No I2C devices found! Check wiring.");
        Serial.print("  SDA=PB");
        Serial.print(TPH_SENSOR_SDA == PB9 ? 9 : TPH_SENSOR_SDA);
        Serial.print(", SCL=PB");
        Serial.println(TPH_SENSOR_SCL == PB8 ? 8 : TPH_SENSOR_SCL);
        return false;
    }

    /* Verify sensor by attempting a test read */
    Serial.println("  Performing startup test read...");
    float testTemp = sht20.readTemperature();
    float testHum = sht20.readHumidity();

    /* Check for error codes from library (998=timeout, 999=CRC error) */
    if (testTemp == 998 || testHum == 998) {
        Serial.println("ERROR: SHT20 I2C timeout!");
        Serial.println("  Check wiring: SDA=PB9, SCL=PB8");
        Serial.println("  Verify I2C address is 0x40");
        return false;
    }
    if (testTemp == 999 || testHum == 999) {
        Serial.println("ERROR: SHT20 CRC error!");
        return false;
    }
    if (isnan(testTemp) || isnan(testHum)) {
        Serial.println("ERROR: SHT20 not responding!");
        Serial.println("  Check wiring: SDA=PB9, SCL=PB8");
        Serial.println("  Verify I2C address is 0x40");
        return false;
    }

    Serial.print("  Startup test: OK (T=");
    Serial.print(testTemp);
    Serial.print("C, H=");
    Serial.print(testHum);
    Serial.println("%)");
#endif

    /* Print sensor capabilities */
    Serial.print("  Capabilities: ");
    if (currentConfig->capabilities & TPH_CAP_TEMPERATURE) Serial.print("Temperature ");
    if (currentConfig->capabilities & TPH_CAP_PRESSURE) Serial.print("Pressure ");
    if (currentConfig->capabilities & TPH_CAP_HUMIDITY) Serial.print("Humidity ");
    Serial.println();

    Serial.print("  I2C Address: 0x");
    Serial.println(currentConfig->i2cAddress, HEX);

    sensorInitialized = true;
    Serial.println("TPH sensor initialized.");

    return true;
}

/**
 * @brief Read all measurements from TPH sensor
 */
bool tph_sensor_read(tph_sensor_readings_t *readings) {
    if (readings == nullptr) {
        Serial.println("ERROR: Invalid pointer in tph_sensor_read()");
        return false;
    }

    if (!sensorInitialized || currentConfig == nullptr) {
        Serial.println("ERROR: TPH sensor not initialized!");
        readings->readingValid = false;
        readings->errorCode = TPH_ERROR_INIT_FAILED;
        return false;
    }

    /* Initialize readings with NAN (not available) */
    readings->temperature = NAN;
    readings->pressure = NAN;
    readings->humidity = NAN;
    readings->readingValid = false;
    readings->errorCode = TPH_ERROR_NONE;

    /* Call sensor-specific read function */
#if (TPH_SENSOR_TYPE == TPH_SENSOR_BMP280)
    return readBMP280(readings);
#elif (TPH_SENSOR_TYPE == TPH_SENSOR_BME280)
    return readBME280(readings);
#elif (TPH_SENSOR_TYPE == TPH_SENSOR_SHT20)
    return readSHT20(readings);
#else
    Serial.println("ERROR: No sensor type defined!");
    readings->errorCode = TPH_ERROR_READ_FAILED;
    return false;
#endif
}

/**
 * @brief Print TPH sensor readings to serial console
 */
void tph_sensor_printReadings(const tph_sensor_readings_t *readings) {
    if (readings == nullptr) {
        Serial.println("ERROR: Invalid pointer in tph_sensor_printReadings()");
        return;
    }

    if (currentConfig != nullptr) {
        Serial.print("Sensor: ");
        Serial.println(currentConfig->name);
    }

    if (readings->readingValid) {
        if (!isnan(readings->temperature)) {
            Serial.print("Temperature: ");
            Serial.print(readings->temperature, 1);
            Serial.println(" C");
        }
        if (!isnan(readings->pressure)) {
            Serial.print("Pressure: ");
            Serial.print(readings->pressure, 1);
            Serial.println(" hPa");
        }
        if (!isnan(readings->humidity)) {
            Serial.print("Humidity: ");
            Serial.print(readings->humidity, 1);
            Serial.println(" %");
        }
    } else {
        Serial.print("Reading INVALID (error code: ");
        Serial.print(readings->errorCode);
        Serial.println(")");
    }

    Serial.println("---------------------------------------------");
}

/**
 * @brief Check if sensor has specific capability
 */
bool tph_sensor_hasCapability(tph_sensor_capability_t capability) {
    if (currentConfig == nullptr) {
        return false;
    }
    return (currentConfig->capabilities & capability) != 0;
}
