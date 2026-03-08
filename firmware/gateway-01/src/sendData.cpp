/**
 * @file sendData.cpp
 * @brief Implementation of data transmission module
 * 
 * @author Alexandre Nuernberg
 * @date 2025-12-30
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

#include "sendData.h"
#include "stationConfig.h"  // For precipitation conversion
#include <mbedtls/md.h>
#include <SSLClient.h>
#include <ArduinoHttpClient.h>
#include "trust_anchors.h"  ///< ISRG Root X1 BearSSL trust anchor

// Memory requirements for SSL/TLS
#define MIN_FREE_HEAP_FOR_SSL 55000

// HTTP timeout settings
#define DEFAULT_TIMEOUT_MS 10000

// Retry settings
#define RETRY_BASE_DELAY_MS 1000
#define RETRY_MAX_DELAY_MS 30000

/**
 * @brief Constructor implementation
 */
DataTransmitter::DataTransmitter(const char* serverUrl, const String& apiKey, uint8_t maxRetries)
    : _serverUrl(serverUrl)
    , _apiKey(apiKey)
    , _maxRetries(maxRetries)
    , _timeout(DEFAULT_TIMEOUT_MS)
    , _lastHttpCode(0)
    , _lastError("")
    , _debugMode(false)
    , _gsmClient(nullptr)
    , _celServer(nullptr)
    , _celResource(nullptr)
    , _celPort(443)
{
    debugLog("DataTransmitter initialized");
}

/**
 * @brief Destructor implementation
 */
DataTransmitter::~DataTransmitter() {
    debugLog("DataTransmitter destroyed");
}

/**
 * @brief Send data via WiFi connection
 */
TransmissionResult DataTransmitter::sendDataWiFi(const SensorData& data) {
    debugLog("Starting WiFi transmission...");
    
    // Check WiFi connection
    if (WiFi.status() != WL_CONNECTED) {
        _lastError = "WiFi not connected";
        debugLog(_lastError);
        return TX_ERROR_WIFI;
    }
    
    // Check memory availability
    if (!checkMemoryAvailability()) {
        _lastError = "Insufficient memory for SSL";
        debugLog(_lastError);
        return TX_ERROR_MEMORY;
    }
    
    // Allocate buffer for serialized data (stack allocation)
    uint8_t buffer[256];
    size_t payloadSize = serializeData(data, buffer, sizeof(buffer));
    
    if (payloadSize == 0) {
        _lastError = "Serialization failed";
        debugLog(_lastError);
        return TX_ERROR_MEMORY;
    }
    
    debugLog("Data serialized: " + String(payloadSize) + " bytes");
    
    // Create WiFi client
    WiFiClientSecure client;
    client.setInsecure(); // Use TLS without certificate verification
    
    // Execute POST request with retry logic
    TransmissionResult result = executePostRequest(client, buffer, payloadSize);
    
    return result;
}

/**
 * @brief Initialize cellular transmission parameters.
 *
 * Must be called after the modem has a GPRS connection and before any
 * sendDataCellular() call. Stores a reference to the TinyGsmClient TCP
 * socket and the server connection parameters.
 *
 * @param tcpClient  TinyGsmClient (or any Arduino Client) wrapping the modem
 * @param server     Hostname for ArduinoHttpClient
 * @param resource   URL path for the POST endpoint
 * @param port       HTTPS port (443)
 */
void DataTransmitter::initCellular(Client& tcpClient, const char* server, const char* resource, int port) {
    _gsmClient   = &tcpClient;
    _celServer   = server;
    _celResource = resource;
    _celPort     = port;
    debugLog("Cellular initialized — server: " + String(server) + ":" + String(port));
}

/**
 * @brief Send data via Cellular NB-IoT HTTPS connection.
 *
 * Serializes, signs, and POSTs via SSLClient (BearSSL TLS 1.2) over the
 * TinyGsmClient TCP socket. Call initCellular() first.
 *
 * @param data Sensor data to transmit
 * @return TransmissionResult status code
 */
