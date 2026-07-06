<?php
/**
 * @file predictions.php
 * @brief Public prediction dashboard — M4 LightGBM & M6 MLR real-time forecasts
 *        (Issues #108, #120).
 *
 * Shows for each active station (01 and 03):
 *  - Last 3 hours of observed level (level_delta_cm)
 *  - M4 LightGBM prediction cone (purple dashed)
 *  - M6 MLR prediction cone (deep orange dashed) — overlaid on the same chart
 *  - Alert threshold lines (Atenção / Alerta / Inundação)
 *  - Gate status badges and precipitation rolling sum for both models
 *  - Recent prediction_alerts + prediction_alerts_m6 merged table
 *
 * Data is loaded server-side; the page auto-refreshes every 5 minutes to stay
 * aligned with the cron interval.
 *
 * @author Alexandre Nuernberg
 */

require_once 'header.php';
$pdo = db();

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

/** @var array Stations to display with their threshold annotations (cm). */
$stations = [
    1 => [
        'name'      => 'Estação 01 — Nível',
        'atencao'   => 50,
        'alerta'    => 60,
        'inundacao' => 75,
    ],
    3 => [
        'name'      => 'Estação 03 — Nível',
        'atencao'   => 50,
        'alerta'    => 60,
        'inundacao' => 75,
    ],
];

$historyHours  = 3;
$maxAlertRows  = 20;

// ---------------------------------------------------------------------------
// Data loading helpers
// ---------------------------------------------------------------------------

/**
 * @brief Fetch recent observed level history for one station.
 *
 * @param PDO $pdo         Database connection.
 * @param int $stationId   Station identifier.
 * @param int $hours       Lookback window in hours.
 * @return array           Rows with keys 'ts' (string) and 'level' (float|null).
 */
function fetchLevelHistory(PDO $pdo, int $stationId, int $hours): array {
    $sql = "SELECT
                DATE_FORMAT(timestamp, '%Y-%m-%dT%H:%i:00Z') AS ts,
                ROUND(level_delta_cm, 2) AS level
            FROM measurements
            WHERE id_station = :sid
              AND timestamp >= UTC_TIMESTAMP() - INTERVAL :h HOUR
              AND level_delta_cm IS NOT NULL
            ORDER BY timestamp ASC";

    $stmt = $pdo->prepare($sql);
    $stmt->bindValue(':sid', $stationId, PDO::PARAM_INT);
    $stmt->bindValue(':h',   $hours,     PDO::PARAM_INT);
    $stmt->execute();
    return $stmt->fetchAll(PDO::FETCH_ASSOC);
}

/**
 * @brief Fetch the most recent prediction row for one station.
 *
 * @param PDO $pdo        Database connection.
 * @param int $stationId  Station identifier.
 * @return array|null     Prediction row or null if no predictions exist yet.
 */
function fetchLatestPrediction(PDO $pdo, int $stationId): ?array {
    $sql = "SELECT *
            FROM predictions
            WHERE id_station = :sid
            ORDER BY timestamp DESC
            LIMIT 1";

    $stmt = $pdo->prepare($sql);
    $stmt->bindValue(':sid', $stationId, PDO::PARAM_INT);
    $stmt->execute();
    $row = $stmt->fetch(PDO::FETCH_ASSOC);
    return $row ?: null;
}

/**
 * @brief Fetch the most recent prediction_m6 row for one station.
 *
 * @param PDO $pdo        Database connection.
 * @param int $stationId  Station identifier.
 * @return array|null     Prediction row or null if no M6 predictions exist yet.
 */
function fetchLatestPredictionM6(PDO $pdo, int $stationId): ?array {
    $sql = "SELECT *
            FROM predictions_m6
            WHERE id_station = :sid
            ORDER BY timestamp DESC
            LIMIT 1";

    $stmt = $pdo->prepare($sql);
    $stmt->bindValue(':sid', $stationId, PDO::PARAM_INT);
    $stmt->execute();
    $row = $stmt->fetch(PDO::FETCH_ASSOC);
    return $row ?: null;
}

