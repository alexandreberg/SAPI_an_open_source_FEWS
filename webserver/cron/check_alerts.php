<?php
/**
 * @file check_alerts.php
 * @brief Alert state-machine cron job.
 *
 * Runs every minute via Hostinger crontab:
 *   * * * * * /usr/bin/php /home/<HOSTINGER_USER>/cron/check_alerts.php
 *
 * For each (station, variable) combination that has at least one enabled
 * alert rule, this script:
 *   1. Reads the latest measurement value from the database.
 *      - For 'precipitation_mm': sums the last 60 minutes (Station-02 logic).
 *      - For other variables: reads the single most-recent measurement.
 *   2. Evaluates all enabled rules to determine the current alert level
 *      (none / attention / alert / flood).
 *   3. Compares to the persisted state in alert_state.
 *   4. If the level has changed, sends notifications to all enabled contacts
 *      assigned to that station (email via PHPMailer, WhatsApp via CallMeBot).
 *   5. Writes an immutable entry to alert_log for each notification attempt.
 *   6. Updates alert_state with the new level and event_max_level.
 *
 * Credentials are loaded from the sapi.php credential file via functions.php.
 *
 * Email is sent via PHP native mail() — no SMTP library required.
 * The mail From address is defined by MAIL_FROM / MAIL_FROM_NAME below.
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

// ── Bootstrap ──────────────────────────────────────────────────────────
// Include shared DB helper (also loads the sapi.php credential file
// with DB constants).
require_once dirname(__DIR__) . '/public_html/sapi/functions.php';
require_once dirname(__DIR__) . '/public_html/sapi/email_helper.php';

// ── Email sender identity ──────────────────────────────────────────────
define('MAIL_FROM',      'alerta.ilha3d@gmail.com');
define('MAIL_FROM_NAME', 'SAPI - Alerta de Inundação');

// ── Level hierarchy ────────────────────────────────────────────────────
/** Ordered list of alert levels from least to most severe. */
const LEVEL_ORDER = ['none', 'attention', 'alert', 'flood'];

/**
 * @brief Returns the numeric rank of an alert level (higher = more severe).
 *
 * @param string $level  One of: none, attention, alert, flood.
 * @return int           Rank (0 = none … 3 = flood).
 */
function levelRank(string $level): int
{
    $rank = array_search($level, LEVEL_ORDER, true);
    return $rank === false ? 0 : (int)$rank;
}

// ── Allowed measurement variables (whitelist against SQL injection) ────
const ALLOWED_MEASUREMENT_VARS = [
    'level_cm', 'precipitation_mm', 'temperature_C', 'surface_temperature_C',
    'bat_voltage', 'panel_voltage', 'pressure', 'humidity_percentual',
];

// ── Database helper ────────────────────────────────────────────────────
$pdo = db();

// ── Station name cache ─────────────────────────────────────────────────
$stationNames = [];

/**
 * @brief Fetches the station name (cached).
 *
 * @param PDO $pdo         Database connection.
 * @param int $stationId   Station primary key.
 * @return string          Station name, or "Estação N" as fallback.
 */
function getStationName(PDO $pdo, int $stationId): string
{
    global $stationNames;
    if (!isset($stationNames[$stationId])) {
        $stmt = $pdo->prepare('SELECT name FROM stations WHERE id = ?');
        $stmt->execute([$stationId]);
        $row = $stmt->fetch();
        $stationNames[$stationId] = $row ? $row['name'] : "Estação $stationId";
    }
    return $stationNames[$stationId];
}

// ── Read current measurement value ─────────────────────────────────────
/**
 * @brief Reads the current value for a given station+variable.
 *
 * For 'precipitation_mm', returns the SUM over the last 60 minutes.
 *
 * For 'level_cm', uses the pre-computed level_delta_cm column when a recent
 * delta-filtered value is available (populated by cron/filter_level.php).
 * This rejects spurious HC-SR04/US-100 echoes (readings changing faster than
 * physically possible) with zero added lag — unlike level_kalman_cm, which
 * had 10-25 min of lag at flood peaks and would delay alert triggers by the
 * same amount (Issue #63). Falls back to raw level_cm if no filtered value
 * has been computed yet (e.g., before the first filter_level.php run).
 *
 * NOTE: level_kalman_cm was retired entirely on 2026-08-20 (UI + cron no
 * longer write it) — it is kept only as a historical column. This function
 * already preferred level_delta_cm since Issue #63 (2026-03-23 / 2026-08-13),
 * so the retirement does not change alert behavior.
 *
 * For all other variables, returns the most-recent non-NULL raw reading.
 *
 * @param PDO    $pdo        Database connection.
 * @param int    $stationId  Station ID.
 * @param string $variable   Column name in the measurements table.
 * @return float|null        Current value, or null if no data available.
 */