TransmissionResult DataTransmitter::sendDataCellular(const SensorData& data) {
    debugLog("Starting Cellular HTTPS transmission...");

    if (_gsmClient == nullptr) {
        _lastError = "Cellular not initialized — call initCellular() first";
        debugLog(_lastError);
        return TX_ERROR_WIFI;
    }

    if (!checkMemoryAvailability()) {
        _lastError = "Insufficient memory for TLS handshake";
        debugLog(_lastError);
        return TX_ERROR_MEMORY;
    }

    uint8_t buffer[256];
    size_t payloadSize = serializeData(data, buffer, sizeof(buffer));
    if (payloadSize == 0) {
        _lastError = "Serialization failed";
        debugLog(_lastError);
        return TX_ERROR_MEMORY;
    }

    debugLog("Data serialized: " + String(payloadSize) + " bytes");
    return executePostRequestCellular(buffer, payloadSize);
}

/**
 * @brief Execute HTTPS POST via cellular with retry logic.
 *
 * Creates an SSLClient (BearSSL) wrapping the stored _gsmClient TCP socket.
 * Uses ArduinoHttpClient for the HTTP layer. Timeout is 45 s to budget for
 * NB-IoT round-trip latency (up to 30 s) plus TLS handshake (up to 15 s).
 *
 * GPIO34 is used as the BearSSL entropy source: it is a floating input-only
 * pin on the LilyGO T-SIM7000G, producing noisy ADC reads.
 *
 * @param payload     Serialized MessagePack payload
 * @param payloadSize Payload length in bytes
 * @return TransmissionResult status code
 */
TransmissionResult DataTransmitter::executePostRequestCellular(const uint8_t* payload, size_t payloadSize) {
    TransmissionResult result = TX_ERROR_HTTP;

    // Generate HMAC-SHA256 signature (same logic as WiFi path)
    uint8_t signature[32];
    if (!generateSignature(payload, payloadSize, signature)) {
        _lastError = "Failed to generate signature";
        debugLog(_lastError);
        return TX_ERROR_AUTH;
    }

    String signatureHex = "";
    for (int i = 0; i < 32; i++) {
        char hex[3];
        sprintf(hex, "%02x", signature[i]);
        signatureHex += hex;
    }

    // SSLClient wraps gsmClient: TLS runs on ESP32, modem carries opaque TCP bytes.
    // GPIO34 = floating input-only on LilyGO T-SIM7000G — valid ADC for entropy.
    SSLClient sslClient(*_gsmClient, TAs, 1, 34);

    // Retry loop — same exponential backoff as WiFi path
    for (uint8_t attempt = 0; attempt <= _maxRetries; attempt++) {
        if (attempt > 0) {
            uint32_t delayMs = min((uint32_t)(RETRY_BASE_DELAY_MS * pow(2, attempt - 1)),
                                  (uint32_t)RETRY_MAX_DELAY_MS);
            debugLog("Retry attempt " + String(attempt) + " after " + String(delayMs) + " ms");
            delay(delayMs);
        }

        // 45 s timeout: 30 s NB-IoT latency budget + 15 s TLS handshake budget
        HttpClient https(sslClient, _celServer, _celPort);
        https.setTimeout(45000);

        debugLog("Sending HTTPS POST (attempt " + String(attempt + 1) + ")");
        debugLog("Free heap: " + String(ESP.getFreeHeap()) + " bytes");

        https.beginRequest();
        int err = https.post(_celResource);
        if (err != 0) {
            _lastError = "https.post() error: " + String(err);
            debugLog(_lastError);
            https.stop();
            result = TX_ERROR_HTTP;
            continue;
        }

        https.sendHeader("Content-Type",   "application/msgpack");
        https.sendHeader("X-API-Key",      _apiKey);
        https.sendHeader("X-Signature",    signatureHex);
        https.sendHeader("Content-Length", (int)payloadSize);
        https.beginBody();
        https.write((uint8_t*)payload, payloadSize);
        https.endRequest();

        _lastHttpCode = https.responseStatusCode();

        if (_lastHttpCode == 200) {
            debugLog("Cellular HTTPS transmission successful (HTTP 200)");
            result = TX_SUCCESS;
            https.stop();
            break;
        } else if (_lastHttpCode > 0) {
            _lastError = "HTTP error: " + String(_lastHttpCode);
            debugLog(_lastError);
            String response = https.responseBody();
            debugLog("Server response: " + response);
            result = TX_ERROR_SERVER;
        } else {
            _lastError = "Connection error: " + String(_lastHttpCode);
            debugLog(_lastError);
            result = TX_ERROR_HTTP;
        }

        https.stop();

        // Don't retry on authentication errors
        if (_lastHttpCode == 401 || _lastHttpCode == 403) {
            debugLog("Authentication error, aborting retries");
            result = TX_ERROR_AUTH;
            break;
        }
    }

    return result;
}

