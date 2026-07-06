<?php
require_once 'header.php';

// Conexão PDO
$pdo = db();

/**
 * Página merge.php
 *
 * Um ÚNICO gráfico com:
 *  - variável de interesse de measurements (var)
 *  - prec_mm da tabela merge
 *
 * Filtros:
 *  - id_station (obrigatório, measurements)
 *  - var        (obrigatório, coluna em measurements)
 *  - de / ate   (opcionais, Y-m-d H:i)
 *  - mode       (opcional, filtra merge.mode; vazio = todos)
 */

$idStation = isset($_GET['id_station'])
    ? (int)$_GET['id_station']
    : (isset($_GET['idStation']) ? (int)$_GET['idStation'] : 0);

$variavel = $_GET['var'] ?? null;
$mode     = isset($_GET['mode']) ? trim((string)$_GET['mode']) : '';

if (!$idStation) {
    die('Estação não especificada (parâmetro id_station).');
}
if (!$variavel) {
    die('Variável não especificada (parâmetro var).');
}

/**
 * Limites físicos válidos por variável (Issue #56).
 * Valores fora destes intervalos são descartados na exibição.
 * @var array<string, array{0: float, 1: float}>
 */
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

// Whitelist de colunas válidas em measurements
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

if (!array_key_exists($variavel, $allowedVars)) {
    die('Variável inválida para measurements: ' . htmlspecialchars($variavel));
}

// Datas: de / ate (texto: Y-m-d H:i)
$de  = isset($_GET['de'])  ? trim((string)$_GET['de'])  : '';
$ate = isset($_GET['ate']) ? trim((string)$_GET['ate']) : '';

$now          = new DateTime('now');
$defaultEnd   = clone $now;
$defaultStart = (clone $now)->modify('-7 days');

if ($de || $ate) {
    try {
        if ($de) {
            $startDt = new DateTime($de);
        } else {
            $startDt = $defaultStart;
        }

        if ($ate) {
            $endDt = new DateTime($ate);
        } else {
            $endDt = $defaultEnd;
        }

        if ($startDt > $endDt) {
            [$startDt, $endDt] = [$endDt, $startDt];
        }
    } catch (Exception $e) {
        $startDt = $defaultStart;
        $endDt   = $defaultEnd;
    }
} else {
    $startDt = $defaultStart;
    $endDt   = $defaultEnd;
}

$deHtml  = $startDt->format('Y-m-d H:i');
$ateHtml = $endDt->format('Y-m-d H:i');

$deSql  = $startDt->format('Y-m-d H:i:s');
$ateSql = $endDt->format('Y-m-d H:i:s');

// Nome/descrição da estação (se tiver tabela stations)
$stationName = 'Estação #' . $idStation;
$stationDesc = '';

try {
    $sqlStation = "SELECT name, description FROM stations WHERE id = :id AND deleted_at IS NULL";
    $stStation  = $pdo->prepare($sqlStation);
    $stStation->execute([':id' => $idStation]);
    if ($st = $stStation->fetch(PDO::FETCH_ASSOC)) {
        if (!empty($st['name'])) {
            $stationName = $st['name'];
        }
        if (!empty($st['description'])) {
            $stationDesc = $st['description'];
        }
    }
} catch (Throwable $e) {
    // ignora se não existir
}

// Lista de modes distintos em merge (para o select)
$modes = [];
try {
    $stModes = $pdo->query("SELECT DISTINCT mode FROM `merge` WHERE mode IS NOT NULL ORDER BY mode");
    if ($stModes) {
        while ($row = $stModes->fetch(PDO::FETCH_ASSOC)) {
            $value = trim((string)$row['mode']);
            if ($value !== '') {
                $modes[] = $value;
            }
        }
    }
} catch (Throwable $e) {
    $modes = [];
}

if ($mode !== '' && !in_array($mode, $modes, true)) {
    $mode = '';
}

