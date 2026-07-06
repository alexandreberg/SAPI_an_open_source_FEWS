<?php
/**
 * @file filter_level.php
 * @brief Cron script — applies delta filter + Kalman smoother to level_cm.
 *
 * Runs every 5 minutes via Hostinger cPanel → Advanced → Cron Jobs:
 *   * /5 * * * *  /usr/bin/php /home/<HOSTINGER_USER>/cron/filter_level.php
 *
 * IMPORTANT — first run (initial backfill):
 *   Run manually via Hostinger SSH terminal BEFORE activating the cron job:
 *     php /home/<HOSTINGER_USER>/cron/filter_level.php
 *   This processes all historical rows (may take several minutes for
 *   Station-01 with months of 1-min data). Subsequent cron runs are fast
 *   because only new rows are processed.
 *
 * Concurrent execution protection:
 *   A file lock (/home/<HOSTINGER_USER>/tmp/filter_level.lock) prevents a second
 *   instance from starting if a previous run is still active. The lock is
 *   released automatically when the script exits (even on error).
 *
 * Pipeline per unprocessed row:
 *   1. Hard physical limit check (0–500 cm) — rejects firmware crash values.
 *   2. Delta (rate-of-change) filter — rejects physically impossible transients.
 *      Threshold scales with elapsed time: maxDelta × elapsed_minutes.
 *   3. 1-D Kalman smoother applied to accepted readings only.
 *
 * Output columns written to measurements:
 *   level_delta_cm  — level_cm value if accepted by both filters, NULL if rejected.
 *   level_kalman_cm — Kalman-smoothed estimate, NULL if row was rejected.
 *
 * Incremental processing: only rows where level_delta_cm IS NULL AND
 * level_cm IS NOT NULL are processed. On first run this backfills all history.
 *
 * Station parameters are hardcoded here (Issue #59 tracks moving them to the
 * admin UI / station_filter_config DB table).
 *
 * @author Alexandre Nuernberg
 */

// ── Bootstrap ────────────────────────────────────────────────────────────────
require_once dirname(__DIR__) . '/public_html/sapi/functions.php';

// ── Concurrent execution lock ─────────────────────────────────────────────────
/**
 * Prevents two cron instances from running simultaneously.
 * Uses a non-blocking exclusive flock — if the lock cannot be acquired the
 * previous run is still active and this instance exits immediately.
 *
 * The lock file is kept in /home/<HOSTINGER_USER>/tmp/ (create this directory on
 * Hostinger if it does not exist, or change the path to any writable location).
 */
$lockPath = '/home/<HOSTINGER_USER>/tmp/filter_level.lock';
$lockFp   = fopen($lockPath, 'w');

if ($lockFp === false) {
    error_log('filter_level: cannot open lock file ' . $lockPath . ' — aborting.');
    exit(1);
}

if (!flock($lockFp, LOCK_EX | LOCK_NB)) {
    // Another instance is already running — exit silently
    error_log('filter_level: already running (lock held), skipping this run.');
    fclose($lockFp);
    exit(0);
}

// Lock acquired — register a shutdown handler to always release it
register_shutdown_function(function () use ($lockFp) {
    flock($lockFp, LOCK_UN);
    fclose($lockFp);
});

$pdo = db();

// ── Per-station filter configuration ─────────────────────────────────────────
/**
 * @var array<int, array{
 *   levelZero: float,
 *   maxSensorRange: float,
 *   hardMin: float,
 *   hardMax: float,
 *   maxDelta: float,
 *   kalmanQ: float,
 *   kalmanR: float
 * }>
 *
 * levelZero      — sensor mounting reference (levelZero − distance_raw = level_cm).
 *                  Station-01: calibrated 2025-12-30. Station-03: calibrated 2026-03-01.
 * maxSensorRange — physical max range of ultrasonic sensor (cm).
 * hardMin/Max    — absolute physical limits (same as $varLimits in view.php).
 * maxDelta       — maximum plausible level change per minute (cm/min).
 *                  Calibrated from real flood events (2025-2026 historical data):
 *                  fastest observed rise ~2 cm/min; 5 cm/min gives a safe margin
 *                  while firmly rejecting sensor slow-drift (~13-15 cm/min equivalent).
 * kalmanQ        — process noise (lower = smoother, slower to react to real changes).
 * kalmanR        — measurement noise (higher = heavier smoothing on accepted readings).
 */
