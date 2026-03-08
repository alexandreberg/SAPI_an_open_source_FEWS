/**
 * @file sendData.h
 * @brief Data transmission module for LoRa Gateway to Cloud Server
 * 
 * This module handles the serialization and transmission of sensor data
 * from the ESP32 gateway to a remote MySQL server via HTTPS POST requests.
 * Supports both WiFi and Cellular (NB-IoT) connections with automatic fallback.
 * 
 * @author Alexandre Nuernberg
 * @date 2025-12-29
 * @version 1.0.0
 * 
 * Features:
 * - MessagePack binary serialization for minimal bandwidth usage
 * - HMAC-SHA256 authentication for data integrity
 * - Automatic retry mechanism with exponential backoff
 * - Memory-efficient implementation for ESP32
 * - Support for WiFi and Cellular connections
 * 
 * Dependencies:
 * - ArduinoJson 7.4.2+
 * - WiFiClientSecure (ESP32)
 * - HTTPClient (ESP32)
 * 
 * @see https://arduinojson.org/
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

#ifndef SEND_DATA_H
#define SEND_DATA_H

#include <Arduino.h>
#include <ArduinoJson.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <Client.h>  ///< Arduino Client base class — used for the cellular TCP socket

/**
 * @struct SensorData
 * @brief Packed structure containing all sensor measurements
 * 
 * This structure is transmitted via LoRa from remote stations to the gateway.
 * All fields are sized to minimize memory usage while maintaining necessary precision.
 * The structure is packed to ensure consistent memory layout across platforms.
 * 
 * @note Total size: 60 bytes
 */
struct __attribute__((packed)) SensorData {
    uint32_t idStation;              ///< Station identifier (1-4294967295)
    uint32_t reading_number;         ///< Sequential reading counter
    uint32_t timestamp;              ///< Unix timestamp (UTC)
    int32_t level;                   ///< Water level in cm
    float temperature;               ///< Air temperature in Celsius
    float pressure;                  ///< Atmospheric pressure in hPa
    int32_t humidity;                ///< Relative humidity (0-100%)
    int16_t precipitation_pulses;    ///< Rain gauge pulses
    float surface_temperature;       ///< Surface temperature in Celsius
    int32_t Vbat;                    ///< Battery voltage in mV
    int32_t Vpanel;                  ///< Solar panel voltage in mV
    int32_t rssi;                    ///< LoRa RSSI in dBm
    float snr;                       ///< LoRa Signal-to-Noise Ratio in dB
    int32_t sigWiFi;                 ///< WiFi signal strength (gateway)
    int32_t sigCel;                  ///< Cellular signal strength (gateway)
};

/**
 * @enum TransmissionResult
 * @brief Result codes for data transmission attempts
 */
enum TransmissionResult {
    TX_SUCCESS = 0,           ///< Data transmitted successfully
    TX_ERROR_WIFI = -1,       ///< WiFi connection error
    TX_ERROR_HTTP = -2,       ///< HTTP request error
    TX_ERROR_AUTH = -3,       ///< Authentication failure
    TX_ERROR_MEMORY = -4,     ///< Insufficient memory
    TX_ERROR_TIMEOUT = -5,    ///< Request timeout
    TX_ERROR_SERVER = -6      ///< Server returned error
};

/**
 * @class DataTransmitter
 * @brief Manages data serialization and transmission to cloud server
 * 
 * This class handles all aspects of sending sensor data to the remote server:
 * - Serializes data to MessagePack format
 * - Generates authentication signatures
 * - Manages HTTP/HTTPS connections
 * - Implements retry logic with exponential backoff
 * - Monitors memory usage
 */
class DataTransmitter {
public:
    /**
     * @brief Constructor
     * @param serverUrl Complete HTTPS URL to POST endpoint
     * @param apiKey API key for authentication
     * @param maxRetries Maximum number of retry attempts (default: 3)
     */
    DataTransmitter(const char* serverUrl, const String& apiKey, uint8_t maxRetries = 3);
    
    /**
     * @brief Destructor
     */
    ~DataTransmitter();
    
    /**
     * @brief Send sensor data to server via WiFi
     * 
     * Serializes the sensor data structure to MessagePack format,
     * adds authentication headers, and transmits via HTTPS POST.
     * Implements automatic retry with exponential backoff on failure.
     * 
     * @param data Reference to sensor data structure
     * @return TransmissionResult status code
     * 
     * @note This function blocks until transmission completes or fails
     * @note Requires active WiFi connection
     */
    TransmissionResult sendDataWiFi(const SensorData& data);
    
    /**
     * @brief Send sensor data to server via Cellular (NB-IoT HTTPS)
     *
     * Uses SSLClient (BearSSL) over TinyGsmClient TCP to perform a TLS 1.2
     * HTTPS POST. Call initCellular() first after GPRS is connected.
     *
     * Architecture: [ESP32 BearSSL] → [TinyGsmClient TCP] → [SIM7000G NB-IoT] → server:443
     *
     * @param data Reference to sensor data structure
     * @return TransmissionResult status code
     *
     * @note Requires active GPRS/NB-IoT connection and initCellular() called first
     */
    TransmissionResult sendDataCellular(const SensorData& data);