// ------------------------
// measurements: variável de interesse
// Para level_cm também busca level_delta_cm (Issue #63 / both.php).
// O filtro delta rejeita picos isolados com zero lag — evita distorção do
// eixo Y causada por outliers dentro dos limites físicos (e.g. 335 cm).
// ------------------------
$fetchDelta = ($variavel === 'level_cm');

$sqlMeas = $fetchDelta
    ? "SELECT timestamp, level_cm AS value, level_delta_cm AS value_delta
       FROM measurements
       WHERE id_station = :id_station
         AND deleted_at IS NULL
         AND timestamp BETWEEN :de AND :ate
       ORDER BY timestamp ASC"
    : "SELECT timestamp, `$variavel` AS value
       FROM measurements
       WHERE id_station = :id_station
         AND deleted_at IS NULL
         AND timestamp BETWEEN :de AND :ate
       ORDER BY timestamp ASC";

$stMeas = $pdo->prepare($sqlMeas);
$stMeas->execute([
    ':id_station' => $idStation,
    ':de'         => $deSql,
    ':ate'        => $ateSql,
]);

$mapMeas       = []; // ts => valor
$limMin        = $varLimits[$variavel][0] ?? null;
$limMax        = $varLimits[$variavel][1] ?? null;
$countOutliers = 0;
$hasDbFiltered = false; // true se ao menos um ponto delta foi usado

while ($row = $stMeas->fetch(PDO::FETCH_ASSOC)) {
    if ($row['value'] === null) {
        continue;
    }
    $v = (float)$row['value'];

    // Descarta valores fora dos limites físicos da variável (Issue #56)
    if ($limMin !== null && $v < $limMin) { $countOutliers++; continue; }
    if ($limMax !== null && $v > $limMax) { $countOutliers++; continue; }

    // Prefere level_delta_cm quando disponível (Issue #63) —
    // zero lag, picos rejeitados. Fallback para raw se delta for null.
    if ($fetchDelta && isset($row['value_delta']) && $row['value_delta'] !== null) {
        $v = (float)$row['value_delta'];
        $hasDbFiltered = true;
    }

    $ts = (new DateTime($row['timestamp']))->format('Y-m-d H:i:s');
    $mapMeas[$ts] = $v;
}

// ------------------------
// merge: prec_mm, com filtro por mode
// ------------------------
$sqlMerge = "
    SELECT timestamp, prec_mm AS value, mode
    FROM `merge`
    WHERE deleted_at IS NULL
      AND timestamp BETWEEN :de AND :ate
";
$paramsMerge = [
    ':de'  => $deSql,
    ':ate' => $ateSql,
];

if ($mode !== '') {
    $sqlMerge .= " AND mode = :mode";
    $paramsMerge[':mode'] = $mode;
}

$sqlMerge .= " ORDER BY timestamp ASC";

$stMerge = $pdo->prepare($sqlMerge);
$stMerge->execute($paramsMerge);

$mapMerge = []; // ts => valor
while ($row = $stMerge->fetch(PDO::FETCH_ASSOC)) {
    if ($row['value'] === null) {
        continue;
    }
    $ts = (new DateTime($row['timestamp']))->format('Y-m-d H:i:s');
    $mapMerge[$ts] = (float)$row['value'];
}

// ------------------------
// measurements: Station-02 precipitation_mm (hardcoded id=2, Issue #66)
// Always shown alongside MERGE for direct comparison.
// ------------------------
$mapSt02 = [];
$limPrecMin = $varLimits['precipitation_mm'][0];
$limPrecMax = $varLimits['precipitation_mm'][1];

try {
    $sqlSt02 = "SELECT timestamp, precipitation_mm AS value
                FROM measurements
                WHERE id_station = 2
                  AND deleted_at IS NULL
                  AND timestamp BETWEEN :de AND :ate
                ORDER BY timestamp ASC";
    $stSt02 = $pdo->prepare($sqlSt02);
    $stSt02->execute([':de' => $deSql, ':ate' => $ateSql]);

    while ($row = $stSt02->fetch(PDO::FETCH_ASSOC)) {
        if ($row['value'] === null) {
            continue;
        }
        $v = (float)$row['value'];
        if ($v < $limPrecMin || $v > $limPrecMax) {
            continue;
        }
        $ts = (new DateTime($row['timestamp']))->format('Y-m-d H:i:s');
        $mapSt02[$ts] = $v;
    }
} catch (Throwable $e) {
    $mapSt02 = [];
}

