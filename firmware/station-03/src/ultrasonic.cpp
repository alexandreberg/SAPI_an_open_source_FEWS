/**
 * @file ultrasonic.cpp
 * @brief Implementation of ultrasonic distance sensor functions
 *
 * Supports multiple ultrasonic sensor types:
 *  - HC-SR04:   Echo mode (trigger pulse, measure echo duration)
 *  - US-100:    Serial mode (sends 0x55, receives 2 bytes distance in mm)
 *  - AJ-SR04M:  Serial mode 2 (120K resistor, sends 0x01, receives 4 bytes)
 *
 * Uses median filtering to eliminate erroneous measurements caused by
 * acoustic reflections on water surfaces.
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

#include "ultrasonic.h"
#include <HardwareSerial.h>

/* Include watchdog for reload in retry loops */
#ifdef enableWatchDog
#include <IWatchdog.h>
#endif

/*******************************************************************************
 * Configuration - Select sensor type here
 ******************************************************************************/

/**
 * @brief Select the ultrasonic sensor type to use
 *
 * Options:
 *   US_SENSOR_HC_SR04  (1) - HC-SR04 in Echo mode
 *   US_SENSOR_US100    (2) - US-100 in Serial mode
 *   US_SENSOR_AJ_SR04M (3) - AJ-SR04M in Serial mode 2
 */
#ifndef US_SENSOR_TYPE
// #define US_SENSOR_TYPE US_SENSOR_HC_SR04
#define US_SENSOR_TYPE US_SENSOR_US100
#endif

/** @brief Enable serial debug output */
#define enableSerialLog

/** @brief add more serial log verbosity */
//#define enableVerbosity

/* US_SENSOR_FAILURE_CODE is defined in ultrasonic.h */

/*******************************************************************************
 * Pin Definitions
 ******************************************************************************/

/* Echo mode pins (HC-SR04) */
#define PIN_TRIGGER PC11  /**< Trigger output pin */
#define PIN_ECHO    PC10  /**< Echo input pin */

/* Serial mode pins (US-100, AJ-SR04M) */
#define PIN_US_TX   PC11  /**< UART TX to sensor RX */
#define PIN_US_RX   PC10  /**< UART RX from sensor TX */

/*******************************************************************************
 * Sensor Configuration Definitions
 ******************************************************************************/

/** @brief Number of readings for median calculation (odd number recommended) */
#define NUM_READINGS 11

/** @brief Maximum retry attempts for a single reading */
#define MAX_RETRIES 20

/** @brief Speed of sound divisor for distance calculation (microseconds to cm) */
#define SOUND_DIVISOR 58

/**
 * @brief Predefined sensor configurations
 */
static const ultrasonic_config_t sensorConfigs[] = {
    /* HC-SR04: Echo mode (also used by US-100 with jumper removed) */
    {
        .name           = "HC-SR04",
        .type           = US_SENSOR_HC_SR04,
        .mode           = US_MODE_ECHO,
        .minDistance    = 2,
        .maxDistance    = 450,
        .triggerPulseUs = 50,
        .serialBaudRate = 0,        /* Not used in echo mode */
        .serialCommand  = 0x00,     /* Not used in echo mode */
        .responseBytes  = 0,        /* Not used in echo mode */
        .timeoutMs      = 38        /* ~26ms round-trip at 450cm + margin */
    },
    /* US-100: Serial mode */
    {
        .name           = "US-100",
        .type           = US_SENSOR_US100,
        .mode           = US_MODE_SERIAL,
        .minDistance    = 2,
        .maxDistance    = 350,
        .triggerPulseUs = 0,        /* Not used in serial mode */
        .serialBaudRate = 9600,
        .serialCommand  = 0x55,     /* Command to request distance */
        .responseBytes  = 2,        /* 2 bytes: MSB + LSB (distance in mm) */
        .timeoutMs      = 100
    },
    /* AJ-SR04M: Serial mode 2 (with 120K resistor on R19) */
    {
        .name           = "AJ-SR04M",
        .type           = US_SENSOR_AJ_SR04M,
        .mode           = US_MODE_SERIAL,
        .minDistance    = 20,
        .maxDistance    = 800,
        .triggerPulseUs = 0,        /* Not used in serial mode */
        .serialBaudRate = 9600,
        .serialCommand  = 0x01,     /* Command to request distance */
        .responseBytes  = 4,        /* 4 bytes: 0xFF + MSB + LSB + checksum */
        .timeoutMs      = 150
    }
};