function getCurrentValue(PDO $pdo, int $stationId, string $variable): ?float
{
    if (!in_array($variable, ALLOWED_MEASUREMENT_VARS, true)) {
        error_log("check_alerts: unknown variable '$variable', skipping.");
        return null;
    }

    if ($variable === 'precipitation_mm') {
        // Accumulate last 60 minutes for the rain gauge station
        $stmt = $pdo->prepare(
            "SELECT COALESCE(SUM(precipitation_mm), 0) AS val
             FROM measurements
             WHERE id_station = ?
               AND deleted_at IS NULL
               AND timestamp >= DATE_SUB(NOW(), INTERVAL 60 MINUTE)"
        );
        $stmt->execute([$stationId]);
        $row = $stmt->fetch();
        return ($row && $row['val'] !== null) ? (float)$row['val'] : null;
    }

    if ($variable === 'level_cm') {
        // Prefer the delta-filtered value (Issue #63) to avoid false alerts
        // from spurious ultrasonic echoes, without the lag level_kalman_cm
        // would introduce at the alert trigger.
        // "Recent" = within the last 10 minutes (2× the cron interval of 5 min).
        $stmt = $pdo->prepare(
            "SELECT level_delta_cm AS val
             FROM measurements
             WHERE id_station     = ?
               AND deleted_at     IS NULL
               AND level_delta_cm IS NOT NULL
               AND timestamp      >= DATE_SUB(NOW(), INTERVAL 10 MINUTE)
             ORDER BY timestamp DESC
             LIMIT 1"
        );
        $stmt->execute([$stationId]);
        $row = $stmt->fetch();

        if ($row && $row['val'] !== null) {
            return (float)$row['val']; // Delta-filtered value
        }

        // Fallback: raw level_cm (cron not yet run, or too old)
        $stmt = $pdo->prepare(
            "SELECT level_cm AS val
             FROM measurements
             WHERE id_station = ?
               AND deleted_at IS NULL
               AND level_cm   IS NOT NULL
             ORDER BY timestamp DESC
             LIMIT 1"
        );
        $stmt->execute([$stationId]);
        $row = $stmt->fetch();
        return ($row && $row['val'] !== null) ? (float)$row['val'] : null;
    }

    // All other variables: latest single raw reading
    $stmt = $pdo->prepare(
        "SELECT `$variable` AS val
         FROM measurements
         WHERE id_station = ?
           AND deleted_at IS NULL
           AND `$variable` IS NOT NULL
         ORDER BY timestamp DESC
         LIMIT 1"
    );
    $stmt->execute([$stationId]);
    $row = $stmt->fetch();

    return ($row && $row['val'] !== null) ? (float)$row['val'] : null;
}

// ── Evaluate rules ─────────────────────────────────────────────────────
/**
 * @brief Determines the highest alert level triggered by the current value.
 *
 * Tests all enabled rules for the given station+variable.
 * Returns the level with the highest severity whose condition is met.
 *
 * @param float $value   Current measurement value.
 * @param array $rules   Rows from alert_rules for this station+variable.
 * @return string        Alert level: 'none' | 'attention' | 'alert' | 'flood'.
 */
function determineLevel(float $value, array $rules): string
{
    $highest = 'none';

    foreach ($rules as $rule) {
        if (!$rule['enabled']) {
            continue;
        }

        $passes = match($rule['operator']) {
            '>='    => $value >= (float)$rule['threshold'],
            '>'     => $value >  (float)$rule['threshold'],
            '<='    => $value <= (float)$rule['threshold'],
            '<'     => $value <  (float)$rule['threshold'],
            default => false,
        };

        if ($passes && levelRank($rule['level']) > levelRank($highest)) {
            $highest = $rule['level'];
        }
    }

    return $highest;
}

// ── State helpers ──────────────────────────────────────────────────────
/**
 * @brief Reads (or creates) the alert_state row for a station+variable.
 *
 * @param PDO    $pdo       Database connection.
 * @param int    $stationId Station ID.
 * @param string $variable  Variable name.
 * @return array            alert_state row as associative array.
 */