// ------------------------
// Monta labels e séries alinhadas
// ------------------------
$labelsAll = array_unique(array_merge(
    array_keys($mapMeas),
    array_keys($mapMerge),
    array_keys($mapSt02)
));
sort($labelsAll); // Y-m-d H:i:s ordena certinho como string

$serieMeas  = [];
$serieMerge = [];
$serieSt02  = [];

foreach ($labelsAll as $ts) {
    $serieMeas[]  = array_key_exists($ts, $mapMeas)  ? $mapMeas[$ts]  : null;
    $serieMerge[] = array_key_exists($ts, $mapMerge) ? $mapMerge[$ts] : null;
    $serieSt02[]  = array_key_exists($ts, $mapSt02)  ? $mapSt02[$ts]  : null;
}

$tituloVariavel = $allowedVars[$variavel];
$tituloMerge    = 'prec_mm (merge' . ($mode !== '' ? ' — mode ' . $mode : '') . ')';

/**
 * When the left variable is precipitation_mm, both series are in mm —
 * share a single Y-axis so the scales are directly comparable.
 */
$sameScale = ($variavel === 'precipitation_mm');

$periodoStr = $startDt->format('d/m/Y H:i') . ' até ' . $endDt->format('d/m/Y H:i');
$labelModo  = $mode === '' ? 'Todos os modes (merge)' : ('Mode merge: ' . $mode);


$idStation = isset($_GET['id_station'])
    ? (int)$_GET['id_station']
    : (isset($_GET['idStation']) ? (int)$_GET['idStation'] : 0);

$variavel  = $_GET['var']  ?? '';
$deParam   = $_GET['de']   ?? '';
$ateParam  = $_GET['ate']  ?? '';
$modeParam = $_GET['mode'] ?? '';

// Monta query string para voltar ao view.php com os mesmos filtros
$viewParams = [
    'id_station' => $idStation,
    'var'        => $variavel,
    'de'         => $deParam,
    'ate'        => $ateParam,
];

if ($modeParam !== '') {
    $viewParams['mode'] = $modeParam;
}

$viewUrl = 'view.php?' . http_build_query($viewParams);

