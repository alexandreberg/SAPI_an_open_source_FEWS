<?php
/**
 * @file predictions_m6.php
 * @brief Authenticated POST endpoint — stores one M6 MLR prediction result from
 *        the RPi cron job and records alert state transitions (Issue #120).
 *
 * Isolated from predictions.php (M4): writes to predictions_m6 and
 * prediction_alerts_m6 tables.  Uses the same X-API-Key authentication.
 *
 * Expected JSON body (identical schema to predictions.php):
 * {
 *   "station_id":        int,
 *   "timestamp":         "Y-m-d\TH:i:s\Z",
 *   "h_pred_30":         float,
 *   "h_pred_60":         float,
 *   "h_pred_90":         float,
 *   "h_pred_120":        float,
 *   "precip_rolling":    float,
 *   "precip_source":     "station02" | "merge",
 *   "gate_active":       bool,
 *   "raw_alert_level":   "none" | "atencao" | "alerta" | "inundacao",
 *   "alert_level":       "none" | "atencao" | "alerta" | "inundacao",
 *   "consecutive_steps": int,
 *   "alert_transition":  "fired" | "cleared" | "none"
 * }
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
header('Access-Control-Allow-Methods: POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, X-API-Key');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit();
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['error' => 'Method not allowed. Use POST.']);
    exit();
}

// ── Config files ──────────────────────────────────────────────────────────────
$apiConfigPath = '/home/<HOSTINGER_USER>/private_configs/sapi/api_config.php';
$dbConfigPath  = '/home/<HOSTINGER_USER>/private_configs/sapi/db_config.php';

foreach ([$apiConfigPath, $dbConfigPath] as $path) {
    if (!file_exists($path)) {
        http_response_code(500);
        echo json_encode(['error' => 'Server configuration error.']);
        error_log('[predictions_m6.php] Missing config: ' . $path);
        exit();
    }
}

require_once $apiConfigPath;
require_once $dbConfigPath;
require_once dirname(__DIR__) . '/email_helper.php';

// ── Email notification helpers ────────────────────────────────────────────────

define('PRED_M6_MAIL_FROM',      'alerta.ilha3d@gmail.com');
define('PRED_M6_MAIL_FROM_NAME', 'SAPI - Alerta Preditivo M6');

/** @var array<string,string> Alert level labels in Portuguese. */
const PRED_M6_LEVEL_LABELS = [
    'none'      => 'Normalizado',
    'atencao'   => 'ATENÇÃO',
    'alerta'    => 'ALERTA',
    'inundacao' => 'INUNDAÇÃO',
];

/**
 * @brief Builds the email body for an M6 MLR predictive alert notification.
 *
 * @param string     $stationName   Human-readable station name.
 * @param string     $transition    'fired' or 'cleared'.
 * @param string     $alertLevel    Alert level at transition time.
 * @param float      $hPred30       +30 min prediction (cm).
 * @param float      $hPred60       +60 min prediction (cm).
 * @param float      $hPred90       +90 min prediction (cm).
 * @param float      $hPred120      +120 min prediction (cm).
 * @param float|null $precipRolling 6-hour rolling precipitation (mm).
 * @param string     $precipSource  'station02' or 'merge'.
 * @param string     $timestamp     UTC timestamp string.
 * @return string                   Plain-text email body.
 */
function buildM6EmailBody(
    string  $stationName,
    string  $transition,
    string  $alertLevel,
    float   $hPred30,
    float   $hPred60,
    float   $hPred90,
    float   $hPred120,
    ?float  $precipRolling,
    string  $precipSource,
    string  $timestamp
): string {
    $levelLabel  = PRED_M6_LEVEL_LABELS[$alertLevel] ?? strtoupper($alertLevel);
    $precipStr   = $precipRolling !== null
        ? number_format($precipRolling, 1) . ' mm (' . $precipSource . ')'
        : 'N/D';

    if ($transition === 'fired') {
        return
            "[SAPI] Alerta Preditivo M6 MLR — {$levelLabel} — {$stationName}\n" .
            "Timestamp: {$timestamp}\n\n" .
            "O modelo M6 MLR (Regressão Linear) prevê um evento de inundação.\n\n" .
            "Projeções de nível:\n" .
            "  +30 min : " . number_format($hPred30,  1) . " cm\n" .
            "  +60 min : " . number_format($hPred60,  1) . " cm\n" .
            "  +90 min : " . number_format($hPred90,  1) . " cm\n" .
            " +120 min : " . number_format($hPred120, 1) . " cm\n\n" .
            "Precipitação (6h): {$precipStr}\n";
    }

    return
        "[SAPI] Alerta Preditivo M6 MLR Normalizado — {$stationName}\n" .
        "Timestamp: {$timestamp}\n\n" .
        "Situação normalizada — todos os horizontes abaixo dos limites.\n\n" .
        "Projeções atuais:\n" .
        "  +30 min : " . number_format($hPred30,  1) . " cm\n" .
        "  +60 min : " . number_format($hPred60,  1) . " cm\n" .
        "  +90 min : " . number_format($hPred90,  1) . " cm\n" .
        " +120 min : " . number_format($hPred120, 1) . " cm\n\n" .
        "Precipitação (6h): {$precipStr}\n";
}