function getState(PDO $pdo, int $stationId, string $variable): array
{
    $stmt = $pdo->prepare(
        'SELECT * FROM alert_state WHERE id_station = ? AND variable = ?'
    );
    $stmt->execute([$stationId, $variable]);
    $row = $stmt->fetch();

    if (!$row) {
        // Auto-create missing state row
        $pdo->prepare(
            'INSERT IGNORE INTO alert_state (id_station, variable) VALUES (?,?)'
        )->execute([$stationId, $variable]);
        return [
            'id_station'       => $stationId,
            'variable'         => $variable,
            'current_level'    => 'none',
            'entered_at'       => null,
            'last_alert_sent_at' => null,
            'event_max_level'  => 'none',
        ];
    }

    return $row;
}

/**
 * @brief Persists the updated alert state.
 *
 * @param PDO    $pdo          Database connection.
 * @param int    $stationId    Station ID.
 * @param string $variable     Variable name.
 * @param string $newLevel     New current alert level.
 * @param string $newMaxLevel  New event_max_level (highest level in this event).
 * @return void
 */
function updateState(
    PDO    $pdo,
    int    $stationId,
    string $variable,
    string $newLevel,
    string $newMaxLevel
): void {
    // PHP-side branch avoids string literal comparison in SQL,
    // which would trigger collation mismatch errors on MariaDB.
    if ($newLevel === 'none') {
        // Event ended: clear entered_at
        $pdo->prepare(
            'UPDATE alert_state
             SET current_level     = ?,
                 event_max_level   = ?,
                 last_alert_sent_at = NOW(),
                 entered_at        = NULL
             WHERE id_station = ? AND variable = ?'
        )->execute([$newLevel, $newMaxLevel, $stationId, $variable]);
    } else {
        // Active alert: preserve entered_at from first escalation
        $pdo->prepare(
            'UPDATE alert_state
             SET current_level     = ?,
                 event_max_level   = ?,
                 last_alert_sent_at = NOW(),
                 entered_at        = COALESCE(entered_at, NOW())
             WHERE id_station = ? AND variable = ?'
        )->execute([$newLevel, $newMaxLevel, $stationId, $variable]);
    }
}

// ── Notification helpers ───────────────────────────────────────────────
/**
 * @brief Builds a plain-text notification message.
 *
 * @param string      $stationName  Human-readable station name.
 * @param string      $variable     Measurement variable.
 * @param string      $level        Alert level.
 * @param string      $eventType    One of: escalation, de-escalation, normalized, summary.
 * @param float|null  $value        Measured value at trigger time.
 * @param string      $maxLevel     Highest level reached in event (for summary).
 * @return string                   Notification message text.
 */
function buildMessage(
    string $stationName,
    string $variable,
    string $level,
    string $eventType,
    ?float $value,
    string $maxLevel = 'none'
): string {
    $levelLabels = [
        'none'      => 'Normalizado',
        'attention' => 'ATENÇÃO',
        'alert'     => 'ALERTA',
        'flood'     => 'INUNDAÇÃO',
    ];
    $varLabels = [
        'level_cm'         => 'Nível',
        'precipitation_mm' => 'Precipitação (60 min)',
    ];

    $stationLabel = $stationName;
    $varLabel     = $varLabels[$variable] ?? $variable;
    $levelLabel   = $levelLabels[$level]  ?? strtoupper($level);
    $unit         = ($variable === 'precipitation_mm') ? 'mm' : 'cm';
    $valueStr     = $value !== null ? round($value, 1) . ' ' . $unit : 'N/D';

    return match($eventType) {
        'escalation'    =>
            "[SAPI] {$levelLabel} — {$stationLabel}\n" .
            "{$varLabel}: {$valueStr}\n" .
            "Nível de alerta atingido: {$levelLabel}.",

        'de-escalation' =>
            "[SAPI] Retornando para {$levelLabel} — {$stationLabel}\n" .
            "{$varLabel}: {$valueStr}.",

        'normalized'    =>
            "[SAPI] Normalizado — {$stationLabel}\n" .
            "{$varLabel}: {$valueStr}\nSituação normalizada.",

        'summary'       =>
            "[SAPI] Resumo do evento — {$stationLabel}\n" .
            "Nível máximo atingido: " . ($levelLabels[$maxLevel] ?? $maxLevel) . ".\n" .
            "Situação atual: Normalizado.",

        default => "[SAPI] Alerta — {$stationLabel}: {$valueStr}",
    };
}