    /**
     * @brief Initialize cellular transmission parameters
     *
     * Must be called after the modem has a GPRS connection, before any
     * sendDataCellular() call. Stores the TinyGsmClient reference and
     * server parameters for use during transmission.
     *
     * @param tcpClient  Reference to TinyGsmClient (or any Arduino Client)
     * @param server     Hostname for ArduinoHttpClient (e.g. "sapi.ilha3d.com")
     * @param resource   URL path (e.g. "/sapi/sensorData/receive-data.php")
     * @param port       HTTPS port (443)
     */
    void initCellular(Client& tcpClient, const char* server, const char* resource, int port);
    
    /**
     * @brief Send data using best available connection
     * 
     * Automatically selects WiFi or Cellular based on availability.
     * Tries WiFi first, falls back to Cellular if needed.
     * 
     * @param data Reference to sensor data structure
     * @return TransmissionResult status code
     */
    TransmissionResult sendDataAuto(const SensorData& data);
    
    /**
     * @brief Set maximum retry attempts
     * @param retries Number of retries (0-10)
     */
    void setMaxRetries(uint8_t retries);
    
    /**
     * @brief Set connection timeout
     * @param timeoutMs Timeout in milliseconds
     */
    void setTimeout(uint16_t timeoutMs);
    
    /**
     * @brief Get last HTTP response code
     * @return HTTP status code from last request
     */
    int getLastHttpCode() const;
    
    /**
     * @brief Get last error message
     * @return Error description string
     */
    String getLastError() const;
    
    /**
     * @brief Enable/disable debug output
     * @param enable true to enable debug prints
     */
    void setDebugMode(bool enable);

private:
    const char* _serverUrl;          ///< Server endpoint URL (WiFi path — full URL)
    String _apiKey;                  ///< API authentication key
    uint8_t _maxRetries;             ///< Maximum transmission attempts
    uint16_t _timeout;               ///< Connection timeout (ms)
    int _lastHttpCode;               ///< Last HTTP response code
    String _lastError;               ///< Last error message
    bool _debugMode;                 ///< Debug output flag

    // Cellular-specific state (set by initCellular)
    Client*     _gsmClient;          ///< Underlying TCP socket (TinyGsmClient)
    const char* _celServer;          ///< Hostname for ArduinoHttpClient
    const char* _celResource;        ///< URL path for ArduinoHttpClient
    int         _celPort;            ///< Port for ArduinoHttpClient (443)
    
    /**
     * @brief Serialize sensor data to MessagePack format
     * 
     * Converts SensorData structure to compact binary MessagePack format.
     * Uses stack-allocated buffer to avoid heap fragmentation.
     * 
     * @param data Reference to sensor data
     * @param buffer Output buffer for serialized data
     * @param bufferSize Size of output buffer
     * @return Number of bytes written, or 0 on error
     */
    size_t serializeData(const SensorData& data, uint8_t* buffer, size_t bufferSize);
    
    /**
     * @brief Generate HMAC-SHA256 authentication signature
     * 
     * Creates a signature of the data payload using the API key.
     * This ensures data integrity and authenticity.
     * 
     * @param data Pointer to data buffer
     * @param dataLen Length of data
     * @param signature Output buffer for signature (32 bytes)
     * @return true if signature generated successfully
     */
    bool generateSignature(const uint8_t* data, size_t dataLen, uint8_t* signature);
    
    /**
     * @brief Execute HTTP POST request with retry logic (WiFi path)
     *
     * Sends data to server with automatic retry on failure.
     * Implements exponential backoff between attempts.
     *
     * @param client Reference to WiFiClientSecure
     * @param payload Data payload
     * @param payloadSize Size of payload
     * @return TransmissionResult status code
     */
    TransmissionResult executePostRequest(WiFiClientSecure& client,
                                         const uint8_t* payload,
                                         size_t payloadSize);

    /**
     * @brief Execute HTTPS POST request via cellular (NB-IoT path)
     *
     * Uses SSLClient (BearSSL TLS 1.2) over the stored _gsmClient TCP socket.
     * Timeout is 45 s to account for NB-IoT latency plus TLS handshake overhead.
     * Shares the same retry structure and HMAC logic as the WiFi path.
     *
     * @param payload    Serialized MessagePack payload
     * @param payloadSize Size of payload in bytes
     * @return TransmissionResult status code
     */
    TransmissionResult executePostRequestCellular(const uint8_t* payload, size_t payloadSize);
    
    /**
     * @brief Check available memory before transmission
     * 
     * Verifies sufficient heap memory for SSL handshake and buffers.
     * 
     * @return true if sufficient memory available
     */
    bool checkMemoryAvailability();
    
    /**
     * @brief Log debug message if debug mode enabled
     * @param message Message to log
     */
    void debugLog(const String& message);
};

/**
 * @brief Convert transmission result to human-readable string
 * @param result TransmissionResult code
 * @return Description string
 */
const char* transmissionResultToString(TransmissionResult result);

#endif // SEND_DATA_H