/** @brief Current sensor configuration pointer */
static const ultrasonic_config_t *currentConfig = nullptr;

/** @brief Serial port for sensor communication (serial mode only) */
static HardwareSerial *sensorSerial = nullptr;

/**
 * @brief Flag indicating if startup test failed
 *
 * When true, ultrasonic_read() will immediately return the failure code
 * without attempting sensor communication, preventing watchdog timeout loops.
 */
static bool startupTestFailed = false;

/*******************************************************************************
 * Private Helper Functions
 ******************************************************************************/

/**
 * @brief Compare function for qsort
 */
static int compareReadings(const void *a, const void *b) {
    return (*(int *)a - *(int *)b);
}

/**
 * @brief Calculate median of an integer array
 */
static float calculateMedian(int *array, int arraySize) {
    qsort(array, arraySize, sizeof(int), compareReadings);

#ifdef enableVerbosity
    Serial.println("Sorted distance readings:");
    for (int i = 0; i < arraySize; i++) {
        Serial.println(array[i]);
    }
    Serial.println();
#endif

    if (arraySize % 2 == 0) {
        return (float)(array[arraySize / 2 - 1] + array[arraySize / 2]) / 2.0f;
    } else {
        return (float)array[arraySize / 2];
    }
}

/**
 * @brief Get sensor configuration by type
 */
static const ultrasonic_config_t* getConfigByType(ultrasonic_sensor_type_t type) {
    for (size_t i = 0; i < sizeof(sensorConfigs) / sizeof(sensorConfigs[0]); i++) {
        if (sensorConfigs[i].type == type) {
            return &sensorConfigs[i];
        }
    }
    return nullptr;
}

/**
 * @brief Read single distance using Echo mode (HC-SR04)
 *
 * @return Distance in cm, or -1 if invalid
 */
static int32_t readEchoMode(void) {
    /* Generate trigger pulse */
    digitalWrite(PIN_TRIGGER, LOW);
    delayMicroseconds(5);
    digitalWrite(PIN_TRIGGER, HIGH);
    delayMicroseconds(currentConfig->triggerPulseUs);
    digitalWrite(PIN_TRIGGER, LOW);

    /* Measure echo pulse duration */
    unsigned long pulseLength = pulseIn(PIN_ECHO, HIGH, currentConfig->timeoutMs * 1000);

    if (pulseLength == 0) {
        return -1;  /* Timeout */
    }

    /* Calculate distance in centimeters (round half up, not truncate) */
    int32_t distance = (pulseLength + (SOUND_DIVISOR / 2)) / SOUND_DIVISOR;

    return distance;
}

/**
 * @brief Read single distance using Serial mode (US-100)
 *
 * US-100 protocol:
 *   - Send: 0x55
 *   - Receive: 2 bytes (MSB, LSB) = distance in millimeters
 *
 * @return Distance in cm, or -1 if invalid
 */
