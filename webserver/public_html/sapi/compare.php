<?php
/**
 * compare.php — Comparação multi-estação em um único gráfico (Issue #56 Phase 4).
 *
 * Permite selecionar múltiplas estações e uma variável para sobrepor as
 * séries temporais em um único gráfico Chart.js, com uma série por estação.
 * Opcionalmente sobrepõe prec_mm do MERGE em eixo Y secundário.
 *
 * Parâmetros GET:
 *   stations[]   (int[])  — IDs das estações selecionadas
 *   var          (string) — coluna de measurements a comparar
 *   de           (string) — data/hora inicial (Y-m-d H:i)
 *   ate          (string) — data/hora final   (Y-m-d H:i)
 *   show_merge   (1|0)    — sobrepor prec_mm do MERGE
 */
require_once 'header.php';

$pdo = db();

// ── Whitelist de variáveis ─────────────────────────────────────────────────
$allowedVars = [
    'level_cm'              => 'Nível (cm)',
    'temperature_C'         => 'Temperatura do ar (°C)',
    'pressure'              => 'Pressão (hPa)',
    'humidity_percentual'   => 'Umidade relativa (%)',
    'surface_temperature_C' => 'Temperatura superfície (°C)',
    'precipitation_pulses'  => 'Pulsos de precipitação',
    'precipitation_mm'      => 'Precipitação (mm)',
    'bat_voltage'           => 'Tensão bateria (V)',
    'panel_voltage'         => 'Tensão painel (V)',
    'rssi'                  => 'RSSI',
    's_wifi'                => 'Sinal Wi-Fi',
    's_gsm'                 => 'Sinal GSM',
];

// Limites físicos por variável (para filtragem de outliers — Issue #56)
$varLimits = [
    'level_cm'              => [0,    500  ],
    'temperature_C'         => [-10,  55   ],
    'surface_temperature_C' => [-10,  55   ],
    'pressure'              => [900,  1100 ],
    'humidity_percentual'   => [0,    100  ],
    'precipitation_pulses'  => [0,    2000 ],
    'precipitation_mm'      => [0,    200  ],
    'bat_voltage'           => [0,    20   ],
    'panel_voltage'         => [0,    30   ],
    'rssi'                  => [-140, 0    ],
    's_wifi'                => [-100, 0    ],
    's_gsm'                 => [-115, 0    ],
];

// ── Todas as estações disponíveis (para o formulário) ─────────────────────
$stmtAll = $pdo->query(
    "SELECT id, name FROM stations WHERE deleted_at IS NULL ORDER BY id ASC"
);
$allStations = $stmtAll->fetchAll(PDO::FETCH_ASSOC);

// ── Parâmetros GET ─────────────────────────────────────────────────────────
$selectedIds = [];
if (!empty($_GET['stations']) && is_array($_GET['stations'])) {
    foreach ($_GET['stations'] as $sid) {
        $sid = (int)$sid;
        if ($sid > 0) $selectedIds[] = $sid;
    }
}
$selectedIds = array_unique($selectedIds);

$variavel   = isset($_GET['var']) && array_key_exists($_GET['var'], $allowedVars)
              ? $_GET['var'] : '';
$showMerge  = !empty($_GET['show_merge']);

// ── Datas ──────────────────────────────────────────────────────────────────
$now         = new DateTime();
$defaultEnd  = clone $now;
$defaultStart = (clone $now)->modify('-7 days');

$de  = trim((string)($_GET['de']  ?? ''));
$ate = trim((string)($_GET['ate'] ?? ''));

try {
    $startDt = $de  ? new DateTime($de)  : $defaultStart;
    $endDt   = $ate ? new DateTime($ate) : $defaultEnd;
    if ($startDt > $endDt) [$startDt, $endDt] = [$endDt, $startDt];
} catch (Exception $e) {
    $startDt = $defaultStart;
    $endDt   = $defaultEnd;
}

$deHtml  = $startDt->format('Y-m-d H:i');
$ateHtml = $endDt->format('Y-m-d H:i');
$deSql   = $startDt->format('Y-m-d H:i:s');
$ateSql  = $endDt->format('Y-m-d H:i:s');

$periodoStr = $startDt->format('d/m/Y H:i') . ' até ' . $endDt->format('d/m/Y H:i');

