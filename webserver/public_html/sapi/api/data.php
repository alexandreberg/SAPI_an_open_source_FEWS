<?php
/**
 * @file data.php
 * @brief Authenticated GET endpoint — returns recent sensor data for the RPi
 *        prediction cron job (Issue #108).
 *
 * Query parameters:
 *   station_id  int    Required. Station identifier.
 *   field       string Required. 'level' → level_delta_cm; 'precip' → precipitation_mm.
 *   hours       int    Optional. Lookback window in hours (default 6, max 48 for level/precip, max 720 for merge).
 *
 * Authentication: X-API-Key header must match $PREDICT_API_KEY from api_config.php.
 *
 * Response: JSON array of {timestamp: "Y-m-d H:i:s", value: float}
 *           ordered oldest-first.  Returns [] for valid requests with no data.
 *
 * @author Alexandre Nuernberg
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
ini_set('error_log', dirname(__DIR__) . '/error.log');

header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, X-API-Key');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit();
}

if ($_SERVER['REQUEST_METHOD'] !== 'GET') {
    http_response_code(405);
    echo json_encode(['error' => 'Method not allowed. Use GET.']);
    exit();
}

// ── Config files ──────────────────────────────────────────────────────────────
$apiConfigPath = '/home/<HOSTINGER_USER>/private_configs/sapi/api_config.php';
$dbConfigPath  = '/home/<HOSTINGER_USER>/private_configs/sapi/db_config.php';

foreach ([$apiConfigPath, $dbConfigPath] as $path) {
    if (!file_exists($path)) {
        http_response_code(500);
        echo json_encode(['error' => 'Server configuration error.']);
        error_log('[data.php] Missing config: ' . $path);
        exit();
    }
}

require_once $apiConfigPath;
require_once $dbConfigPath;

// ── Authentication ────────────────────────────────────────────────────────────
$providedKey = $_SERVER['HTTP_X_API_KEY'] ?? '';

if (empty($providedKey) || $providedKey !== $PREDICT_API_KEY) {
    http_response_code(401);
    echo json_encode(['error' => 'Unauthorized.']);
    error_log('[data.php] Invalid or missing API key');
    exit();
}

// ── Parameter validation ──────────────────────────────────────────────────────
$stationId = isset($_GET['station_id']) ? (int)$_GET['station_id'] : 0;
$field     = isset($_GET['field'])      ? trim((string)$_GET['field']) : '';
$hoursRaw  = isset($_GET['hours']) ? (int)$_GET['hours'] : 6;
// merge allows a longer window for the daily refresh/backfill script.
$hoursCap  = ($field === 'merge') ? 720 : 48;
$hours     = min($hoursRaw, $hoursCap);
if ($hours <= 0) { $hours = 6; }

$allowedFields = ['level', 'precip', 'merge'];
if (!in_array($field, $allowedFields, true)) {
    http_response_code(400);
    echo json_encode(['error' => 'Invalid field. Use level, precip, or merge.']);
    exit();
}

// station_id is not used for merge; validate only for level/precip.
if ($field !== 'merge' && $stationId <= 0) {
    http_response_code(400);
    echo json_encode(['error' => 'Missing or invalid station_id.']);
    exit();
}

if ($hours <= 0) {
    $hours = 6;
}

// ── Query ─────────────────────────────────────────────────────────────────────
try {
    $pdo = getDatabaseConnection();

    if ($field === 'merge') {
        // MERGE/GPM hourly precipitation — fallback source when Station-02 is offline.
        // Returns hourly rows; inference.py forward-fills and divides by 12 (5-min slots).
        $sql = "SELECT
                    DATE_FORMAT(timestamp, '%Y-%m-%d %H:%i:%S') AS timestamp,
                    prec_mm AS value
                FROM `merge`
                WHERE timestamp >= UTC_TIMESTAMP() - INTERVAL :hours HOUR
                  AND prec_mm IS NOT NULL
                ORDER BY timestamp ASC";

        $stmt = $pdo->prepare($sql);
        $stmt->bindValue(':hours', $hours, PDO::PARAM_INT);
        $stmt->execute();

        $rows = $stmt->fetchAll(PDO::FETCH_ASSOC);
        foreach ($rows as &$row) {
            $row['value'] = $row['value'] !== null ? (float)$row['value'] : null;
        }
        unset($row);

        echo json_encode($rows);
        exit();
    }

    if ($field === 'level') {
        // level_delta_cm — the delta-filtered, zero-lag level used by the ML model.
        $sql = "SELECT
                    DATE_FORMAT(timestamp, '%Y-%m-%d %H:%i:%S') AS timestamp,
                    level_delta_cm AS value
                FROM measurements
                WHERE id_station = :station_id
                  AND timestamp >= UTC_TIMESTAMP() - INTERVAL :hours HOUR
                  AND level_delta_cm IS NOT NULL
                ORDER BY timestamp ASC";
    } else {
        // precipitation_mm — tipping-bucket mm per reading interval.
        $sql = "SELECT
                    DATE_FORMAT(timestamp, '%Y-%m-%d %H:%i:%S') AS timestamp,
                    precipitation_mm AS value
                FROM measurements
                WHERE id_station = :station_id
                  AND timestamp >= UTC_TIMESTAMP() - INTERVAL :hours HOUR
                  AND precipitation_mm IS NOT NULL
                ORDER BY timestamp ASC";
    }

    $stmt = $pdo->prepare($sql);
    $stmt->bindValue(':station_id', $stationId, PDO::PARAM_INT);
    $stmt->bindValue(':hours',      $hours,     PDO::PARAM_INT);
    $stmt->execute();

    $rows = $stmt->fetchAll(PDO::FETCH_ASSOC);

    // Cast value to float for JSON output.
    foreach ($rows as &$row) {
        $row['value'] = $row['value'] !== null ? (float)$row['value'] : null;
    }
    unset($row);

    echo json_encode($rows);

} catch (PDOException $e) {
    error_log('[data.php] DB error: ' . $e->getMessage());
    http_response_code(500);
    echo json_encode(['error' => 'Database error.']);
}