static int32_t readSerialUS100(void) {
    if (sensorSerial == nullptr) {
#ifdef enableSerialLog
        Serial.println("[US100] ERROR: sensorSerial is null!");
#endif
        return -1;
    }

    /* Clear any pending data */
    int clearedBytes = 0;
    while (sensorSerial->available()) {
        sensorSerial->read();
        clearedBytes++;
    }
// #ifdef enableSerialLog
//     if (clearedBytes > 0) {
//         Serial.print("[US100] Cleared ");
//         Serial.print(clearedBytes);
//         Serial.println(" pending bytes");
//     }
// #endif

    /* Send command */
    size_t bytesSent = sensorSerial->write(currentConfig->serialCommand);
    sensorSerial->flush();  /* Wait for TX to complete */

// #ifdef enableSerialLog
//     Serial.print("[US100] Sent command 0x");
//     Serial.print(currentConfig->serialCommand, HEX);
//     Serial.print(" (");
//     Serial.print(bytesSent);
//     Serial.println(" bytes written)");
// #endif

    /* Wait for response with timeout */
    unsigned long startTime = millis();
    while (sensorSerial->available() < currentConfig->responseBytes) {
        if (millis() - startTime > currentConfig->timeoutMs) {
// #ifdef enableSerialLog
//             Serial.print("[US100] TIMEOUT after ");
//             Serial.print(currentConfig->timeoutMs);
//             Serial.print("ms. Bytes available: ");
//             Serial.println(sensorSerial->available());
// #endif
            return -1;  /* Timeout */
        }
        delay(1);
    }

// #ifdef enableSerialLog
//     unsigned long responseTime = millis() - startTime;
//     Serial.print("[US100] Response received in ");
//     Serial.print(responseTime);
//     Serial.print("ms. Bytes available: ");
//     Serial.println(sensorSerial->available());
// #endif

    /* Read response: 2 bytes (MSB + LSB) = distance in mm */
    uint8_t msb = sensorSerial->read();
    uint8_t lsb = sensorSerial->read();

// #ifdef enableSerialLog
//     Serial.print("[US100] Raw bytes: MSB=0x");
//     Serial.print(msb, HEX);
//     Serial.print(" (");
//     Serial.print(msb);
//     Serial.print("), LSB=0x");
//     Serial.print(lsb, HEX);
//     Serial.print(" (");
//     Serial.print(lsb);
//     Serial.println(")");
// #endif

    /* Calculate distance in mm, convert to cm (round half up, not truncate) */
    uint16_t distanceMm = (msb << 8) | lsb;
    int32_t distanceCm = (distanceMm + 5) / 10;

#ifdef enableSerialLog
    Serial.print("[US100] Distance: ");
    Serial.print(distanceMm);
    Serial.print(" mm = ");
    Serial.print(distanceCm);
    Serial.println(" cm");
#endif

    return distanceCm;
}

/**
 * @brief Read single distance using Serial mode 2 (AJ-SR04M)
 *
 * AJ-SR04M protocol (Mode 2 with 120K resistor on R19):
 *   - Send: 0x01
 *   - Receive: 4 bytes (0xFF, MSB, LSB, Checksum)
 *   - Checksum = (0xFF + MSB + LSB) & 0xFF
 *
 * @return Distance in cm, or -1 if invalid
 */
static int32_t readSerialAJSR04M(void) {
    if (sensorSerial == nullptr) {
        return -1;
    }

    /* Clear any pending data */
    while (sensorSerial->available()) {
        sensorSerial->read();
    }

    /* Send command */
    sensorSerial->write(currentConfig->serialCommand);

    /* Wait for response with timeout */
    unsigned long startTime = millis();
    while (sensorSerial->available() < currentConfig->responseBytes) {
        if (millis() - startTime > currentConfig->timeoutMs) {
            return -1;  /* Timeout */
        }
        delay(1);
    }

    /* Read response: 4 bytes (0xFF, MSB, LSB, Checksum) */
    uint8_t header = sensorSerial->read();
    uint8_t msb = sensorSerial->read();
    uint8_t lsb = sensorSerial->read();
    uint8_t checksum = sensorSerial->read();

    /* Verify header */
    if (header != 0xFF) {
        return -1;  /* Invalid header */
    }

    /* Verify checksum */
    uint8_t calcChecksum = (header + msb + lsb) & 0xFF;
    if (checksum != calcChecksum) {
        return -1;  /* Checksum error */
    }

    /* Calculate distance in mm, convert to cm (round half up, not truncate) */
    uint16_t distanceMm = (msb << 8) | lsb;
    int32_t distanceCm = (distanceMm + 5) / 10;

    return distanceCm;
}