/**
 * @brief Sends an alert email via Gmail SMTP (PHPMailer).
 *
 * @param string $to       Recipient e-mail address.
 * @param string $subject  E-mail subject line.
 * @param string $body     Plain-text body (wrapped in simple HTML).
 * @return bool            True on success, false on failure.
 */
function sendEmail(string $to, string $subject, string $body): bool
{
    $htmlBody  = '<div style="font-family:sans-serif;font-size:14px;line-height:1.6;">';
    $htmlBody .= nl2br(htmlspecialchars($body));
    $htmlBody .= '<p style="margin-top:16px;">'
               . '<a href="https://ilha3d.com/sapi/" style="color:#1565C0;">'
               . 'Painel SAPI</a></p>';
    $htmlBody .= '<hr style="margin-top:20px;">';
    $htmlBody .= '<small style="color:#666;">Sistema SAPI — IFSC Florianópolis</small>';
    $htmlBody .= '</div>';

    $ok = sendEmailViaSMTP($to, $subject, $htmlBody, MAIL_FROM_NAME);
    if (!$ok) {
        error_log("check_alerts: sendEmailViaSMTP() failed sending to $to");
    }
    return $ok;
}

/**
 * @brief Sends a WhatsApp notification via the CallMeBot API.
 *
 * @param string $phone   Recipient phone number in E.164 format (+55...).
 * @param string $apiKey  CallMeBot API key obtained during opt-in.
 * @param string $message Plain-text message (max ~4000 chars).
 * @return bool           True if HTTP request succeeded, false otherwise.
 */
function sendWhatsApp(string $phone, string $apiKey, string $message): bool
{
    $url = 'https://api.callmebot.com/whatsapp.php?' . http_build_query([
        'phone'  => $phone,
        'text'   => $message,
        'apikey' => $apiKey,
    ]);

    $context = stream_context_create([
        'http' => [
            'method'  => 'GET',
            'timeout' => 20,
            // Minimal user-agent to avoid being blocked
            'header'  => "User-Agent: SAPI-AlertBot/1.0\r\n",
        ],
    ]);

    $result = @file_get_contents($url, false, $context);
    if ($result === false) {
        error_log("check_alerts: WhatsApp send failed for phone $phone");
        return false;
    }
    return true;
}

/**
 * @brief Writes one row to alert_log for each notification attempt.
 *
 * @param PDO         $pdo        Database connection.
 * @param int         $stationId  Station ID.
 * @param string      $variable   Variable name.
 * @param string      $level      Alert level.
 * @param string      $eventType  Notification event type.
 * @param float|null  $value      Measurement value at trigger.
 * @param int         $contactId  Contact ID.
 * @param string      $channel    'email' or 'whatsapp'.
 * @param bool        $success    Whether the send succeeded.
 * @return void
 */
function logAlert(
    PDO    $pdo,
    int    $stationId,
    string $variable,
    string $level,
    string $eventType,
    ?float $value,
    int    $contactId,
    string $channel,
    bool   $success
): void {
    $pdo->prepare(
        'INSERT INTO alert_log
             (id_station, variable, level, event_type, value_at_trigger,
              id_contact, channel, status)
         VALUES (?,?,?,?,?,?,?,?)'
    )->execute([
        $stationId,
        $variable,
        $level,
        $eventType,
        $value,
        $contactId,
        $channel,
        $success ? 'sent' : 'failed',
    ]);
}

/**
 * @brief Dispatches a notification to a single contact via all configured channels.
 *
 * @param PDO         $pdo        Database connection.
 * @param array       $contact    Row from alert_contacts.
 * @param int         $stationId  Station ID.
 * @param string      $variable   Variable name.
 * @param string      $level      Alert level.
 * @param string      $eventType  Event type.
 * @param float|null  $value      Measurement value at trigger.
 * @param string      $maxLevel   Highest level in this event (for summary).
 * @return void
 */