?>
      <!--begin::App Main-->
      <main class="app-main">
        <!--begin::App Content Header-->
        <div class="app-content-header">
          <div class="container-fluid">
            <div class="row">
              <div class="col-sm-8">
                <h3 class="mb-0">
                  <?= htmlspecialchars($stationName) ?> — <?= htmlspecialchars($tituloVariavel) ?> x prec_mm (merge)
                </h3>
                <p class="text-muted mb-0 small">
                  <?= htmlspecialchars($periodoStr) ?> &middot; <?= htmlspecialchars($labelModo) ?>
                </p>
                <?php if ($stationDesc): ?>
                  <p class="text-muted mb-0 small"><?= htmlspecialchars($stationDesc) ?></p>
                <?php endif; ?>
              </div>
              <div class="col-sm-4 text-sm-end mt-2 mt-sm-0">
                <span class="badge text-bg-secondary">Estação #<?= (int)$idStation ?></span>
              </div>
            </div>
          </div>
        </div>
        <!--end::App Content Header-->

        <!--begin::App Content-->
        <div class="app-content">
          <div class="container-fluid">

            <div class="row">
              <div class="col-12">

                <div class="card mb-3">
                  <div class="card-header d-flex flex-column flex-md-row justify-content-between align-items-md-center">
                    <div>
                      <h3 class="card-title mb-0 d-block w-100">Gráfico único — measurements x merge</h3>
                      <div class="text-muted small">
                        Variável: <?= htmlspecialchars($tituloVariavel) ?> (measurements) &middot; prec_mm (merge)
                      </div>
                    </div>
                  </div>

                  <div class="card-body">

                    <?php if ($countOutliers > 0): ?>
                      <div class="alert alert-warning alert-sm py-1 px-2 mb-2 small">
                        <i class="bi bi-exclamation-triangle-fill me-1"></i>
                        <?= $countOutliers ?> leitura(s) de <strong><?= htmlspecialchars($tituloVariavel) ?></strong>
                        fora dos limites físicos (<?= htmlspecialchars($limMin) ?> – <?= htmlspecialchars($limMax) ?>)
                        foram ocultadas. Os dados brutos permanecem no banco.
                      </div>
                    <?php endif; ?>
                    <?php if ($hasDbFiltered): ?>
                      <div class="alert alert-info alert-sm py-1 px-2 mb-2 small">
                        <i class="bi bi-funnel-fill me-1"></i>
                        A variável <strong><?= htmlspecialchars($tituloVariavel) ?></strong> está sendo exibida
                        com o <strong>filtro Δ</strong> aplicado — picos isolados do sensor foram removidos.
                        Os dados brutos permanecem no banco.
                      </div>
                    <?php endif; ?>

                    <!-- Filtros -->
                    <form method="get"
                          class="row row-cols-1 row-cols-md-4 gx-2 gy-1 align-items-end mb-3">

                      <input type="hidden" name="id_station" value="<?= (int)$idStation ?>">
                      <input type="hidden" name="var"        value="<?= htmlspecialchars($variavel) ?>">

                      <div class="col">
                        <label for="de" class="form-label mb-1 small">Data/hora inicial</label>
                        <input
                          type="text"
                          class="form-control form-control-sm"
                          id="de"
                          name="de"
                          value="<?= htmlspecialchars($deHtml) ?>"
                          autocomplete="off"
                          required
                        >
                      </div>

                      <div class="col">
                        <label for="ate" class="form-label mb-1 small">Data/hora final</label>
                        <input
                          type="text"
                          class="form-control form-control-sm"
                          id="ate"
                          name="ate"
                          value="<?= htmlspecialchars($ateHtml) ?>"
                          autocomplete="off"
                          required
                        >
                      </div>

                      <div class="col">
                        <label for="mode" class="form-label mb-1 small">Mode (merge)</label>
                        <select
                          id="mode"
                          name="mode"
                          class="form-select form-select-sm"
                        >
                          <option value="">Todos</option>
                          <?php foreach ($modes as $m): ?>
                            <option value="<?= htmlspecialchars($m) ?>"
                              <?= $m === $mode ? 'selected' : '' ?>>
                              <?= htmlspecialchars($m) ?>
                            </option>
                          <?php endforeach; ?>
                        </select>
                      </div>

                      <div class="col">
                        <label class="form-label mb-1 small d-none d-md-block">&nbsp;</label>
                        <button type="submit" class="btn btn-primary btn-sm w-100">
                          Aplicar filtro
                        </button>
                      </div>
                    </form>

                    <?php if (empty($labelsAll)): ?>
                      <div class="alert alert-warning mb-0">
                        Nenhum dado encontrado em <code>measurements</code> e <code>merge</code> para o período/modo informados.
                        A série da Estação-02 (prec_mm) também está vazia para este período.
                      </div>
                    <?php else: ?>

                      <div class="mb-2 text-center">
                        <small class="text-muted">
                          Um único gráfico com duas séries. Use o scroll do mouse ou arraste para dar zoom.
                        </small>
                      </div>

                      <div class="chart-container" style="position: relative; width: 100%; height: 360px;">
                        <canvas id="grafico_unico"></canvas>
                      </div>

                      <div class="mt-3 mb-3 text-center text-dark small" id="estatisticas_merge"></div>

                      <div class="mt-2 mt-md-0 text-center">
                        <button type="button" class="btn btn-outline-primary btn-sm" onclick="window.location.href='<?= htmlspecialchars($viewUrl, ENT_QUOTES, 'UTF-8') ?>'">
                          Voltar
                        </button>
                        <button type="button" class="btn btn-outline-primary btn-sm me-1" onclick="chartUnico.resetZoom()">
                          Redefinir zoom
                        </button>
                        <button type="button" class="btn btn-outline-primary btn-sm me-1" onclick="baixarUnico()">
                          Baixar imagem
                        </button>
                        <button type="button" class="btn btn-outline-primary btn-sm" onclick="exportarCSVUnico()">
                          Exportar CSV (merge)
                        </button>
                      </div>

                    <?php endif; ?>
                  </div>
                </div>

              </div>
            </div>

          </div>
        </div>
        <!--end::App Content-->
      </main>
      <!--end::App Main-->

    <!-- Scripts específicos da página -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-annotation@2.2.1"></script>
    <script src="https://cdn.jsdelivr.net/npm/date-fns@2.29.3"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-zoom@2.0.1/dist/chartjs-plugin-zoom.min.js"></script>

    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/flatpickr/dist/flatpickr.min.css">
    <script src="https://cdn.jsdelivr.net/npm/flatpickr"></script>
    <script src="https://cdn.jsdelivr.net/npm/flatpickr/dist/l10n/pt.js"></script>