const STATION_CONFIG = [
    1 => [
        'levelZero'      => 291.0,
        'maxSensorRange' => 450.0,
        'hardMin'        => 0.0,
        'hardMax'        => 500.0,
        'maxDelta'       => 5.0,
        'kalmanQ'        => 1.0,
        'kalmanR'        => 200.0,
    ],
    3 => [
        'levelZero'      => 236.0,
        'maxSensorRange' => 300.0,
        'hardMin'        => 0.0,
        'hardMax'        => 500.0,
        'maxDelta'       => 5.0,
        'kalmanQ'        => 1.0,
        'kalmanR'        => 200.0,
    ],
];

// ── Kalman filter (1-D scalar) ────────────────────────────────────────────────
/**
 * @brief Applies a 1-D Kalman filter to a single new observation,
 *        updating the filter state in place.
 *
 * The filter state ($x, $P) must be seeded before the first call and
 * carried across iterations (passed by reference).
 *
 * Kalman equations (scalar):
 *   Predict:  P⁻ = P + Q
 *   Gain:     K  = P⁻ / (P⁻ + R)
 *   Update:   x  = x + K * (z − x)
 *             P  = (1 − K) * P⁻
 *
 * @param float  $z  New observation (accepted level_cm value).
 * @param float &$x  Current state estimate (updated in place).
 * @param float &$P  Current error covariance (updated in place).
 * @param float  $Q  Process noise variance.
 * @param float  $R  Measurement noise variance.
 * @return float     Filtered estimate.
 */
function kalmanUpdate(float $z, float &$x, float &$P, float $Q, float $R): float
{
    $Pp = $P + $Q;              // predicted covariance
    $K  = $Pp / ($Pp + $R);     // Kalman gain
    $x  = $x + $K * ($z - $x); // state update
    $P  = (1.0 - $K) * $Pp;    // covariance update
    return $x;
}

// ── Per-station processing ────────────────────────────────────────────────────
/**
 * @brief Fetches unprocessed rows for a station, ordered by timestamp ASC.
 *
 * "Unprocessed" = level_cm IS NOT NULL AND level_delta_cm IS NULL AND
 *                 deleted_at IS NULL AND timestamp <= NOW()
 * The timestamp <= NOW() guard prevents processing rows with future timestamps
 * (e.g. Station-01 32-bit overflow bug producing year 2106).
 *
 * @param PDO $pdo        Database connection.
 * @param int $stationId  Station primary key.
 * @return array          Rows as associative arrays: id, timestamp, level_cm.
 */
function fetchUnprocessed(PDO $pdo, int $stationId): array
{
    $stmt = $pdo->prepare(
        "SELECT id, timestamp, level_cm, flag
         FROM measurements
         WHERE id_station    = :sid
           AND level_cm      IS NOT NULL
           AND level_delta_cm IS NULL
           AND deleted_at    IS NULL
           AND timestamp     <= NOW()
         ORDER BY timestamp ASC"
    );
    $stmt->execute([':sid' => $stationId]);
    return $stmt->fetchAll(PDO::FETCH_ASSOC);
}

/**
 * @brief Fetches the Kalman state from the last accepted (non-NULL) processed row.
 *
 * Used to seed the Kalman filter when resuming incremental processing,
 * so the filter memory is not lost between cron runs.
 *
 * Returns null if no previously processed row exists (first run).
 *
 * @param PDO $pdo        Database connection.
 * @param int $stationId  Station primary key.
 * @return array|null     Associative array with 'level_delta_cm' and
 *                        'level_kalman_cm', or null.
 */
function fetchLastAccepted(PDO $pdo, int $stationId): ?array
{
    $stmt = $pdo->prepare(
        "SELECT timestamp, level_delta_cm, level_kalman_cm
         FROM measurements
         WHERE id_station     = :sid
           AND level_delta_cm IS NOT NULL
           AND deleted_at     IS NULL
         ORDER BY timestamp DESC
         LIMIT 1"
    );
    $stmt->execute([':sid' => $stationId]);
    $row = $stmt->fetch(PDO::FETCH_ASSOC);
    return $row ?: null;
}

/**
 * @brief Writes level_delta_cm and level_kalman_cm back to a measurements row.
 *
 * @param PDO        $pdo     Database connection.
 * @param int        $id      measurements.id primary key.
 * @param float|null $delta   Accepted level value, or null if rejected.
 * @param float|null $kalman  Kalman estimate, or null if rejected.
 * @return void
 */
function writeFiltered(PDO $pdo, int $id, ?float $delta, ?float $kalman): void
{
    $stmt = $pdo->prepare(
        "UPDATE measurements
         SET level_delta_cm  = :delta,
             level_kalman_cm = :kalman
         WHERE id = :id"
    );
    $stmt->execute([
        ':delta'  => $delta,
        ':kalman' => $kalman,
        ':id'     => $id,
    ]);
}