/** @var string Content-ID used to reference the embedded chart image from the HTML body. */
const PRED_M6_CHART_CID = 'predictionchartm6';

/**
 * @brief Sends an M6 alert email via Gmail SMTP (PHPMailer).
 *
 * The chart, when present, is embedded as inline image bytes (Content-ID),
 * never referenced by a public URL — a URL points at a file that gets
 * overwritten by the station's next alert, so an email opened later would
 * show a chart from a different, later moment than when it was sent
 * (Issue #190).
 *
 * @param string      $to        Recipient email address.
 * @param string      $subject   Email subject line.
 * @param string      $body      Plain-text body.
 * @param string|null $chartPng  Raw PNG bytes of the chart (fired only), or null.
 * @return bool                  True on success, false on failure.
 */
function sendM6Email(string $to, string $subject, string $body, ?string $chartPng = null): bool
{
    $htmlBody  = '<div style="font-family:sans-serif;font-size:14px;line-height:1.6;">';
    $htmlBody .= nl2br(htmlspecialchars($body));

    if ($chartPng !== null) {
        $htmlBody .= '<img src="cid:' . PRED_M6_CHART_CID . '" '
                   . 'alt="Gráfico de previsão M6" '
                   . 'style="max-width:600px;width:100%;margin:16px 0;display:block;">';
    }

    $htmlBody .= '<p style="margin-top:16px;">'
               . '<a href="https://ilha3d.com/sapi/predictions.php" style="color:#1565C0;">'
               . 'Ver previsões no painel SAPI</a></p>';
    $htmlBody .= '<hr style="margin-top:20px;">';
    $htmlBody .= '<small style="color:#666;">Sistema SAPI — IFSC Florianópolis<br>';
    $htmlBody .= 'Notificação gerada automaticamente pelo pipeline preditivo M6 MLR.</small>';
    $htmlBody .= '</div>';

    $ok = sendEmailViaSMTP($to, $subject, $htmlBody, PRED_M6_MAIL_FROM_NAME, $chartPng, PRED_M6_CHART_CID);
    if (!$ok) {
        error_log('[predictions_m6.php] sendEmailViaSMTP() failed sending to ' . $to);
    }
    return $ok;
}

/**
 * @brief Fetches the station name from the database.
 *
 * @param PDO $pdo        Database connection.
 * @param int $stationId  Station primary key.
 * @return string         Station name or fallback string.
 */
function getM6StationName(PDO $pdo, int $stationId): string
{
    $stmt = $pdo->prepare('SELECT name FROM stations WHERE id = ?');
    $stmt->execute([$stationId]);
    $row = $stmt->fetch();
    return $row ? $row['name'] : "Estação {$stationId}";
}

/**
 * @brief Sends email notifications for an M6 alert transition.
 *
 * @param PDO         $pdo             Database connection.
 * @param int         $alertId         ID of the prediction_alerts_m6 row just inserted.
 * @param int         $stationId       Station ID.
 * @param string      $alertTransition 'fired' or 'cleared'.
 * @param string      $alertLevel      Alert level at transition.
 * @param float       $hPred30         +30 min prediction (cm).
 * @param float       $hPred60         +60 min prediction (cm).
 * @param float       $hPred90         +90 min prediction (cm).
 * @param float       $hPred120        +120 min prediction (cm).
 * @param float|null  $precipRolling   6-hour rolling precipitation (mm).
 * @param string      $precipSource    Precipitation source.
 * @param string      $timestamp       UTC timestamp string.
 * @param string|null $chartB64        Base64-encoded PNG chart (fired only), or null.
 * @return void
 */