<script>
document.addEventListener('DOMContentLoaded', function () {
  flatpickr("#de", {
    enableTime: true,
    dateFormat: "Y-m-d H:i",
    time_24hr: true,
    locale: "pt"
  });

  flatpickr("#ate", {
    enableTime: true,
    dateFormat: "Y-m-d H:i",
    time_24hr: true,
    locale: "pt"
  });
});
</script>

<script>
  const labels      = <?= json_encode($labelsAll) ?>;
  const serieMeas   = <?= json_encode($serieMeas,  JSON_NUMERIC_CHECK) ?>;
  const serieMerge  = <?= json_encode($serieMerge, JSON_NUMERIC_CHECK) ?>;
  const serieSt02   = <?= json_encode($serieSt02,  JSON_NUMERIC_CHECK) ?>;

  const hasMeas  = Array.isArray(serieMeas)  && serieMeas.some(v  => v !== null);
  const hasMerge = Array.isArray(serieMerge) && serieMerge.some(v => v !== null);
  const hasSt02  = Array.isArray(serieSt02)  && serieSt02.some(v  => v !== null);

  let chartUnico = null;

  if (labels.length && (hasMeas || hasMerge || hasSt02)) {
    const ctx = document.getElementById('grafico_unico').getContext('2d');

    const datasets = [];

    // When both series are in mm (precipitation_mm vs prec_mm), share y1 so
    // the scales are directly comparable. Otherwise use independent axes.
    const sameScale = <?= $sameScale ? 'true' : 'false' ?>;

    if (hasMeas) {
      datasets.push({
        label: '<?= addslashes($tituloVariavel) ?> (measurements)',
        data: serieMeas,
        borderColor: '#eab308',
        backgroundColor: 'rgba(234,179,8,0.15)',
        tension: 0.25,
        pointRadius: 0,
        pointHoverRadius: 3,
        fill: false,
        yAxisID: 'y1',
        spanGaps: true,
      });
    }

    if (hasMerge) {
      datasets.push({
        label: '<?= addslashes($tituloMerge) ?>',
        data: serieMerge,
        borderColor: '#0dcaf0',
        backgroundColor: 'rgba(13,202,240,0.18)',
        tension: 0.25,
        pointRadius: 0,
        pointHoverRadius: 3,
        fill: true,
        yAxisID: sameScale ? 'y1' : 'y2',
        spanGaps: true,
      });
    }

    if (hasSt02) {
      datasets.push({
        label: 'prec_mm (Estação-02 — medido)',
        data: serieSt02,
        borderColor: '#198754',
        backgroundColor: 'rgba(25,135,84,0.15)',
        tension: 0.25,
        pointRadius: 0,
        pointHoverRadius: 3,
        fill: false,
        yAxisID: sameScale ? 'y1' : 'y2',
        spanGaps: true,
      });
    }

    chartUnico = new Chart(ctx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: datasets
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        plugins: {
          legend: { display: true },
          zoom: {
            zoom: {
              wheel: { enabled: true },
              pinch: { enabled: true },
              drag:  { enabled: true },
              mode: 'x',
            },
            pan: {
              enabled: true,
              mode: 'x',
            }
          },
          annotation: { annotations: {} }
        },
        scales: {
          x: {
            title: { display: true, text: 'Data/Hora (UTC)' }
          },
          y1: {
            position: 'left',
            title: {
              display: true,
              text: sameScale ? 'Precipitação (mm)' : '<?= addslashes($tituloVariavel) ?>'
            }
          },
          ...(sameScale ? {} : {
            y2: {
              position: 'right',
              grid: { drawOnChartArea: false },
              title: { display: true, text: 'prec_mm (mm)' }
            }
          })
        }
      }
    });

    // Estatísticas e σ só sobre série merge
    function calcularEstatisticasMerge() {
      if (!hasMerge) return null;

      const vals = serieMerge
        .filter(v => v !== null && Number.isFinite(v));

      if (!vals.length) return null;

      const soma = vals.reduce((a, b) => a + b, 0);
      const media = soma / vals.length;

      const ordenados = [...vals].sort((a, b) => a - b);
      const meio = Math.floor(ordenados.length / 2);
      const mediana = ordenados.length % 2 === 0
        ? (ordenados[meio - 1] + ordenados[meio]) / 2
        : ordenados[meio];

      const moda = ordenados.sort((a, b) =>
        vals.filter(v => v === a).length - vals.filter(v => v === b).length
      ).pop();

      const variancia = vals.reduce((acc, val) => acc + Math.pow(val - media, 2), 0) / vals.length;
      const sigma = Math.sqrt(variancia);

      const minValor = Math.min(...vals);
      const maxValor = Math.max(...vals);

      return { media, mediana, moda, sigma, minimo: minValor, maximo: maxValor };
    }

    function atualizarEstatisticasMerge() {
      const stats = calcularEstatisticasMerge();
      const el = document.getElementById('estatisticas_merge');

      if (!stats) {
        el.innerHTML = '<div class="alert alert-info mb-0">Sem dados de prec_mm (merge) para calcular estatísticas.</div>';
        chartUnico.options.plugins.annotation.annotations = {};
        chartUnico.update();
        return;
      }

      el.innerHTML = `
        <div class="d-flex flex-wrap justify-content-center align-items-center gap-3 text-center mt-2">
          <div><strong>Média (merge)</strong><br>${stats.media.toFixed(2)}</div>
          <div><strong>Mediana</strong><br>${stats.mediana.toFixed(2)}</div>
          <div><strong>Moda</strong><br>${stats.moda.toFixed(2)}</div>
          <div><strong>Mín</strong><br>${stats.minimo.toFixed(2)}</div>
          <div><strong>Máx</strong><br>${stats.maximo.toFixed(2)}</div>
          <div><strong>σ</strong><br>${stats.sigma.toFixed(2)}</div>
          <div><strong>1σ</strong><br>${(stats.media - stats.sigma).toFixed(2)} a ${(stats.media + stats.sigma).toFixed(2)}</div>
          <div><strong>2σ</strong><br>${(stats.media - 2*stats.sigma).toFixed(2)} a ${(stats.media + 2*stats.sigma).toFixed(2)}</div>
          <div><strong>3σ</strong><br>${(stats.media - 3*stats.sigma).toFixed(2)} a ${(stats.media + 3*stats.sigma).toFixed(2)}</div>
        </div>
      `;

      const m = stats.media;
      const s = stats.sigma;

      const ann = {
        mean: {
          type: 'line',
          yScaleID: 'y2',
          yMin: m,
          yMax: m,
          borderColor: 'green',
          borderWidth: 1.5,
          label: {
            content: `Média: ${m.toFixed(2)}`,
            enabled: true,
            position: 'start',
            backgroundColor: 'rgba(0,128,0,0.1)',
            color: 'green'
          }
        },
        plus1: {
          type: 'line',
          yScaleID: 'y2',
          yMin: m + s,
          yMax: m + s,
          borderColor: 'orange',
          borderWidth: 1,
          borderDash: [4, 4],
          label: {
            content: '+1σ',
            enabled: true,
            position: 'end',
            backgroundColor: 'rgba(255,165,0,0.1)',
            color: 'orange'
          }
        },
        minus1: {
          type: 'line',
          yScaleID: 'y2',
          yMin: m - s,
          yMax: m - s,
          borderColor: 'orange',
          borderWidth: 1,
          borderDash: [4, 4],
          label: {
            content: '-1σ',
            enabled: true,
            position: 'end',
            backgroundColor: 'rgba(255,165,0,0.1)',
            color: 'orange'
          }
        },
        plus2: {
          type: 'line',
          yScaleID: 'y2',
          yMin: m + 2*s,
          yMax: m + 2*s,
          borderColor: 'red',
          borderWidth: 1,
          borderDash: [6, 4],
          label: {
            content: '+2σ',
            enabled: true,
            position: 'end',
            backgroundColor: 'rgba(255,0,0,0.08)',
            color: 'red'
          }
        },
        minus2: {
          type: 'line',
          yScaleID: 'y2',
          yMin: m - 2*s,
          yMax: m - 2*s,
          borderColor: 'red',
          borderWidth: 1,
          borderDash: [6, 4],
          label: {
            content: '-2σ',
            enabled: true,
            position: 'end',
            backgroundColor: 'rgba(255,0,0,0.08)',
            color: 'red'
          }
        },
        plus3: {
          type: 'line',
          yScaleID: 'y2',
          yMin: m + 3*s,
          yMax: m + 3*s,
          borderColor: '#6f42c1',
          borderWidth: 1,
          borderDash: [8, 4],
          label: {
            content: '+3σ',
            enabled: true,
            position: 'end',
            backgroundColor: 'rgba(111,66,193,0.08)',
            color: '#6f42c1'
          }
        },
        minus3: {
          type: 'line',
          yScaleID: 'y2',
          yMin: m - 3*s,
          yMax: m - 3*s,
          borderColor: '#6f42c1',
          borderWidth: 1,
          borderDash: [8, 4],
          label: {
            content: '-3σ',
            enabled: true,
            position: 'end',
            backgroundColor: 'rgba(111,66,193,0.08)',
            color: '#6f42c1'
          }
        }
      };

      chartUnico.options.plugins.annotation.annotations = ann;
      chartUnico.update();
    }

    //atualizarEstatisticasMerge();

    function baixarUnico() {
      const link = document.createElement('a');
      link.href = chartUnico.toBase64Image();
      link.download = 'grafico-measurements-merge.png';
      link.click();
    }
    window.baixarUnico = baixarUnico;

    function exportarCSVUnico() {
      if (!hasMerge && !hasSt02) {
        alert('Sem dados de precipitação para exportar.');
        return;
      }

      const linhas = ['timestamp;prec_mm_merge;prec_mm_estacao02'];
      labels.forEach((ts, idx) => {
        const vm = serieMerge[idx];
        const vs = serieSt02[idx];
        // Only emit rows that have at least one precipitation value
        if ((vm !== null && Number.isFinite(vm)) || (vs !== null && Number.isFinite(vs))) {
          const colMerge = (vm !== null && Number.isFinite(vm)) ? vm : '';
          const colSt02  = (vs !== null && Number.isFinite(vs)) ? vs : '';
          linhas.push(`${ts};${colMerge};${colSt02}`);
        }
      });

      const blob = new Blob([linhas.join('\n')], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'precipitacao_merge_estacao02.csv';
      a.click();
      URL.revokeObjectURL(url);
    }
    window.exportarCSVUnico = exportarCSVUnico;

  } else {
    function baixarUnico()  { alert('Sem dados para baixar gráfico.'); }
    function exportarCSVUnico() { alert('Sem dados para exportar.'); }
    window.baixarUnico = baixarUnico;
    window.exportarCSVUnico = exportarCSVUnico;
  }
</script>

<?php require_once 'footer.php'; ?>