// ── Main ─────────────────────────────────────────────────────────────────────
foreach (STATION_CONFIG as $stationId => $cfg) {

    $rows = fetchUnprocessed($pdo, $stationId);

    if (empty($rows)) {
        continue; // nothing to process for this station
    }

    // ── Seed filter state ──────────────────────────────────────────────────
    // Try to resume from the last accepted row so the Kalman state is preserved
    // across incremental runs.
    $lastAccepted = fetchLastAccepted($pdo, $stationId);

    if ($lastAccepted !== null) {
        // Resume: seed from last accepted delta value and Kalman estimate
        $lastValidValue     = (float)$lastAccepted['level_delta_cm'];
        $lastValidTimestamp = new DateTime($lastAccepted['timestamp']);
        $kalmanX            = (float)$lastAccepted['level_kalman_cm'];
        $kalmanP            = 1.0; // restart covariance — conservative but correct
    } else {
        // First run: seed from the first valid raw reading in the batch
        $seeded = false;
        foreach ($rows as $row) {
            $v = (float)$row['level_cm'];
            if ($v >= $cfg['hardMin'] && $v <= $cfg['hardMax']) {
                $lastValidValue     = $v;
                $lastValidTimestamp = new DateTime($row['timestamp']);
                $kalmanX            = $v;
                $kalmanP            = 1.0;
                $seeded = true;
                break;
            }
        }
        if (!$seeded) {
            // All rows in batch fail hard limits — mark all as processed with NULLs
            // Use 0.0 as sentinel to mark "processed but rejected at hard limit stage"
            // (level_delta_cm = NULL signals rejection; we need a non-NULL to mark
            // the row as processed and not re-evaluated every run).
            // Solution: write a special marker by setting level_delta_cm = -1
            // (outside valid physical range) so the row is skipped next run.
            // Actually, the cleanest solution: write 0.0 in level_delta_cm as a
            // "processed-rejected" marker ONLY when all rows fail. But this is an
            // edge case (entire batch outside 0–500) that should not happen in practice.
            // For safety, log and skip — these rows will be retried next run.
            error_log("filter_level: Station $stationId — no valid seed row found in batch, skipping.");
            continue;
        }
    }

    // ── Process each unprocessed row ──────────────────────────────────────
    $accepted = 0;
    $rejected = 0;
    $flagged  = 0;

    foreach ($rows as $row) {
        $id    = (int)$row['id'];
        $v     = (float)$row['level_cm'];
        $rowTs = new DateTime($row['timestamp']);

        // 0. Manual bad-data flag (flag = 'b' set via admin/phpMyAdmin).
        //    Treat as an invalid gap: write NULL/NULL but do NOT advance
        //    lastValid — the flagged period does not contaminate the seed.
        if (($row['flag'] ?? null) === 'b') {
            writeFiltered($pdo, $id, null, null);
            $flagged++;
            continue;
        }

        // 1. Hard physical limit check (catches SMALLINT_MAX crash values)
        if ($v < $cfg['hardMin'] || $v > $cfg['hardMax']) {
            writeFiltered($pdo, $id, null, null);
            $rejected++;
            // Do not update lastValidTimestamp — the gap continues
            continue;
        }

        // 2. Delta (rate-of-change) filter
        //    Elapsed time in minutes since last accepted reading
        $elapsedMin = ($rowTs->getTimestamp() - $lastValidTimestamp->getTimestamp()) / 60.0;

        // Guard against non-monotonic timestamps (duplicate or out-of-order rows)
        if ($elapsedMin <= 0) {
            writeFiltered($pdo, $id, null, null);
            $rejected++;
            continue;
        }

        $maxAllowedDelta = $cfg['maxDelta'] * $elapsedMin;

        if (abs($v - $lastValidValue) > $maxAllowedDelta) {
            // Physically impossible rate of change — spurious echo or firmware glitch
            writeFiltered($pdo, $id, null, null);
            $rejected++;
            // Gap grows; threshold scales with elapsed time automatically next iteration
            continue;
        }

        // 3. Row accepted — apply Kalman smoother
        $kalmanEstimate = kalmanUpdate($v, $kalmanX, $kalmanP, $cfg['kalmanQ'], $cfg['kalmanR']);

        writeFiltered($pdo, $id, $v, round($kalmanEstimate, 2));

        // Advance state
        $lastValidValue     = $v;
        $lastValidTimestamp = $rowTs;
        $accepted++;
    }

    error_log(sprintf(
        "filter_level: Station %d — processed %d rows (%d accepted, %d rejected, %d flagged).",
        $stationId,
        count($rows),
        $accepted,
        $rejected,
        $flagged
    ));
}