function sendAlert(
    PDO    $pdo,
    array  $contact,
    int    $stationId,
    string $variable,
    string $level,
    string $eventType,
    ?float $value,
    string $maxLevel = 'none'
): void {
    $stationName = getStationName($pdo, $stationId);
    $message     = buildMessage($stationName, $variable, $level, $eventType, $value, $maxLevel);
    $subject     = "[SAPI] " . strtoupper($level) . " — " . $stationName;

    if ($eventType === 'normalized' || $eventType === 'summary') {
        $subject = "[SAPI] Normalizado — " . $stationName;
    }

    // Email channel
    if (!empty($contact['email'])) {
        $ok = sendEmail($contact['email'], $subject, $message);
        logAlert($pdo, $stationId, $variable, $level, $eventType, $value,
                 (int)$contact['id'], 'email', $ok);
    }

    // WhatsApp channel
    if (!empty($contact['whatsapp_number']) && !empty($contact['whatsapp_apikey'])) {
        $ok = sendWhatsApp(
            $contact['whatsapp_number'],
            $contact['whatsapp_apikey'],
            $message
        );
        logAlert($pdo, $stationId, $variable, $level, $eventType, $value,
                 (int)$contact['id'], 'whatsapp', $ok);
    }
}

// ── Main loop ─────────────────────────────────────────────────────────
/**
 * @brief Fetches all distinct (station, variable) pairs that have enabled rules.
 *
 * @param PDO $pdo  Database connection.
 * @return array    List of associative arrays with 'id_station' and 'variable'.
 */
function getActiveGroups(PDO $pdo): array
{
    return $pdo->query(
        'SELECT DISTINCT ar.id_station, ar.variable
         FROM alert_rules ar
         JOIN stations s ON s.id = ar.id_station AND s.deleted_at IS NULL
         WHERE ar.enabled = 1 AND ar.deleted_at IS NULL'
    )->fetchAll();
}

$groups = getActiveGroups($pdo);

foreach ($groups as $group) {
    $stationId = (int)$group['id_station'];
    $variable  = $group['variable'];

    // 1. Get current measurement value
    $currentValue = getCurrentValue($pdo, $stationId, $variable);
    if ($currentValue === null) {
        // No data available for this station/variable — skip
        continue;
    }

    // 2. Load all enabled rules for this group
    $rulesStmt = $pdo->prepare(
        'SELECT level, operator, threshold, enabled
         FROM alert_rules
         WHERE id_station = ? AND variable = ? AND deleted_at IS NULL'
    );
    $rulesStmt->execute([$stationId, $variable]);
    $rules = $rulesStmt->fetchAll();

    // 3. Determine new alert level
    $newLevel = determineLevel($currentValue, $rules);

    // 4. Get persisted state
    $state        = getState($pdo, $stationId, $variable);
    $currentLevel = $state['current_level'];

    // 5. No change — nothing to do
    if ($newLevel === $currentLevel) {
        continue;
    }

    // 6. Determine event type
    if (levelRank($newLevel) > levelRank($currentLevel)) {
        $eventType = 'escalation';
    } elseif ($newLevel === 'none') {
        $eventType = 'normalized';
    } else {
        $eventType = 'de-escalation';
    }

    // 7. Calculate new event_max_level
    $currentMaxLevel = $state['event_max_level'] ?? 'none';
    if ($eventType === 'escalation' &&
        levelRank($newLevel) > levelRank($currentMaxLevel)) {
        $newMaxLevel = $newLevel;
    } elseif ($eventType === 'normalized') {
        $newMaxLevel = 'none'; // reset after event ends
    } else {
        $newMaxLevel = $currentMaxLevel;
    }

    // 8. Fetch contacts assigned to this station
    $contactsStmt = $pdo->prepare(
        'SELECT ac.*
         FROM alert_contacts ac
         JOIN contact_stations cs ON cs.id_contact = ac.id
         WHERE cs.id_station = ? AND ac.enabled = 1 AND ac.deleted_at IS NULL'
    );
    $contactsStmt->execute([$stationId]);
    $contacts = $contactsStmt->fetchAll();

    // 9. Send notifications
    foreach ($contacts as $contact) {
        sendAlert($pdo, $contact, $stationId, $variable,
                  $newLevel, $eventType, $currentValue, $currentMaxLevel);

        // After 'normalized', also send the event summary
        if ($eventType === 'normalized') {
            sendAlert($pdo, $contact, $stationId, $variable,
                      $newLevel, 'summary', $currentValue, $currentMaxLevel);
        }
    }

    // 10. Persist updated state
    updateState($pdo, $stationId, $variable, $newLevel, $newMaxLevel);
}