/**
 * @brief Fetch the last N alert transitions from both M4 and M6, merged.
 *
 * Returns a unified list with a 'model' column ('M4' or 'M6'), ordered
 * newest-first so the most recent alert from either model appears first.
 *
 * @param PDO $pdo  Database connection.
 * @param int $n    Maximum rows to return.
 * @return array    Rows ordered newest-first.
 */
function fetchRecentAlerts(PDO $pdo, int $n): array {
    $sql = "SELECT
                pa.id,
                pa.id_station,
                pa.event_type,
                pa.alert_level,
                DATE_FORMAT(pa.timestamp, '%Y-%m-%d %H:%i:%S') AS ts,
                pa.consecutive_steps,
                pa.precip_rolling,
                'M4' AS model
            FROM prediction_alerts pa
            UNION ALL
            SELECT
                pm.id,
                pm.id_station,
                pm.event_type,
                pm.alert_level,
                DATE_FORMAT(pm.timestamp, '%Y-%m-%d %H:%i:%S') AS ts,
                pm.consecutive_steps,
                pm.precip_rolling,
                'M6' AS model
            FROM prediction_alerts_m6 pm
            ORDER BY ts DESC
            LIMIT :n";

    $stmt = $pdo->prepare($sql);
    $stmt->bindValue(':n', $n, PDO::PARAM_INT);
    $stmt->execute();
    return $stmt->fetchAll(PDO::FETCH_ASSOC);
}

// ---------------------------------------------------------------------------
// Load data for all stations
// ---------------------------------------------------------------------------

$stationData  = [];
$recentAlerts = [];

try {
    foreach ($stations as $sid => $cfg_s) {
        $stationData[$sid] = [
            'history'       => fetchLevelHistory($pdo, $sid, $historyHours),
            'prediction'    => fetchLatestPrediction($pdo, $sid),
            'prediction_m6' => fetchLatestPredictionM6($pdo, $sid),
        ];
    }
    $recentAlerts = fetchRecentAlerts($pdo, $maxAlertRows);
} catch (Throwable $e) {
    error_log('[predictions.php] DB error: ' . $e->getMessage());
}

// ---------------------------------------------------------------------------
// Helpers: badge and colour
// ---------------------------------------------------------------------------

/**
 * @brief Return a Bootstrap badge class for an alert level.
 * @param string $level  Alert level string.
 * @return string        CSS class string.
 */
function alertBadgeClass(string $level): string {
    return match($level) {
        'inundacao' => 'bg-danger',
        'alerta'    => 'bg-warning text-dark',
        'atencao'   => 'bg-info text-dark',
        default     => 'bg-secondary',
    };
}

/**
 * @brief Return a human-readable label for an alert level.
 * @param string $level  Alert level string.
 * @return string        Portuguese label.
 */
function alertLabel(string $level): string {
    return match($level) {
        'inundacao' => 'Inundação',
        'alerta'    => 'Alerta',
        'atencao'   => 'Atenção',
        default     => 'Normal',
    };
}

?>