/**
 * @brief Read internal temperature from US-100 sensor
 *
 * US-100 temperature protocol (jumper installed, serial mode):
 *   - Send:    0x50
 *   - Receive: 1 byte (raw)
 *   - Formula: temperature = raw_byte - 45  (standard datasheet formula)
 *
 * Formula confirmed correct in Issue #24 (Feb 2026) using the reference
 * implementation (500 ms blocking delay). A defective sensor had its
 * thermistor stuck at raw=109, which coincidentally gave 27.25 C with the
 * wrong formula (raw/4.0) during Test-02 — masking the bug.
 * With a working sensor at ~25 C ambient: raw=72-73 → 27-28 C.
 *
 * This value is produced by the sensor's own onboard thermistor and is used
 * internally to compensate the speed-of-sound calculation. It can also be
 * read explicitly for cross-comparison with an external probe (e.g. SHT20).
 *
 * @return Temperature in Celsius, or NAN on timeout / sensor not available
 */
static float readTemperatureUS100(void) {
    if (sensorSerial == nullptr) {
        return NAN;
    }

    /* Clear any pending data before sending a new command */
    while (sensorSerial->available()) {
        sensorSerial->read();
    }

    /* Send temperature request command */
    sensorSerial->write((uint8_t)0x50);
    sensorSerial->flush();

    /* Wait for 1-byte response with 100 ms timeout */
    unsigned long startTime = millis();
    while (sensorSerial->available() < 1) {
        if (millis() - startTime > 100) {
#ifdef enableSerialLog
            Serial.println("[US100-TEMP] TIMEOUT - no temperature response");
#endif
            return NAN;
        }
        delay(1);
    }

    uint8_t rawTemp = sensorSerial->read();

    /* Temperature (C) = raw_byte - 45 (standard datasheet formula, confirmed
     * in Issue #24 with reference implementation and a working sensor). */
    float temperature = (float)((int)rawTemp - 45);

#ifdef enableSerialLog
    Serial.print("[US100-TEMP] Raw byte: ");
    Serial.print(rawTemp);
    Serial.print(" -> ");
    Serial.print(temperature, 1);
    Serial.println(" C");
#endif

    return temperature;
}

/**
 * @brief Read single distance based on current sensor mode
 *
 * @return Distance in cm, or -1 if invalid
 */
static int32_t readSingleDistance(void) {
    if (currentConfig == nullptr) {
        return -1;
    }

    switch (currentConfig->type) {
        case US_SENSOR_HC_SR04:
            return readEchoMode();

        case US_SENSOR_US100:
            return readSerialUS100();

        case US_SENSOR_AJ_SR04M:
            return readSerialAJSR04M();

        default:
            return -1;
    }
}

/*******************************************************************************
 * Public API Functions
 ******************************************************************************/

/**
 * @brief Get current sensor configuration
 */
const ultrasonic_config_t* ultrasonic_getConfig(void) {
    return currentConfig;
}

/**
 * @brief Initialize ultrasonic sensor
 */
