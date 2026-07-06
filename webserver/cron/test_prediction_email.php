<?php
/**
 * @file test_prediction_email.php
 * @brief Manual test script for prediction alert email delivery (Issue #110).
 *
 * Sends a fake "fired" prediction alert email to verify:
 *   1. PHPMailer + Gmail SMTP works (alerta.ilha3d@gmail.com credentials).
 *   2. The DB contacts for a station are correctly configured.
 *   3. The HTML body with a chart image URL renders in the inbox.
 *
 * Usage (CLI via SSH — recommended):
 *   php test_prediction_email.php [recipient@example.com] [station_id]
 *
 * Usage (browser, with API key header):
 *   https://ilha3d.com/sapi/cron/test_prediction_email.php?to=you@example.com&station=1
 *
 * Access restricted to: CLI, localhost, or valid X-API-Key header.
 *
 * @author Alexandre Nuernberg
 */

// ── Access guard ──────────────────────────────────────────────────────────────
$isCli       = php_sapi_name() === 'cli';
$isLocalhost = ($_SERVER['REMOTE_ADDR'] ?? '') === '127.0.0.1';

if (!$isCli && !$isLocalhost) {
    $apiConfigPath = '/home/<HOSTINGER_USER>/private_configs/sapi/api_config.php';
    if (file_exists($apiConfigPath)) {
        require_once $apiConfigPath;
    }
    $providedKey = $_SERVER['HTTP_X_API_KEY'] ?? '';
    if (empty($providedKey) || !defined('PREDICT_API_KEY') || $providedKey !== PREDICT_API_KEY) {
        http_response_code(403);
        exit("Forbidden.\n");
    }
}

if (!$isCli) {
    header('Content-Type: text/plain; charset=utf-8');
}

// ── Bootstrap ─────────────────────────────────────────────────────────────────
// __DIR__ = /home/<HOSTINGER_USER>/cron/
// dirname(__DIR__) = /home/<HOSTINGER_USER>/
$dbConfigPath = '/home/<HOSTINGER_USER>/private_configs/sapi/db_config.php';

if (!file_exists($dbConfigPath)) {
    exit("ERROR: DB config not found at {$dbConfigPath}\n");
}

require_once $dbConfigPath;
require_once dirname(__DIR__) . '/public_html/sapi/email_helper.php';

// ── Inputs ────────────────────────────────────────────────────────────────────
$overrideTo      = $isCli ? ($argv[1] ?? null) : ($_GET['to'] ?? null);
$testStationId   = (int)($isCli ? ($argv[2] ?? 1) : ($_GET['station'] ?? 1));
$testFromName    = 'SAPI - Alerta Preditivo [TESTE]';

// ── Fake prediction data ──────────────────────────────────────────────────────
$stationName    = "Estação {$testStationId} [TESTE]";
$timestamp      = gmdate('Y-m-d\TH:i:s\Z');
$alertLevel     = 'atencao';
$hPred30        = 55.0;
$hPred60        = 62.5;
$hPred90        = 58.1;
$hPred120       = 51.3;
$precipRolling  = 12.4;
$precipSource   = 'station02';

// ── Build email body ──────────────────────────────────────────────────────────
$levelLabels = [
    'none'      => 'Normalizado',
    'atencao'   => 'ATENÇÃO',
    'alerta'    => 'ALERTA',
    'inundacao' => 'INUNDAÇÃO',
];
$levelLabel = $levelLabels[$alertLevel];
$precipStr  = number_format($precipRolling, 1) . ' mm (' . $precipSource . ')';

$textBody  = "[SAPI TESTE] Alerta Preditivo — {$levelLabel} — {$stationName}\n";
$textBody .= "Timestamp: {$timestamp}\n\n";
$textBody .= "Este é um e-mail de TESTE. Nenhum alerta real foi disparado.\n\n";
$textBody .= "Projeções de nível (fictícias):\n";
$textBody .= "  +30 min : " . number_format($hPred30,  1) . " cm\n";
$textBody .= "  +60 min : " . number_format($hPred60,  1) . " cm\n";
$textBody .= "  +90 min : " . number_format($hPred90,  1) . " cm\n";
$textBody .= " +120 min : " . number_format($hPred120, 1) . " cm\n\n";
$textBody .= "Precipitação (6h): {$precipStr}\n";

// Use the predictions page as the "chart" link (no actual chart in test mode)
$chartUrl = 'https://ilha3d.com/sapi/predictions.php';

$htmlBody  = '<div style="font-family:sans-serif;font-size:14px;line-height:1.6;">';
$htmlBody .= nl2br(htmlspecialchars($textBody));
$htmlBody .= '<p style="margin-top:16px;">'
           . '<a href="' . htmlspecialchars($chartUrl) . '" style="color:#1565C0;">'
           . 'Ver previsões no painel SAPI</a></p>';
$htmlBody .= '<hr style="margin-top:20px;">';
$htmlBody .= '<small style="color:#666;">Sistema SAPI — IFSC Florianópolis<br>';
$htmlBody .= 'Notificação de TESTE — pipeline preditivo M4 LightGBM.</small>';
$htmlBody .= '</div>';

$subject = "[SAPI TESTE] Alerta Preditivo — {$levelLabel} — {$stationName}";

// ── Connect to DB and fetch contacts ──────────────────────────────────────────
echo "=== SAPI Prediction Email Test (PHPMailer) ===\n";
echo "Station   : {$testStationId}\n";
echo "Timestamp : {$timestamp}\n\n";

try {
    $pdo  = getDatabaseConnection();
    $stmt = $pdo->prepare(
        'SELECT ac.email, ac.name
         FROM alert_contacts ac
         JOIN contact_stations cs ON cs.id_contact = ac.id
         WHERE cs.id_station = ?
           AND ac.enabled = 1
           AND ac.deleted_at IS NULL
           AND ac.email IS NOT NULL
           AND ac.email <> \'\''
    );
    $stmt->execute([$testStationId]);
    $contacts = $stmt->fetchAll();

    echo "DB contacts for station {$testStationId}: " . count($contacts) . "\n";
    foreach ($contacts as $c) {
        echo "  - {$c['name']} <{$c['email']}>\n";
    }
    echo "\n";
} catch (Exception $e) {
    echo "DB ERROR: " . $e->getMessage() . "\n";
    $contacts = [];
}

// ── Determine recipients ──────────────────────────────────────────────────────
if ($overrideTo !== null) {
    $recipients = [['email' => $overrideTo, 'name' => 'Override']];
    echo "Recipient overridden: {$overrideTo}\n\n";
} elseif (!empty($contacts)) {
    $recipients = $contacts;
    echo "Using DB contacts as recipients.\n\n";
} else {
    echo "No contacts found and no override given. Nothing to send.\n";
    echo "Add a contact at https://ilha3d.com/sapi/admin/contacts.php\n";
    exit(0);
}

// ── Send ──────────────────────────────────────────────────────────────────────
$sent = 0; $failed = 0;
foreach ($recipients as $r) {
    $ok = sendEmailViaSMTP($r['email'], $subject, $htmlBody, $testFromName);
    echo "  sendEmailViaSMTP() → {$r['email']} : " . ($ok ? 'OK' : 'FAILED') . "\n";
    $ok ? $sent++ : $failed++;
}

echo "\nResult: {$sent} sent, {$failed} failed.\n";
echo "Error log: /home/<HOSTINGER_USER>/public_html/sapi/error.log\n";
echo "(Check inbox + spam folder within 1-2 minutes)\n";