<!-- Mobile responsiveness (Issue #114) — revised fix.
     Root cause: Chart.js sets canvas style.width via inline style on every
     ResizeObserver tick, overriding max-width:100% and widening the page.
     Solution: wrap canvas in .chart-wrapper with a fixed height and
     overflow:hidden, then use maintainAspectRatio:false so Chart.js fills
     the wrapper without ever exceeding it.
     Card-header fix: flex-wrap + min-width:0 (standard flexbox shrink trick)
     replaces the previous display:block override which could break AdminLTE. -->
<style>
/* Chart wrapper — Chart.js fills this box exactly */
.predictions-card .chart-wrapper {
    position: relative;
    width: 100%;
    overflow: hidden;
    height: 200px;        /* mobile-first */
}
@media (min-width: 768px) {
    .predictions-card .chart-wrapper { height: 280px; }
}

/* Card header badge wrapping on narrow screens */
@media (max-width: 767.98px) {
    .predictions-card > .card-header          { flex-wrap: wrap !important; }
    .predictions-card > .card-header > div   { min-width: 0; width: 100%; }
}

/* Safety net: prevent any remaining overflow from scrolling the page */
@media (max-width: 991.98px) {
    .app-content { overflow-x: hidden; }
}
</style>

<!--begin::App Main-->
<main class="app-main">
  <div class="app-content-header">
    <div class="container-fluid">
      <div class="row">
        <div class="col-sm-6">
          <h3 class="mb-0">Previsões de Inundação — Bibliotecas DARTS: LightGBM &amp; MLR</h3>
        </div>
        <div class="col-sm-6">
          <small class="text-muted">Atualizado automaticamente a cada 5 minutos</small>
        </div>
      </div>
    </div>
  </div>

  <div class="app-content">
    <div class="container-fluid">

      <?php foreach ($stations as $sid => $cfg_s):
        $hist    = $stationData[$sid]['history']       ?? [];
        $pred    = $stationData[$sid]['prediction']    ?? null;
        $predM6  = $stationData[$sid]['prediction_m6'] ?? null;
        $chartId = "chart_station_{$sid}";
      ?>

      <!-- ================================================================== -->
      <!-- Station card                                                         -->
      <!-- ================================================================== -->
      <div class="card mb-4 predictions-card">
        <div class="card-header">
          <!-- w-100 keeps this div constrained to the card width even when
               AdminLTE makes .card-header a flex container. flex-wrap allows
               the metadata small to wrap to its own row via w-100. -->
          <div class="d-flex align-items-center flex-wrap gap-2 w-100">
            <h5 class="card-title mb-0">
              <?= htmlspecialchars($cfg_s['name']) ?>
            </h5>

            <!-- M4 badges -->
            <?php if ($pred): ?>
              <span class="badge bg-light text-dark border fw-semibold" style="font-size:0.7rem;">M4</span>
              <?php if ($pred['gate_active']): ?>
                <span class="badge bg-success" title="M4 Precipitação 6h: <?= round((float)$pred['precip_rolling'], 2) ?> mm — Dispara com ≥ 5 mm em 6h">
                  Gatilho ativo (<?= round((float)$pred['precip_rolling'], 2) ?> mm)
                </span>
              <?php else: ?>
                <span class="badge bg-secondary" title="M4 Precipitação 6h: <?= round((float)$pred['precip_rolling'], 2) ?> mm — Dispara com ≥ 5 mm em 6h">
                  Gatilho inativo (<?= round((float)$pred['precip_rolling'], 2) ?> mm)
                </span>
              <?php endif; ?>
              <span class="badge <?= alertBadgeClass($pred['alert_level']) ?>">
                <?= alertLabel($pred['alert_level']) ?>
              </span>
            <?php else: ?>
              <span class="badge bg-light text-dark border" style="font-size:0.7rem;">M4</span>
              <span class="badge bg-secondary">Sem predições</span>
            <?php endif; ?>

            <!-- M6 badges — separated by a thin vertical divider -->
            <span class="text-muted" style="font-size:0.85rem;">|</span>
            <?php if ($predM6): ?>
              <span class="badge bg-light text-dark border fw-semibold" style="font-size:0.7rem; color:#E65100 !important; border-color:#E65100 !important;">M6</span>
              <?php if ($predM6['gate_active']): ?>
                <span class="badge" style="background:#E65100;" title="M6 Precipitação 6h: <?= round((float)$predM6['precip_rolling'], 2) ?> mm — Dispara com ≥ 5 mm em 6h">
                  Gatilho ativo (<?= round((float)$predM6['precip_rolling'], 2) ?> mm)
                </span>
              <?php else: ?>
                <span class="badge bg-secondary" title="M6 Precipitação 6h: <?= round((float)$predM6['precip_rolling'], 2) ?> mm — Dispara com ≥ 5 mm em 6h">
                  Gatilho inativo (<?= round((float)$predM6['precip_rolling'], 2) ?> mm)
                </span>
              <?php endif; ?>
              <span class="badge <?= alertBadgeClass($predM6['alert_level']) ?>"
                    style="<?= $predM6['alert_level'] === 'none' ? 'opacity:0.7;' : '' ?>">
                <?= alertLabel($predM6['alert_level']) ?>
              </span>
            <?php else: ?>
              <span class="badge bg-light text-dark border" style="font-size:0.7rem;">M6</span>
              <span class="badge bg-secondary">Sem predições</span>
            <?php endif; ?>

            <!-- Threshold legend — pushed to the right.
                 Colors match the dashed annotation lines in the chart. -->
            <div class="ms-auto" style="font-size:0.72rem; line-height:1.7; white-space:nowrap;">
              <div class="d-flex align-items-center gap-1">
                <span style="display:inline-block; width:20px; border-top:2px dashed crimson;"></span>
                <span>Inundação <?= $cfg_s['inundacao'] ?> cm</span>
              </div>
              <div class="d-flex align-items-center gap-1">
                <span style="display:inline-block; width:20px; border-top:2px dashed darkorange;"></span>
                <span>Alerta <?= $cfg_s['alerta'] ?> cm</span>
              </div>
              <div class="d-flex align-items-center gap-1">
                <span style="display:inline-block; width:20px; border-top:2px dashed goldenrod;"></span>
                <span>Atenção <?= $cfg_s['atencao'] ?> cm</span>
              </div>
            </div>

            <!-- Metadata row -->
            <?php if ($pred || $predM6): ?>
            <small class="text-muted w-100 mt-1">
              <?php if ($pred): ?>
                M4 precip: <?= htmlspecialchars($pred['precip_source'] ?? '—') ?>
                &nbsp;|&nbsp;
                M4 última: <?= htmlspecialchars(substr($pred['timestamp'] ?? '—', 0, 16)) ?> UTC
              <?php endif; ?>
              <?php if ($pred && $predM6): ?> &nbsp;&nbsp; <?php endif; ?>
              <?php if ($predM6): ?>
                M6 última: <?= htmlspecialchars(substr($predM6['timestamp'] ?? '—', 0, 16)) ?> UTC
              <?php endif; ?>
              &nbsp;·&nbsp;
              <span title="O alerta preditivo é disparado somente quando a precipitação acumulada nas últimas 6 horas for ≥ 5 mm, mantida por 3 ciclos consecutivos (15 min).">
                Gatilho: precipitação ≥ 5 mm / 6h ⓘ
              </span>
            </small>
            <?php endif; ?>
          </div>
        </div>

        <div class="card-body">
          <div class="chart-wrapper">
            <canvas id="<?= $chartId ?>"></canvas>
          </div>
        </div>

        <?php if ($pred || $predM6): ?>
        <div class="card-footer p-2" style="font-size:0.85rem;">
          <!-- M4 row -->
          <?php if ($pred): ?>
          <div class="row text-center align-items-center g-1 <?= $predM6 ? 'mb-1' : '' ?>">
            <div class="col-2 text-start ps-2">
              <small class="fw-semibold" style="color:#8E24AA;">M4 LightGBM</small>
            </div>
            <?php foreach ([30 => 'h_pred_30', 60 => 'h_pred_60', 90 => 'h_pred_90', 120 => 'h_pred_120'] as $h => $col): ?>
            <div class="col">
              <small class="text-muted d-block">+<?= $h ?> min</small>
              <strong style="color:#8E24AA;"><?= $pred[$col] !== null ? round((float)$pred[$col], 1) . ' cm' : '—' ?></strong>
            </div>
            <?php endforeach; ?>
          </div>
          <?php endif; ?>
          <!-- M6 row -->
          <?php if ($predM6): ?>
          <div class="row text-center align-items-center g-1">
            <div class="col-2 text-start ps-2">
              <small class="fw-semibold" style="color:#E65100;">M6 MLR</small>
            </div>
            <?php foreach ([30 => 'h_pred_30', 60 => 'h_pred_60', 90 => 'h_pred_90', 120 => 'h_pred_120'] as $h => $col): ?>
            <div class="col">
              <small class="text-muted d-block">+<?= $h ?> min</small>
              <strong style="color:#E65100;"><?= $predM6[$col] !== null ? round((float)$predM6[$col], 1) . ' cm' : '—' ?></strong>
            </div>
            <?php endforeach; ?>
          </div>
          <?php endif; ?>
        </div>
        <?php endif; ?>
      </div>

      <?php endforeach; ?>

      <!-- ================================================================== -->
      <!-- Recent prediction alerts table                                       -->
      <!-- ================================================================== -->
      <div class="card">
        <div class="card-header">
          <h5 class="card-title mb-0">Transições de alerta preditivo — M4 &amp; M6 (últimas <?= $maxAlertRows ?>)</h5>
        </div>
        <div class="card-body p-0">
          <?php if (empty($recentAlerts)): ?>
            <p class="p-3 text-muted mb-0">Nenhuma transição registada ainda.</p>
          <?php else: ?>
          <div class="table-responsive">
            <table class="table table-sm table-hover mb-0">
              <thead class="table-light">
                <tr>
                  <th>Modelo</th>
                  <th>Estação</th>
                  <th>Tipo</th>
                  <th>Nível</th>
                  <th>Timestamp (UTC)</th>
                  <th>Debounce</th>
                  <th>Precip 6h</th>
                </tr>
              </thead>
              <tbody>
              <?php foreach ($recentAlerts as $row): ?>
                <tr>
                  <td>
                    <?php if ($row['model'] === 'M6'): ?>
                      <span class="badge" style="background:#E65100;">M6 MLR</span>
                    <?php else: ?>
                      <span class="badge" style="background:#8E24AA;">M4 LightGBM</span>
                    <?php endif; ?>
                  </td>
                  <td><?= (int)$row['id_station'] ?></td>
                  <td>
                    <?php if ($row['event_type'] === 'fired'): ?>
                      <span class="badge bg-danger">Disparado</span>
                    <?php else: ?>
                      <span class="badge bg-success">Normalizado</span>
                    <?php endif; ?>
                  </td>
                  <td>
                    <span class="badge <?= alertBadgeClass($row['alert_level']) ?>">
                      <?= alertLabel($row['alert_level']) ?>
                    </span>
                  </td>
                  <td><?= htmlspecialchars($row['ts']) ?></td>
                  <td><?= (int)$row['consecutive_steps'] ?> / 3 passos</td>
                  <td><?= $row['precip_rolling'] !== null ? round((float)$row['precip_rolling'], 2) . ' mm' : '—' ?></td>
                </tr>
              <?php endforeach; ?>
              </tbody>
            </table>
          </div>
          <?php endif; ?>
        </div>
      </div>

    </div><!-- /.container-fluid -->
  </div><!-- /.app-content -->
</main>
<!--end::App Main-->

<!-- ======================================================================== -->
<!-- Chart.js — prediction cone charts                                          -->
<!-- ======================================================================== -->
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"
        crossorigin="anonymous"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js"
        crossorigin="anonymous"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-annotation@3.0.1/dist/chartjs-plugin-annotation.min.js"
        crossorigin="anonymous"></script>

<script>
// ---------------------------------------------------------------------------
// Chart helper
// ---------------------------------------------------------------------------

/**
 * Build and render a level + M4 + M6 prediction Chart.js chart.
 *
 * @param {string}      canvasId     ID of the <canvas> element.
 * @param {Array}       historyData  [{ts: ISO string, level: number}]
 * @param {Object|null} predM4       Latest M4 prediction row from PHP, or null.
 * @param {Object|null} predM6       Latest M6 prediction row from PHP, or null.
 * @param {Object}      thresholds   {atencao, alerta, inundacao} in cm.
 */
function buildChart(canvasId, historyData, predM4, predM6, thresholds) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;

    // Observed level dataset.
    const obsPoints = historyData.map(r => ({x: r.ts, y: parseFloat(r.level)}));
    const bridgePoint = obsPoints.length > 0 ? [obsPoints[obsPoints.length - 1]] : [];

    // Helper: build prediction cone points from a prediction row.
    function buildPredPoints(pred) {
        if (!pred || !pred.timestamp) return [];
        const t0 = new Date(pred.timestamp.replace(' ', 'T') + 'Z');
        const pts = [];
        [{h: 30, k: 'h_pred_30'}, {h: 60, k: 'h_pred_60'},
         {h: 90, k: 'h_pred_90'}, {h: 120, k: 'h_pred_120'}].forEach(({h, k}) => {
            if (pred[k] !== null) {
                pts.push({x: new Date(t0.getTime() + h * 60 * 1000).toISOString(),
                          y: parseFloat(pred[k])});
            }
        });
        return pts;
    }

    const predM4Points = buildPredPoints(predM4);
    const predM6Points = buildPredPoints(predM6);

    const datasets = [
        {
            label: 'Observado',
            data: obsPoints,
            borderColor: '#1565C0',
            backgroundColor: 'transparent',
            borderWidth: 2,
            pointRadius: 0,
            tension: 0.2,
        },
        {
            label: 'Previsão M4 LightGBM',
            data: [...bridgePoint, ...predM4Points],
            borderColor: '#8E24AA',              /* purple */
            backgroundColor: 'rgba(142,36,170,0.06)',
            borderWidth: 2,
            borderDash: [5, 4],
            pointRadius: predM4Points.length > 0 ? [0, 4, 4, 4, 4] : [0],
            pointBackgroundColor: '#8E24AA',
            tension: 0.2,
        },
        {
            label: 'Previsão M6 MLR',
            data: [...bridgePoint, ...predM6Points],
            borderColor: '#E65100',              /* deep orange */
            backgroundColor: 'rgba(230,81,0,0.06)',
            borderWidth: 2,
            borderDash: [8, 4],                  /* longer dash to distinguish from M4 */
            pointRadius: predM6Points.length > 0 ? [0, 4, 4, 4, 4] : [0],
            pointBackgroundColor: '#E65100',
            tension: 0.2,
        },
    ];

    // Annotation lines for thresholds — labels removed from chart lines.
    // Threshold names and values are shown in the card-header legend box instead,
    // which avoids any overlap with data or tooltips regardless of screen size.
    // goldenrod matches the legend swatch and is more legible on white than CSS 'gold'.
    const annotations = {
        lineAtencao: {
            type: 'line', yMin: thresholds.atencao, yMax: thresholds.atencao,
            borderColor: 'goldenrod', borderWidth: 1.5, borderDash: [4, 3],
            label: {display: false},
        },
        lineAlerta: {
            type: 'line', yMin: thresholds.alerta, yMax: thresholds.alerta,
            borderColor: 'darkorange', borderWidth: 1.5, borderDash: [4, 3],
            label: {display: false},
        },
        lineInundacao: {
            type: 'line', yMin: thresholds.inundacao, yMax: thresholds.inundacao,
            borderColor: 'crimson', borderWidth: 1.5, borderDash: [4, 3],
            label: {display: false},
        },
    };

    // Vertical line at "now" to separate history from forecast.
    annotations.lineNow = {
        type: 'line',
        xMin: new Date().toISOString(),
        xMax: new Date().toISOString(),
        borderColor: 'rgba(0,0,0,0.3)',
        borderWidth: 1,
        borderDash: [3, 3],
        label: {display: true, content: 'Agora', position: 'start', font: {size: 9}},
    };

    new Chart(ctx, {
        type: 'line',
        data: {datasets},
        options: {
            responsive: true,
            maintainAspectRatio: false,    /* height is controlled by .chart-wrapper CSS */
            layout: {padding: {left: 8}},
            interaction: {mode: 'index', intersect: false},
            scales: {
                x: {
                    type: 'time',
                    time: {
                        unit: 'minute',
                        displayFormats: {
                            minute: 'HH:mm',
                            hour:   'HH:mm',
                            day:    'dd/MM HH:mm',
                        },
                        tooltipFormat: 'dd/MM/yyyy HH:mm',
                    },
                    ticks: {
                        callback: function(value, index, ticks) {
                            const d = new Date(value);
                            const hhmm = d.toISOString().substring(11, 16);
                            const dd = String(d.getUTCDate()).padStart(2, '0');
                            const mm = String(d.getUTCMonth() + 1).padStart(2, '0');
                            if (index === 0) return dd + '/' + mm + ' ' + hhmm;
                            // Show date whenever the day rolls over from the previous tick.
                            const prev = new Date(ticks[index - 1].value);
                            if (prev.getUTCDate() !== d.getUTCDate()) {
                                return dd + '/' + mm + ' ' + hhmm;
                            }
                            return hhmm;
                        },
                    },
                    title: {display: true, text: 'Hora (UTC)'},
                },
                y: {
                    title: {display: true, text: 'Cota (cm)'},
                    suggestedMin: (function() {
                        const allY = obsPoints.map(p => p.y)
                            .concat(predM4Points.map(p => p.y))
                            .concat(predM6Points.map(p => p.y));
                        if (!allY.length) return 0;
                        return Math.max(0, Math.min(...allY) - 10);
                    })(),
                    suggestedMax: Math.max(thresholds.inundacao * 1.1,
                        (function() {
                            const allY = obsPoints.map(p => p.y)
                                .concat(predM4Points.map(p => p.y))
                                .concat(predM6Points.map(p => p.y));
                            return allY.length ? Math.max(...allY) + 10 : thresholds.inundacao * 1.1;
                        })()),
                },
            },
            plugins: {
                legend: {position: 'top'},
                annotation: {annotations},
            },
        },
    });
}

