<?php
/**
 * @file receive-data.php
 * @brief Server-side data receiver for IoT sensor measurements
 * 
 * @author Alexandre Nuernberg
 * @date 2025-12-29
 * @version 1.0.3 - MessagePack API Fix
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

error_reporting(E_ALL);
ini_set('display_errors', 0);
ini_set('log_errors', 1);
ini_set('error_log', __DIR__ . '/error.log');

header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, X-API-Key, X-Signature');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit();
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['error' => 'Method not allowed. Use POST.']);
    exit();
}

// Include database configuration
$configPath = '/home/<HOSTINGER_USER>/private_configs/sapi/db_config.php';

if (!file_exists($configPath)) {
    http_response_code(500);
    echo json_encode(['error' => 'Server configuration error.']);
    error_log('CRITICAL: db_config.php not found at: ' . $configPath);
    exit();
}

require_once $configPath;

// Include MessagePack library
if (!file_exists(__DIR__ . '/vendor/autoload.php')) {
    http_response_code(500);
    echo json_encode(['error' => 'Server dependencies not installed.']);
    error_log('CRITICAL: vendor/autoload.php not found.');
    exit();
}

require_once __DIR__ . '/vendor/autoload.php';

// CORRECT WAY to use rybakit/msgpack library
use MessagePack\BufferUnpacker;

/**
 * @brief Validate API key from request headers
 */
function validateApiKey($providedKey) {
    global $VALID_API_KEY;
    
    if (empty($providedKey)) {
        logError('API key missing');
        return false;
    }
    
    if ($providedKey !== $VALID_API_KEY) {
        logError('Invalid API key provided');
        return false;
    }
    
    return true;
}

/**
 * @brief Validate HMAC-SHA256 signature
 */
function validateSignature($data, $providedSignature) {
    global $VALID_API_KEY;
    
    if (empty($providedSignature)) {
        logError('Signature missing');
        return false;
    }
    
    $expectedSignature = hash_hmac('sha256', $data, $VALID_API_KEY);
    
    if (!hash_equals($expectedSignature, $providedSignature)) {
        logError('Signature mismatch');
        return false;
    }
    
    return true;
}

/**
 * @brief Insert measurement into database
 */
function insertMeasurement($pdo, $data) {
    try {
        $datetime = date('Y-m-d H:i:s', $data['timestamp']);
        
        $sql = "INSERT INTO measurements (
                    id_station,
                    reading_number,
                    timestamp,
                    level_cm,
                    temperature_C,
                    pressure,
                    humidity_percentual,
                    precipitation_pulses,
                    precipitation_mm,
                    surface_temperature_C,
                    bat_voltage,
                    panel_voltage,
                    rssi,
                    snr,
                    s_wifi,
                    s_gsm
                ) VALUES (
                    :id_station,
                    :reading_number,
                    :timestamp,
                    :level_cm,
                    :temperature_C,
                    :pressure,
                    :humidity_percentual,
                    :precipitation_pulses,
                    :precipitation_mm,
                    :surface_temperature_C,
                    :bat_voltage,
                    :panel_voltage,
                    :rssi,
                    :snr,
                    :s_wifi,
                    :s_gsm
                )";
        
        $stmt = $pdo->prepare($sql);
        
        $stmt->bindValue(':id_station', $data['id_station'], PDO::PARAM_INT);
        $stmt->bindValue(':reading_number', $data['reading_number'] ?? null, PDO::PARAM_INT);
        $stmt->bindValue(':timestamp', $datetime, PDO::PARAM_STR);
        $stmt->bindValue(':level_cm', $data['level_cm'] ?? null, PDO::PARAM_INT);
        $stmt->bindValue(':temperature_C', $data['temperature_C'] ?? null, PDO::PARAM_STR);
        $stmt->bindValue(':pressure', $data['pressure'] ?? null, PDO::PARAM_STR);
        $stmt->bindValue(':humidity_percentual', $data['humidity_percentual'] ?? null, PDO::PARAM_INT);
        $stmt->bindValue(':precipitation_pulses', $data['precipitation_pulses'] ?? null, PDO::PARAM_INT);
        $stmt->bindValue(':precipitation_mm', $data['precipitation_mm'] ?? null, PDO::PARAM_INT);
        $stmt->bindValue(':surface_temperature_C', $data['surface_temperature_C'] ?? null, PDO::PARAM_STR);
        $stmt->bindValue(':bat_voltage', $data['bat_voltage'] ?? null, PDO::PARAM_STR);
        $stmt->bindValue(':panel_voltage', $data['panel_voltage'] ?? null, PDO::PARAM_STR);
        $stmt->bindValue(':rssi', $data['rssi'] ?? null, PDO::PARAM_INT);
        $stmt->bindValue(':snr', $data['snr'] ?? null, PDO::PARAM_STR);
        $stmt->bindValue(':s_wifi', $data['s_wifi'] ?? null, PDO::PARAM_INT);
        $stmt->bindValue(':s_gsm', $data['s_gsm'] ?? null, PDO::PARAM_INT);
        
        $result = $stmt->execute();
        
        if ($result) {
            logInfo('Measurement inserted: Station ' . $data['id_station'] . 
                   ', Reading #' . ($data['reading_number'] ?? 'N/A'));
        }
        
        return $result;
        
    } catch (PDOException $e) {
        logError('Database error: ' . $e->getMessage());
        return false;
    }
}