function sendM6Notifications(
    PDO    $pdo,
    int    $alertId,
    int    $stationId,
    string $alertTransition,
    string $alertLevel,
    float  $hPred30,
    float  $hPred60,
    float  $hPred90,
    float  $hPred120,
    ?float $precipRolling,
    string $precipSource,
    string $timestamp,
    ?string $chartB64 = null
): void {
    $stationName = getM6StationName($pdo, $stationId);
    $levelLabel  = PRED_M6_LEVEL_LABELS[$alertLevel] ?? strtoupper($alertLevel);

    $subject = $alertTransition === 'fired'
        ? "[SAPI] Alerta Preditivo M6 MLR — {$levelLabel} — {$stationName}"
        : "[SAPI] Alerta Preditivo M6 MLR Normalizado — {$stationName}";

    $body = buildM6EmailBody(
        $stationName, $alertTransition, $alertLevel,
        $hPred30, $hPred60, $hPred90, $hPred120,
        $precipRolling, $precipSource, $timestamp
    );

    // Decode the chart PNG once; the bytes are embedded fresh in every recipient's
    // email (Issue #190 — must not be saved to a shared/overwritable public URL).
    $chartPng = null;
    if ($chartB64 !== null && $alertTransition === 'fired') {
        $chartPng = base64_decode($chartB64, true);
        if ($chartPng === false) {
            error_log('[predictions_m6.php] Invalid base64 chart data for station ' . $stationId . ' — email will have no image');
            $chartPng = null;
        }
    }

    $stmt = $pdo->prepare(
        'SELECT ac.email
         FROM alert_contacts ac
         JOIN contact_stations cs ON cs.id_contact = ac.id
         WHERE cs.id_station = ?
           AND ac.enabled = 1
           AND ac.deleted_at IS NULL
           AND ac.email IS NOT NULL
           AND ac.email <> \'\''
    );
    $stmt->execute([$stationId]);
    $contacts = $stmt->fetchAll();

    $anySent = false;
    foreach ($contacts as $contact) {
        $ok = sendM6Email($contact['email'], $subject, $body, $chartPng);
        if ($ok) {
            $anySent = true;
        }
        error_log(sprintf(
            '[predictions_m6.php] email %s → %s: %s',
            $alertTransition,
            $contact['email'],
            $ok ? 'sent' : 'failed'
        ));
    }

    if ($anySent || empty($contacts)) {
        try {
            $freshPdo = getDatabaseConnection();
            $freshPdo->prepare(
                'UPDATE prediction_alerts_m6 SET notification_sent = 1 WHERE id = ?'
            )->execute([$alertId]);
        } catch (Exception $dbEx) {
            error_log('[predictions_m6.php] Failed to mark notification_sent for alert '
                      . $alertId . ': ' . $dbEx->getMessage());
        }
    }
}

// ── Authentication ────────────────────────────────────────────────────────────
$providedKey = $_SERVER['HTTP_X_API_KEY'] ?? '';

if (empty($providedKey) || $providedKey !== $PREDICT_API_KEY) {
    http_response_code(401);
    echo json_encode(['error' => 'Unauthorized.']);
    error_log('[predictions_m6.php] Invalid or missing API key');
    exit();
}

// ── Parse body ────────────────────────────────────────────────────────────────
$raw = file_get_contents('php://input');
if (empty($raw)) {
    http_response_code(400);
    echo json_encode(['error' => 'Empty request body.']);
    exit();
}

$data = json_decode($raw, true);
if ($data === null) {
    http_response_code(400);
    echo json_encode(['error' => 'Invalid JSON.']);
    exit();
}

// ── Required fields ───────────────────────────────────────────────────────────
$required = ['station_id', 'timestamp', 'h_pred_30', 'h_pred_60', 'h_pred_90', 'h_pred_120'];
foreach ($required as $field) {
    if (!isset($data[$field])) {
        http_response_code(400);
        echo json_encode(['error' => "Missing required field: $field"]);
        exit();
    }
}

// ── Sanitise inputs ───────────────────────────────────────────────────────────
$stationId       = (int)$data['station_id'];
$timestamp       = date('Y-m-d H:i:s', strtotime($data['timestamp']));
$hPred30         = isset($data['h_pred_30'])  ? (float)$data['h_pred_30']  : null;
$hPred60         = isset($data['h_pred_60'])  ? (float)$data['h_pred_60']  : null;
$hPred90         = isset($data['h_pred_90'])  ? (float)$data['h_pred_90']  : null;
$hPred120        = isset($data['h_pred_120']) ? (float)$data['h_pred_120'] : null;
$precipRolling   = isset($data['precip_rolling']) ? (float)$data['precip_rolling'] : null;
$precipSource    = in_array($data['precip_source'] ?? '', ['station02', 'merge'], true)
                   ? $data['precip_source'] : 'unknown';
$gateActive      = !empty($data['gate_active']) ? 1 : 0;

$validLevels   = ['none', 'atencao', 'alerta', 'inundacao'];
$rawAlertLevel = in_array($data['raw_alert_level'] ?? '', $validLevels, true)
                 ? $data['raw_alert_level'] : 'none';
$alertLevel    = in_array($data['alert_level'] ?? '', $validLevels, true)
                 ? $data['alert_level'] : 'none';

$validTransitions = ['fired', 'cleared', 'none'];
$alertTransition  = in_array($data['alert_transition'] ?? '', $validTransitions, true)
                    ? $data['alert_transition'] : 'none';