// ---------------------------------------------------------------------------
// Data passed from PHP
// ---------------------------------------------------------------------------

// Defer chart init until the browser has finished laying out the page so
// Chart.js reads the correct container width, not a pre-layout estimate.
window.addEventListener('load', function () {
<?php foreach ($stations as $sid => $cfg_s):
    $hist   = $stationData[$sid]['history']       ?? [];
    $pred   = $stationData[$sid]['prediction']    ?? null;
    $predM6 = $stationData[$sid]['prediction_m6'] ?? null;
?>
    buildChart(
        <?= json_encode("chart_station_{$sid}") ?>,
        <?= json_encode($hist) ?>,
        <?= json_encode($pred) ?>,
        <?= json_encode($predM6) ?>,
        <?= json_encode(['atencao' => $cfg_s['atencao'], 'alerta' => $cfg_s['alerta'], 'inundacao' => $cfg_s['inundacao']]) ?>
    );
<?php endforeach; ?>
});

// Auto-refresh every 5 minutes.
setTimeout(() => location.reload(), 5 * 60 * 1000);
</script>

<?php
$footerExtra = 'Modelos preditivos com <a href="https://github.com/unit8co/darts" target="_blank" rel="noopener noreferrer">DARTS</a> — Unit8.';
require_once 'footer.php';
?>