/**
 * @brief Log error message
 */
function logError($message) {
    error_log('[ERROR] ' . date('Y-m-d H:i:s') . ' - ' . $message);
}

/**
 * @brief Log info message
 */
function logInfo($message) {
    error_log('[INFO] ' . date('Y-m-d H:i:s') . ' - ' . $message);
}

/**
 * @brief Check rate limiting (simple IP-based)
 */
function checkRateLimit($ip) {
    $cacheFile = sys_get_temp_dir() . '/rate_limit_' . md5($ip) . '.txt';
    $maxRequests = 60;
    $timeWindow = 60;
    
    if (file_exists($cacheFile)) {
        $data = json_decode(file_get_contents($cacheFile), true);
        $currentTime = time();
        
        $data['requests'] = array_filter($data['requests'], function($timestamp) use ($currentTime, $timeWindow) {
            return ($currentTime - $timestamp) < $timeWindow;
        });
        
        if (count($data['requests']) >= $maxRequests) {
            logError('Rate limit exceeded for IP: ' . $ip);
            return false;
        }
        
        $data['requests'][] = $currentTime;
    } else {
        $data = ['requests' => [time()]];
    }
    
    file_put_contents($cacheFile, json_encode($data));
    return true;
}

// ============================================================================
// MAIN EXECUTION
// ============================================================================

try {
    $clientIP = $_SERVER['REMOTE_ADDR'] ?? 'unknown';
    
    if (!checkRateLimit($clientIP)) {
        http_response_code(429);
        echo json_encode(['error' => 'Too many requests. Please try again later.']);
        exit();
    }
    
    $apiKey = $_SERVER['HTTP_X_API_KEY'] ?? '';
    $signature = $_SERVER['HTTP_X_SIGNATURE'] ?? '';
    
    if (!validateApiKey($apiKey)) {
        http_response_code(401);
        echo json_encode(['error' => 'Unauthorized. Invalid API key.']);
        exit();
    }
    
    $rawData = file_get_contents('php://input');
    
    if (empty($rawData)) {
        http_response_code(400);
        echo json_encode(['error' => 'Empty payload']);
        exit();
    }
    
    if (!validateSignature($rawData, $signature)) {
        http_response_code(403);
        echo json_encode(['error' => 'Forbidden. Signature validation failed.']);
        exit();
    }
    
    // CORRECT WAY: Use BufferUnpacker instead of MessagePack constructor
    try {
        $unpacker = new BufferUnpacker();
        $unpacker->reset($rawData);
        $decodedData = $unpacker->unpack();
    } catch (Exception $e) {
        http_response_code(400);
        echo json_encode(['error' => 'Invalid MessagePack data: ' . $e->getMessage()]);
        logError('MessagePack decode error: ' . $e->getMessage());
        exit();
    }
    
    if (!isset($decodedData['id_station']) || !isset($decodedData['timestamp'])) {
        http_response_code(400);
        echo json_encode(['error' => 'Missing required fields (id_station, timestamp)']);
        exit();
    }
    
    $pdo = getDatabaseConnection();
    
    if (insertMeasurement($pdo, $decodedData)) {
        http_response_code(200);
        echo json_encode([
            'success' => true,
            'message' => 'Data received and stored successfully',
            'station_id' => $decodedData['id_station'],
            'timestamp' => date('Y-m-d H:i:s', $decodedData['timestamp'])
        ]);
    } else {
        http_response_code(500);
        echo json_encode(['error' => 'Failed to store data in database']);
    }
    
} catch (Exception $e) {
    logError('Unexpected error: ' . $e->getMessage());
    http_response_code(500);
    echo json_encode(['error' => 'Internal server error']);
}
?>