void ultrasonic_init(void) {
    /* Get configuration for selected sensor type */
    currentConfig = getConfigByType((ultrasonic_sensor_type_t)US_SENSOR_TYPE);

    if (currentConfig == nullptr) {
        Serial.println("ERROR: Invalid ultrasonic sensor type!");
        return;
    }

    Serial.print("Initializing ultrasonic sensor: ");
    Serial.println(currentConfig->name);

    if (currentConfig->mode == US_MODE_ECHO) {
        /* Echo mode: configure GPIO pins */
        pinMode(PIN_TRIGGER, OUTPUT);
        pinMode(PIN_ECHO, INPUT);
        digitalWrite(PIN_TRIGGER, LOW);

        Serial.println("  Mode: Echo (trigger/pulse)");
        Serial.println("  Trigger pin: PC11, Echo pin: PC10");

        /* Startup delay for sensor to stabilize */
        Serial.println("  Waiting 500ms for sensor to stabilize...");
        delay(500);

        /* Perform startup test read to verify sensor responds */
        Serial.println("  Performing startup test read...");
        int32_t testDistance = readEchoMode();
        if (testDistance >= 0 &&
            testDistance >= currentConfig->minDistance &&
            testDistance <= currentConfig->maxDistance) {
            Serial.print("  Startup test: OK (");
            Serial.print(testDistance);
            Serial.println(" cm)");
            startupTestFailed = false;
        } else {
            Serial.println("  Startup test: FAILED - check wiring!");
            Serial.println("  Verify: Trigger -> PC11, Echo -> PC10");
            Serial.println("          Jumper REMOVED for echo mode on US-100");
            Serial.println("  System will report sensor failure code instead of retrying.");
            startupTestFailed = true;
        }
    }
    else if (currentConfig->mode == US_MODE_SERIAL) {
        /* Serial mode: configure UART */
        /* Using Serial3 on STM32 (PC10=RX, PC11=TX) */
        static HardwareSerial Serial3(PIN_US_RX, PIN_US_TX);
        sensorSerial = &Serial3;
        sensorSerial->begin(currentConfig->serialBaudRate);

        Serial.println("  Mode: Serial (UART)");
        Serial.print("  Baud rate: ");
        Serial.println(currentConfig->serialBaudRate);
        Serial.print("  MCU TX pin: PC11 -> connect to sensor RX");
        Serial.println();
        Serial.print("  MCU RX pin: PC10 -> connect to sensor TX");
        Serial.println();
        Serial.print("  Command: 0x");
        Serial.println(currentConfig->serialCommand, HEX);
        Serial.print("  Timeout: ");
        Serial.print(currentConfig->timeoutMs);
        Serial.println(" ms");
        Serial.print("  Expected response bytes: ");
        Serial.println(currentConfig->responseBytes);
    }

    Serial.print("  Range: ");
    Serial.print(currentConfig->minDistance);
    Serial.print(" - ");
    Serial.print(currentConfig->maxDistance);
    Serial.println(" cm");

    /* Startup delay for sensor to stabilize */
    if (currentConfig->mode == US_MODE_SERIAL) {
        Serial.println("  Waiting 500ms for sensor to stabilize...");
        delay(500);

        /* Perform a test read to verify communication */
        Serial.println("  Performing startup test read...");
        int32_t testDistance = readSingleDistance();
        if (testDistance >= 0 &&
            testDistance >= currentConfig->minDistance &&
            testDistance <= currentConfig->maxDistance) {
            Serial.print("  Startup test: OK (");
            Serial.print(testDistance);
            Serial.println(" cm)");
            startupTestFailed = false;
        } else {
            Serial.println("  Startup test: FAILED - check wiring!");
            Serial.println("  Verify: Sensor TX -> MCU RX (PC10)");
            Serial.println("          Sensor RX -> MCU TX (PC11)");
            Serial.println("          Jumper INSTALLED for serial mode on US-100");
            Serial.println("  System will report sensor failure code instead of retrying.");
            startupTestFailed = true;
        }
    }

    Serial.println("Ultrasonic sensor initialized.");
}

/**
 * @brief Read distance from ultrasonic sensor
 *
 * @note If startup test failed (Option D), returns immediately with
 *       US_SENSOR_FAILURE_CODE to prevent watchdog timeout loops.
 * @note Reloads watchdog during retry loops (Option A) to prevent
 *       timeout when sensor is slow to respond.
 */