/**
 * @brief Automatic connection selection
 */
TransmissionResult DataTransmitter::sendDataAuto(const SensorData& data) {
    debugLog("Auto-selecting best connection...");
    
    // Try WiFi first
    if (WiFi.status() == WL_CONNECTED) {
        debugLog("Using WiFi connection");
        return sendDataWiFi(data);
    }
    
    // Fallback to Cellular
    debugLog("WiFi unavailable, trying Cellular");
    return sendDataCellular(data);
}

/**
 * @brief Serialize sensor data to MessagePack
 */
size_t DataTransmitter::serializeData(const SensorData& data, uint8_t* buffer, size_t bufferSize) {
    // Create JSON document with appropriate size
    JsonDocument doc;
    
    // Add data fields - matching PHP field names exactly
    doc["id_station"] = data.idStation;
    doc["reading_number"] = data.reading_number;
    doc["timestamp"] = data.timestamp;
    doc["level_cm"] = data.level;
    
    // Temperature
    if (data.temperature != -99.0) {
        doc["temperature_C"] = data.temperature;
    }
    
    // Pressure
    if (data.pressure != -99.0) {
        doc["pressure"] = data.pressure;
    }
    
    // Humidity
    if (data.humidity != -99) {
        doc["humidity_percentual"] = data.humidity;
    }
    
    // Precipitation
    if (data.precipitation_pulses != -99) {
        doc["precipitation_pulses"] = data.precipitation_pulses;
        
        // Calculate precipitation in mm from pulses
        float prec_mm = calculatePrecipitation(data.idStation, data.precipitation_pulses);
        
        // Only add if valid (station has rain gauge)
        if (prec_mm >= 0.0) {
            doc["precipitation_mm"] = prec_mm;
        }
    }
    
    // Surface temperature
    if (data.surface_temperature != -99.0) {
        doc["surface_temperature_C"] = data.surface_temperature;
    }
    
    // Battery voltage (convert mV to V)
    if (data.Vbat != -99) {
        doc["bat_voltage"] = data.Vbat / 1000.0;
    }
    
    // Panel voltage (convert mV to V)
    if (data.Vpanel != -99) {
        doc["panel_voltage"] = data.Vpanel / 1000.0;
    }
    
    // Signal strengths (always include)
    doc["rssi"] = data.rssi;
    doc["snr"] = data.snr;
    doc["s_wifi"] = data.sigWiFi;
    doc["s_gsm"] = data.sigCel;
    
    // Serialize to MessagePack format
    size_t size = serializeMsgPack(doc, buffer, bufferSize);
    
    if (size == 0) {
        debugLog("MessagePack serialization failed");
        return 0;
    }
    
    return size;
}

/**
 * @brief Generate HMAC-SHA256 signature
 */
bool DataTransmitter::generateSignature(const uint8_t* data, size_t dataLen, uint8_t* signature) {
    mbedtls_md_context_t ctx;
    mbedtls_md_type_t md_type = MBEDTLS_MD_SHA256;
    
    mbedtls_md_init(&ctx);
    
    if (mbedtls_md_setup(&ctx, mbedtls_md_info_from_type(md_type), 1) != 0) {
        mbedtls_md_free(&ctx);
        return false;
    }
    
    if (mbedtls_md_hmac_starts(&ctx, (const unsigned char*)_apiKey.c_str(), _apiKey.length()) != 0) {
        mbedtls_md_free(&ctx);
        return false;
    }
    
    if (mbedtls_md_hmac_update(&ctx, data, dataLen) != 0) {
        mbedtls_md_free(&ctx);
        return false;
    }
    
    if (mbedtls_md_hmac_finish(&ctx, signature) != 0) {
        mbedtls_md_free(&ctx);
        return false;
    }
    
    mbedtls_md_free(&ctx);
    return true;
}

/**
 * @brief Execute POST request with retry logic
 */