// ── Busca dados de medições para cada estação selecionada ──────────────────
/**
 * $seriesData — array de séries por estação.
 * Para level_cm inclui também as séries pré-filtradas pelo cron (Issue #57):
 *   valuesDelta  — level_delta_cm (null = rejeitado)
 *   valuesKalman — level_kalman_cm (null = rejeitado)
 *   hasDbFiltered — true se ao menos um ponto Kalman foi encontrado
 */
$seriesData = [];

if ($variavel && !empty($selectedIds)) {
    $limMin = $varLimits[$variavel][0] ?? null;
    $limMax = $varLimits[$variavel][1] ?? null;

    // Busca nome das estações selecionadas
    $placeholders = implode(',', array_fill(0, count($selectedIds), '?'));
    $stmtNames    = $pdo->prepare(
        "SELECT id, name FROM stations WHERE id IN ($placeholders) AND deleted_at IS NULL"
    );
    $stmtNames->execute($selectedIds);
    $stationNames = [];
    foreach ($stmtNames->fetchAll(PDO::FETCH_ASSOC) as $r) {
        $stationNames[$r['id']] = $r['name'];
    }

    foreach ($selectedIds as $sid) {
        // Para level_cm busca também as colunas pré-filtradas (Issue #57)
        if ($variavel === 'level_cm') {
            $stmtMeas = $pdo->prepare("
                SELECT timestamp,
                       level_cm        AS value,
                       level_delta_cm,
                       level_kalman_cm
                FROM measurements
                WHERE id_station = :id
                  AND deleted_at IS NULL
                  AND timestamp BETWEEN :de AND :ate
                ORDER BY timestamp ASC
            ");
        } else {
            $stmtMeas = $pdo->prepare("
                SELECT timestamp, `{$variavel}` AS value
                FROM measurements
                WHERE id_station = :id
                  AND deleted_at IS NULL
                  AND timestamp BETWEEN :de AND :ate
                ORDER BY timestamp ASC
            ");
        }
        $stmtMeas->execute([':id' => $sid, ':de' => $deSql, ':ate' => $ateSql]);

        $labels       = [];
        $values       = [];
        $valuesDelta  = [];
        $valuesKalman = [];
        $hasDbFiltered = false;

        while ($row = $stmtMeas->fetch(PDO::FETCH_ASSOC)) {
            if ($row['value'] === null) continue;
            $v = (float)$row['value'];
            if ($limMin !== null && $v < $limMin) continue;
            if ($limMax !== null && $v > $limMax) continue;
            $labels[] = (new DateTime($row['timestamp']))->format('Y-m-d H:i:s');
            $values[] = $v;

            if ($variavel === 'level_cm') {
                $dv = isset($row['level_delta_cm'])  && $row['level_delta_cm']  !== null
                      ? (float)$row['level_delta_cm']  : null;
                $kv = isset($row['level_kalman_cm']) && $row['level_kalman_cm'] !== null
                      ? (float)$row['level_kalman_cm'] : null;
                $valuesDelta[]  = $dv;
                $valuesKalman[] = $kv;
                if (!$hasDbFiltered && $kv !== null) {
                    $hasDbFiltered = true;
                }
            }
        }

        $seriesData[] = [
            'id'            => $sid,
            'name'          => $stationNames[$sid] ?? ('Estação ' . $sid),
            'labels'        => $labels,
            'values'        => $values,
            'valuesDelta'   => $valuesDelta,
            'valuesKalman'  => $valuesKalman,
            'hasDbFiltered' => $hasDbFiltered,
        ];
    }
}

// ── MERGE prec_mm ──────────────────────────────────────────────────────────
$mergeLabels = [];
$mergeValues = [];

if ($showMerge && $variavel) {
    $stmtMerge = $pdo->prepare("
        SELECT timestamp, prec_mm AS value
        FROM `merge`
        WHERE deleted_at IS NULL AND timestamp BETWEEN :de AND :ate
        ORDER BY timestamp ASC
    ");
    $stmtMerge->execute([':de' => $deSql, ':ate' => $ateSql]);
    while ($row = $stmtMerge->fetch(PDO::FETCH_ASSOC)) {
        if ($row['value'] === null) continue;
        $mergeLabels[] = (new DateTime($row['timestamp']))->format('Y-m-d H:i:s');
        $mergeValues[] = (float)$row['value'];
    }
}

// Paleta de cores para séries (uma cor por estação)
$palette = ['#007a33', '#8b5cf6', '#dc3545', '#fd7e14', '#e91e8c', '#20c997', '#f59e0b'];
?>

      <!--begin::App Main-->
      <main class="app-main">
        <!--begin::App Content Header-->
        <div class="app-content-header">
          <div class="container-fluid">
            <div class="row">
              <div class="col-sm-8">
                <h3 class="mb-0">Comparação de estações</h3>
                <?php if ($variavel): ?>
                  <p class="text-muted mb-0 small">
                    <?= htmlspecialchars($allowedVars[$variavel]) ?> &middot; <?= htmlspecialchars($periodoStr) ?>
                  </p>
                <?php endif; ?>
              </div>
            </div>
          </div>
        </div>
        <!--end::App Content Header-->

        <!--begin::App Content-->
        <div class="app-content">
          <div class="container-fluid">

            <!-- Formulário de seleção -->
            <div class="card mb-3">
              <div class="card-header">
                <h3 class="card-title mb-0">Configurar comparação</h3>
              </div>
              <div class="card-body">
                <form method="get" class="row gx-3 gy-2 align-items-end">

                  <!-- Seleção de estações -->
                  <div class="col-12 col-md-4">
                    <label class="form-label small mb-1">Estações</label>
                    <div class="border rounded p-2" style="max-height: 140px; overflow-y: auto;">
                      <?php foreach ($allStations as $s): ?>
                        <div class="form-check">
                          <input
                            class="form-check-input"
                            type="checkbox"
                            name="stations[]"
                            value="<?= (int)$s['id'] ?>"
                            id="st<?= (int)$s['id'] ?>"
                            <?= in_array((int)$s['id'], $selectedIds) ? 'checked' : '' ?>
                          >
                          <label class="form-check-label small" for="st<?= (int)$s['id'] ?>">
                            <?= htmlspecialchars($s['name']) ?>
                          </label>
                        </div>
                      <?php endforeach; ?>
                    </div>
                  </div>

                  <!-- Variável -->
                  <div class="col-12 col-md-3">
                    <label for="var" class="form-label small mb-1">Variável</label>
                    <select id="var" name="var" class="form-select form-select-sm">
                      <option value="">— selecione —</option>
                      <?php foreach ($allowedVars as $col => $label): ?>
                        <option value="<?= htmlspecialchars($col) ?>"
                          <?= $col === $variavel ? 'selected' : '' ?>>
                          <?= htmlspecialchars($label) ?>
                        </option>
                      <?php endforeach; ?>
                    </select>
                  </div>

                  <!-- Datas -->
                  <div class="col-6 col-md-2">
                    <label for="de" class="form-label small mb-1">Início</label>
                    <input type="text" id="de" name="de"
                           class="form-control form-control-sm"
                           value="<?= htmlspecialchars($deHtml) ?>"
                           autocomplete="off" required>
                  </div>
                  <div class="col-6 col-md-2">
                    <label for="ate" class="form-label small mb-1">Fim</label>
                    <input type="text" id="ate" name="ate"
                           class="form-control form-control-sm"
                           value="<?= htmlspecialchars($ateHtml) ?>"
                           autocomplete="off" required>
                  </div>

                  <!-- Opções + botão -->
                  <div class="col-12 col-md-1 d-flex flex-column gap-1">
                    <div class="form-check form-check-sm">
                      <input class="form-check-input" type="checkbox"
                             name="show_merge" value="1" id="chkMerge"
                             <?= $showMerge ? 'checked' : '' ?>>
                      <label class="form-check-label small" for="chkMerge">
                        + MERGE
                      </label>
                    </div>
                    <button type="submit" class="btn btn-primary btn-sm">
                      Gerar
                    </button>
                  </div>

                </form>
              </div>
            </div>

            <!-- Gráfico de comparação -->
            <?php if ($variavel && !empty($seriesData)): ?>
              <div class="card mb-3">
                <div class="card-header">
                  <h3 class="card-title mb-0">
                    <?= htmlspecialchars($allowedVars[$variavel]) ?> — todas as estações
                  </h3>
                </div>
                <div class="card-body">
                  <div class="mb-2 text-center">
                    <small class="text-muted">
                      Use scroll ou arraste (retângulo) para dar zoom.
                      Clique na legenda para ocultar/mostrar séries.
                    </small>
                  </div>
                  <div class="chart-container" style="position: relative; width: 100%; height: 380px;">
                    <canvas id="grafico_compare"></canvas>
                  </div>
                  <div class="mt-2 text-center">
                    <button type="button" class="btn btn-outline-primary btn-sm me-1" onclick="chartCompare.resetZoom()">
                      Redefinir zoom
                    </button>
                    <button type="button" class="btn btn-outline-primary btn-sm me-1" onclick="baixarCompare()">
                      Baixar imagem
                    </button>
                    <button type="button" class="btn btn-outline-primary btn-sm" onclick="exportarCSVCompare()">
                      Exportar CSV
                    </button>
                  </div>
                </div>
              </div>
            <?php elseif ($variavel && empty($selectedIds)): ?>
              <div class="alert alert-info">Selecione ao menos uma estação para comparar.</div>
            <?php elseif (!$variavel && !empty($selectedIds)): ?>
              <div class="alert alert-info">Selecione uma variável para comparar.</div>
            <?php endif; ?>

          </div>
        </div>
        <!--end::App Content-->
      </main>
      <!--end::App Main-->

    <!-- Scripts -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/date-fns@2.29.3"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-zoom@2.0.1/dist/chartjs-plugin-zoom.min.js"></script>

    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/flatpickr/dist/flatpickr.min.css">
    <script src="https://cdn.jsdelivr.net/npm/flatpickr"></script>
    <script src="https://cdn.jsdelivr.net/npm/flatpickr/dist/l10n/pt.js"></script>

<script>
document.addEventListener('DOMContentLoaded', function () {
  flatpickr("#de",  { enableTime: true, dateFormat: "Y-m-d H:i", time_24hr: true, locale: "pt" });
  flatpickr("#ate", { enableTime: true, dateFormat: "Y-m-d H:i", time_24hr: true, locale: "pt" });
});
</script>

<?php if ($variavel && !empty($seriesData)): ?>
<script>
/**
 * Gráfico de comparação multi-estação (Issue #56 Phase 4, Issue #57 update).
 *
 * Cada estação selecionada é uma série independente com timestamps próprios
 * (não são alinhadas forçosamente — Chart.js time scale cuida da posição).
 * MERGE prec_mm usa eixo Y secundário (y2) quando habilitado.
 *
 * Para level_cm, quando dados pré-filtrados estão disponíveis (Issue #57),
 * são adicionadas três séries por estação com a mesma cor:
 *   Raw    — linha fina, 40 % opacidade  (fundo)
 *   Delta  — linha média, 60 % opacidade (intermediária)
 *   Kalman — linha espessa, 100 % opacidade (foreground, mais proeminente)
 */
const palette   = <?= json_encode($palette) ?>;
const seriesRaw = <?= json_encode($seriesData, JSON_UNESCAPED_UNICODE | JSON_NUMERIC_CHECK) ?>;
const showMerge = <?= json_encode($showMerge) ?>;
const mergeLabels = <?= json_encode($mergeLabels) ?>;
const mergeValues = <?= json_encode($mergeValues, JSON_NUMERIC_CHECK) ?>;

/**
 * Converte uma cor hex (#rrggbb) para rgba com a opacidade indicada.
 * @param {string} hex   - Cor em formato #rrggbb.
 * @param {number} alpha - Opacidade 0.0–1.0.
 * @returns {string}     - String rgba(r,g,b,alpha).
 */
function hexToRgba(hex, alpha) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

const datasets = [];

seriesRaw.forEach((s, idx) => {
  const color = palette[idx % palette.length];

  if (s.hasDbFiltered) {
    // ── Raw: linha fina, cor com 40% opacidade ──
    datasets.push({
      label: s.name + ' (bruto)',
      data: s.labels.map((ts, i) => ({ x: ts, y: s.values[i] })),
      borderColor: hexToRgba(color, 0.40),
      backgroundColor: hexToRgba(color, 0.05),
      tension: 0.25, pointRadius: 0, pointHoverRadius: 3,
      borderWidth: 1, fill: false, yAxisID: 'y1', spanGaps: false,
    });
    // ── Delta: tracejado, cor com 65% opacidade ──
    datasets.push({
      label: s.name + ' (Δ filtrado)',
      data: s.labels.map((ts, i) => ({ x: ts, y: s.valuesDelta[i] })),
      borderColor: hexToRgba(color, 0.65),
      backgroundColor: hexToRgba(color, 0.05),
      borderDash: [6, 4],
      tension: 0.25, pointRadius: 0, pointHoverRadius: 3,
      borderWidth: 1.5, fill: false, yAxisID: 'y1', spanGaps: false,
    });
    // ── Kalman: linha espessa, cor plena — foreground ──
    datasets.push({
      label: s.name + ' (Kalman)',
      data: s.labels.map((ts, i) => ({ x: ts, y: s.valuesKalman[i] })),
      borderColor: color,
      backgroundColor: hexToRgba(color, 0.08),
      tension: 0.35, pointRadius: 0, pointHoverRadius: 4,
      borderWidth: 2.5, fill: false, yAxisID: 'y1', spanGaps: false,
    });
  } else {
    // Sem dados pré-filtrados — exibe apenas série bruta
    datasets.push({
      label: s.name,
      data: s.labels.map((ts, i) => ({ x: ts, y: s.values[i] })),
      borderColor: color,
      backgroundColor: hexToRgba(color, 0.10),
      tension: 0.25, pointRadius: 1, pointHoverRadius: 4,
      borderWidth: 2, fill: false, yAxisID: 'y1', spanGaps: false,
    });
  }
});

if (showMerge && mergeLabels.length) {
  datasets.push({
    label: 'MERGE prec_mm',
    data: mergeLabels.map((ts, i) => ({ x: ts, y: mergeValues[i] })),
    borderColor: '#0dcaf0',          // ciano — distinto do nível (amarelo) e Kalman (roxo)
    backgroundColor: 'rgba(13,202,240,0.15)',
    tension: 0.25,
    pointRadius: 0,
    pointHoverRadius: 3,
    fill: true,
    yAxisID: 'y2',
    spanGaps: true,
  });
}

const scales = {
  x: {
    type: 'time',
    time: {
      parser: 'yyyy-MM-dd HH:mm:ss',
      tooltipFormat: 'dd/MM/yyyy HH:mm',
      displayFormats: { hour: 'dd/MM HH:mm', minute: 'dd/MM HH:mm' }
    },
    title: { display: true, text: 'Data/Hora (UTC)' }
  },
  y1: {
    position: 'left',
    title: { display: true, text: '<?= addslashes($allowedVars[$variavel]) ?>' }
  }
};

if (showMerge && mergeLabels.length) {
  scales.y2 = {
    position: 'right',
    grid: { drawOnChartArea: false },
    title: { display: true, text: 'prec_mm (mm)' }
  };
}

const ctx = document.getElementById('grafico_compare').getContext('2d');
const chartCompare = new Chart(ctx, {
  type: 'line',
  data: { datasets },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    plugins: {
      legend: { position: 'top' },
      title: { display: true, text: 'Comparação — <?= addslashes($allowedVars[$variavel]) ?>' },
      zoom: {
        pan:  { enabled: true, mode: 'xy' },
        zoom: { wheel: { enabled: true }, pinch: { enabled: true }, drag: { enabled: true }, mode: 'xy' }
      }
    },
    scales
  }
});

/** Baixa o gráfico como imagem PNG. */
function baixarCompare() {
  const a = document.createElement('a');
  a.href     = chartCompare.toBase64Image();
  a.download = 'compare-<?= addslashes($variavel) ?>.png';
  a.click();
}
window.baixarCompare = baixarCompare;

/** Exporta CSV com todas as séries visíveis (timestamps + valores por estação). */
function exportarCSVCompare() {
  const xScale = chartCompare.scales.x;
  const xMin   = xScale.min;
  const xMax   = xScale.max;

  // Coleta todos os timestamps únicos dentro do zoom
  const tsSet = new Set();
  chartCompare.data.datasets.forEach(ds => {
    ds.data.forEach(pt => {
      const t = new Date(pt.x).getTime();
      if (t >= xMin && t <= xMax) tsSet.add(pt.x);
    });
  });

  const tsSorted = [...tsSet].sort();
  const headers  = ['timestamp', ...chartCompare.data.datasets.map(ds => ds.label)];

  const rows = tsSorted.map(ts => {
    const t   = new Date(ts).getTime();
    const row = [ts];
    chartCompare.data.datasets.forEach(ds => {
      const pt = ds.data.find(p => p.x === ts && new Date(p.x).getTime() >= xMin && new Date(p.x).getTime() <= xMax);
      row.push(pt !== undefined ? pt.y : '');
    });
    return row.join(';');
  });

  if (!rows.length) { alert('Nenhum dado visível para exportar.'); return; }

  const blob = new Blob([headers.join(';') + '\n' + rows.join('\n')], { type: 'text/csv;charset=utf-8;' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href     = url;
  a.download = 'compare-<?= addslashes($variavel) ?>.csv';
  a.click();
  URL.revokeObjectURL(url);
}
window.exportarCSVCompare = exportarCSVCompare;
</script>
<?php endif; ?>

<?php require_once 'footer.php'; ?>