bool ultrasonic_read(ultrasonic_readings_t *readings) {
    if (readings == nullptr) {
        Serial.println("ERROR: Invalid pointer in ultrasonic_read()");
        return false;
    }

    if (currentConfig == nullptr) {
        Serial.println("ERROR: Ultrasonic sensor not initialized!");
        readings->distance = -1;
        readings->correctedDistance = -1;
        readings->internalTemperature = NAN;
        readings->readingValid = false;
        readings->validReadingsCount = 0;
        return false;
    }

    /* Option D: Early bailout if startup test failed */
    if (startupTestFailed) {
        Serial.println("WARNING: Ultrasonic sensor startup test failed - returning failure code");
        readings->distance = US_SENSOR_FAILURE_CODE;
        readings->correctedDistance = US_SENSOR_FAILURE_CODE;
        readings->internalTemperature = NAN;
        readings->readingValid = false;
        readings->validReadingsCount = 0;
        return false;
    }

    int rawReadings[NUM_READINGS];
    int validCount = 0;

    /* Take NUM_READINGS consecutive readings */
    for (int i = 0; i < NUM_READINGS; i++) {
        int retries = 0;
        int32_t distance = -1;

        /* Retry until valid reading or max retries reached */
        do {
            distance = readSingleDistance();
            delay(50);
            retries++;

            /* Option A: Reload watchdog during retry loop to prevent timeout */
#ifdef enableWatchDog
            IWatchdog.reload();
#endif
        } while ((distance < currentConfig->minDistance ||
                  distance > currentConfig->maxDistance ||
                  distance < 0) && retries < MAX_RETRIES);

        /* Store valid reading */
        if (distance >= currentConfig->minDistance &&
            distance <= currentConfig->maxDistance) {
            rawReadings[validCount] = distance;
            validCount++;

#ifdef enableSerialLog
            Serial.print("Reading ");
            Serial.print(i);
            Serial.print(": ");
            Serial.print(distance);
            Serial.println(" cm");
#endif
        }
    }

    readings->validReadingsCount = validCount;

    /* Check if we have enough valid readings */
    if (validCount < 3) {
        Serial.println("WARNING: Not enough valid ultrasonic readings");
        readings->distance = -1;
        readings->correctedDistance = -1;
        readings->internalTemperature = NAN;
        readings->readingValid = false;
        return false;
    }

    /* Calculate median of valid readings */
    readings->distance = (int32_t)calculateMedian(rawReadings, validCount);

    /*
     * Apply linear regression correction derived from Test-03
     * (US-100_Serial_Mode_Test_Report-03.md, Section 5.5 and 8.4):
     *
     *   Error (cm) = 0.0807 * Distance - 1.5135
     *   Corrected  = 0.925 * Distance + 1.41
     *
     * Reference: Bosch GLM 20 (corrected), 37 valid points, R²=0.99.
     * MAE = 0.73 cm, RMSE = 0.91 cm.
     * The sensor consistently overestimates across the full 20-354 cm range.
     */
    readings->correctedDistance = (int32_t)roundf(0.925f * (float)readings->distance + 1.41f);

    /* Read US-100 internal temperature (available only in serial mode via 0x50 command).
     * A brief pause ensures the sensor is ready for a new command after the distance loop. */
    if (currentConfig->type == US_SENSOR_US100) {
        delay(10);
        readings->internalTemperature = readTemperatureUS100();
    } else {
        readings->internalTemperature = NAN;
    }

    readings->readingValid = true;

    return true;
}

/**
 * @brief Print ultrasonic readings to serial console
 *
 * Prints raw median distance, regression-corrected distance, and (for US-100
 * in serial mode) the sensor's internal temperature reading.
 *
 * @param readings Pointer to ultrasonic_readings_t structure
 */
void ultrasonic_printReadings(const ultrasonic_readings_t *readings) {
    if (readings == nullptr) {
        Serial.println("ERROR: Invalid pointer in ultrasonic_printReadings()");
        return;
    }

    Serial.println("---------------------------------------------");
    if (currentConfig != nullptr) {
        Serial.print("[Ultrasonic] Sensor: ");
        Serial.println(currentConfig->name);
    }

    Serial.print("[Ultrasonic] Valid readings  : ");
    Serial.print(readings->validReadingsCount);
    Serial.print("/");
    Serial.println(NUM_READINGS);

    if (readings->readingValid) {
        Serial.print("[Ultrasonic] Raw distance    : ");
        Serial.print(readings->distance);
        Serial.println(" cm");

        Serial.print("[Ultrasonic] Corrected dist  : ");
        Serial.print(readings->correctedDistance);
        Serial.println(" cm  (= 0.925 x raw + 1.41)");

        if (!isnan(readings->internalTemperature)) {
            Serial.print("[Ultrasonic] US-100 int temp : ");
            Serial.print(readings->internalTemperature, 1);
            Serial.println(" C");
        }
    } else {
        Serial.println("[Ultrasonic] Distance: INVALID");
    }

    Serial.println("---------------------------------------------");
}