TransmissionResult DataTransmitter::executePostRequest(WiFiClientSecure& client, 
                                                      const uint8_t* payload, 
                                                      size_t payloadSize) {
    HTTPClient https;
    TransmissionResult result = TX_ERROR_HTTP;
    
    // Generate authentication signature
    uint8_t signature[32];
    if (!generateSignature(payload, payloadSize, signature)) {
        _lastError = "Failed to generate signature";
        debugLog(_lastError);
        return TX_ERROR_AUTH;
    }
    
    // Convert signature to hex string
    String signatureHex = "";
    for (int i = 0; i < 32; i++) {
        char hex[3];
        sprintf(hex, "%02x", signature[i]);
        signatureHex += hex;
    }
    
    // Retry loop with exponential backoff
    for (uint8_t attempt = 0; attempt <= _maxRetries; attempt++) {
        if (attempt > 0) {
            uint32_t delayMs = min((uint32_t)(RETRY_BASE_DELAY_MS * pow(2, attempt - 1)), 
                                  (uint32_t)RETRY_MAX_DELAY_MS);
            debugLog("Retry attempt " + String(attempt) + " after " + String(delayMs) + "ms");
            delay(delayMs);
        }
        
        // Initialize HTTPS connection
        if (!https.begin(client, _serverUrl)) {
            _lastError = "Failed to initialize HTTPS";
            debugLog(_lastError);
            continue;
        }
        
        https.setTimeout(_timeout);
        
        // Set headers
        https.addHeader("Content-Type", "application/msgpack");
        https.addHeader("X-API-Key", _apiKey);
        https.addHeader("X-Signature", signatureHex);
        https.addHeader("Connection", "keep-alive");
        
        debugLog("Sending POST request (attempt " + String(attempt + 1) + ")");
        debugLog("Free heap: " + String(ESP.getFreeHeap()) + " bytes");
        
        // Send POST request
        _lastHttpCode = https.POST((uint8_t*)payload, payloadSize);
        
        // Check response
        if (_lastHttpCode == 200) {
            debugLog("Transmission successful (HTTP 200)");
            result = TX_SUCCESS;
            https.end();
            break;
        } else if (_lastHttpCode > 0) {
            _lastError = "HTTP error: " + String(_lastHttpCode);
            debugLog(_lastError);
            String response = https.getString();
            debugLog("Server response: " + response);
            result = TX_ERROR_SERVER;
        } else {
            _lastError = "Connection error: " + String(_lastHttpCode);
            debugLog(_lastError);
            result = TX_ERROR_HTTP;
        }
        
        https.end();
        
        // Don't retry on authentication errors
        if (_lastHttpCode == 401 || _lastHttpCode == 403) {
            debugLog("Authentication error, aborting retries");
            result = TX_ERROR_AUTH;
            break;
        }
    }
    
    return result;
}

/**
 * @brief Check memory availability
 */
bool DataTransmitter::checkMemoryAvailability() {
    uint32_t freeHeap = ESP.getFreeHeap();
    debugLog("Free heap: " + String(freeHeap) + " bytes");
    return freeHeap >= MIN_FREE_HEAP_FOR_SSL;
}

/**
 * @brief Debug logging
 */
void DataTransmitter::debugLog(const String& message) {
    if (_debugMode) {
        Serial.println("[DataTransmitter] " + message);
    }
}

/**
 * @brief Setters implementation
 */
void DataTransmitter::setMaxRetries(uint8_t retries) {
    _maxRetries = min(retries, (uint8_t)10);
}

void DataTransmitter::setTimeout(uint16_t timeoutMs) {
    _timeout = timeoutMs;
}

void DataTransmitter::setDebugMode(bool enable) {
    _debugMode = enable;
}

/**
 * @brief Getters implementation
 */
int DataTransmitter::getLastHttpCode() const {
    return _lastHttpCode;
}

String DataTransmitter::getLastError() const {
    return _lastError;
}

/**
 * @brief Convert result code to string
 */
const char* transmissionResultToString(TransmissionResult result) {
    switch (result) {
        case TX_SUCCESS: return "Success";
        case TX_ERROR_WIFI: return "WiFi Error";
        case TX_ERROR_HTTP: return "HTTP Error";
        case TX_ERROR_AUTH: return "Authentication Error";
        case TX_ERROR_MEMORY: return "Memory Error";
        case TX_ERROR_TIMEOUT: return "Timeout";
        case TX_ERROR_SERVER: return "Server Error";
        default: return "Unknown Error";
    }
}