$consecutiveSteps = isset($data['consecutive_steps']) ? (int)$data['consecutive_steps'] : 0;

$chartB64 = (isset($data['chart_b64']) && is_string($data['chart_b64']) && strlen($data['chart_b64']) > 0)
            ? $data['chart_b64'] : null;

if ($stationId <= 0) {
    http_response_code(400);
    echo json_encode(['error' => 'Invalid station_id.']);
    exit();
}

// ── Database inserts ──────────────────────────────────────────────────────────
try {
    $pdo = getDatabaseConnection();
    $pdo->beginTransaction();

    $sql = "INSERT INTO predictions_m6
                (id_station, timestamp, h_pred_30, h_pred_60, h_pred_90, h_pred_120,
                 precip_rolling, precip_source, gate_active, raw_alert_level, alert_level)
            VALUES
                (:id_station, :timestamp, :h_pred_30, :h_pred_60, :h_pred_90, :h_pred_120,
                 :precip_rolling, :precip_source, :gate_active, :raw_alert_level, :alert_level)";

    $stmt = $pdo->prepare($sql);
    $stmt->bindValue(':id_station',      $stationId,     PDO::PARAM_INT);
    $stmt->bindValue(':timestamp',       $timestamp,     PDO::PARAM_STR);
    $stmt->bindValue(':h_pred_30',       $hPred30,       PDO::PARAM_STR);
    $stmt->bindValue(':h_pred_60',       $hPred60,       PDO::PARAM_STR);
    $stmt->bindValue(':h_pred_90',       $hPred90,       PDO::PARAM_STR);
    $stmt->bindValue(':h_pred_120',      $hPred120,      PDO::PARAM_STR);
    $stmt->bindValue(':precip_rolling',  $precipRolling, PDO::PARAM_STR);
    $stmt->bindValue(':precip_source',   $precipSource,  PDO::PARAM_STR);
    $stmt->bindValue(':gate_active',     $gateActive,    PDO::PARAM_INT);
    $stmt->bindValue(':raw_alert_level', $rawAlertLevel, PDO::PARAM_STR);
    $stmt->bindValue(':alert_level',     $alertLevel,    PDO::PARAM_STR);
    $stmt->execute();

    $predictionId = (int)$pdo->lastInsertId();

    if ($alertTransition === 'fired' || $alertTransition === 'cleared') {
        $sqlAlert = "INSERT INTO prediction_alerts_m6
                         (id_station, event_type, alert_level, timestamp,
                          consecutive_steps, precip_rolling)
                     VALUES
                         (:id_station, :event_type, :alert_level, :timestamp,
                          :consecutive_steps, :precip_rolling)";

        $stmtAlert = $pdo->prepare($sqlAlert);
        $stmtAlert->bindValue(':id_station',        $stationId,        PDO::PARAM_INT);
        $stmtAlert->bindValue(':event_type',         $alertTransition,  PDO::PARAM_STR);
        $stmtAlert->bindValue(':alert_level',        $alertLevel,       PDO::PARAM_STR);
        $stmtAlert->bindValue(':timestamp',          $timestamp,        PDO::PARAM_STR);
        $stmtAlert->bindValue(':consecutive_steps',  $consecutiveSteps, PDO::PARAM_INT);
        $stmtAlert->bindValue(':precip_rolling',     $precipRolling,    PDO::PARAM_STR);
        $stmtAlert->execute();
        $alertRowId = (int)$pdo->lastInsertId();

        error_log(sprintf(
            '[predictions_m6.php] M6 Alert transition: station=%d type=%s level=%s',
            $stationId, $alertTransition, $alertLevel
        ));

        $pdo->commit();

        try {
            sendM6Notifications(
                $pdo,
                $alertRowId,
                $stationId,
                $alertTransition,
                $alertLevel,
                $hPred30,
                $hPred60,
                $hPred90,
                $hPred120,
                $precipRolling,
                $precipSource,
                $timestamp,
                $chartB64
            );
        } catch (Exception $notifEx) {
            error_log('[predictions_m6.php] Notification error: ' . $notifEx->getMessage());
        }

        http_response_code(201);
        echo json_encode([
            'success'       => true,
            'prediction_id' => $predictionId,
            'station_id'    => $stationId,
            'timestamp'     => $timestamp,
        ]);
        exit();
    }

    $pdo->commit();

    http_response_code(201);
    echo json_encode([
        'success'       => true,
        'prediction_id' => $predictionId,
        'station_id'    => $stationId,
        'timestamp'     => $timestamp,
    ]);

} catch (PDOException $e) {
    if ($pdo->inTransaction()) {
        $pdo->rollBack();
    }
    error_log('[predictions_m6.php] DB error: ' . $e->getMessage());
    http_response_code(500);
    echo json_encode(['error' => 'Database error.']);
}
