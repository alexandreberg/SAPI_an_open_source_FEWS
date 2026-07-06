<?php
require_once 'header.php';

// Conexão PDO
$pdo = db();

/**
 * Parâmetros GET:
 *  - id_station (ou idStation)
 *  - var (nome da coluna em measurements)
 *  - de / ate (YYYY-MM-DDTHH:MM no datetime-local)
 */

$idStation = isset($_GET['id_station'])
    ? (int)$_GET['id_station']
    : (isset($_GET['idStation']) ? (int)$_GET['idStation'] : 0);

$variavel = $_GET['var'] ?? null;

if (!$idStation) {
    die('Estação não especificada (parâmetro id_station).');
}
if (!$variavel) {
    die('Variável não especificada (parâmetro var).');
}

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

/**
 * Variables for which the Kalman filter button is shown.
 * Only level readings benefit from it — temperature, pressure, humidity,
 * voltages and precipitation are smooth signals or discrete events where
 * Kalman adds no value or is misleading.
 */
$kalmanVars = ['level_cm', 'surface_temperature_C'];

/**
 * Limites físicos válidos por variável (Issue #56).
 *
 * Valores fora destes intervalos são descartados na exibição —
 * os dados brutos permanecem intactos no banco de dados.
 *
 * Justificativas:
 *   level_cm            — altura máxima real abaixo de uma ponte (~5 m)
 *   temperature_C       — extremos climáticos de SC
 *   surface_temperature_C — idem
 *   pressure            — pressão atmosférica nível do mar ± margem
 *   humidity_percentual — 0–100 %
 *   precipitation_pulses — limite operacional de um pluviômetro de báscula
 *   bat_voltage         — bateria Li-ion + solar (faixa operacional)
 *   panel_voltage       — painel solar típico
 *   rssi                — faixa válida LoRa SX1276
 *   s_wifi              — faixa RSSI Wi-Fi
 *   s_gsm               — faixa RSSI GSM/NB-IoT
 *
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

if (!array_key_exists($variavel, $allowedVars)) {
    die('Variável inválida para consulta.');
}

// Filtro de datas
$de  = $_GET['de']  ?? null;
$ate = $_GET['ate'] ?? null;

// Se não veio filtro, usar últimos 7 dias
if (!$de && !$ate) {
    $endDt   = new DateTime(); // agora
    $startDt = (clone $endDt)->modify('-7 days');
} else {
    // Normaliza strings vindas do datetime-local (YYYY-MM-DDTHH:MM)
    try {
        if ($de) {
            $de = str_replace('T', ' ', $de);
            $startDt = new DateTime($de);
        }
        if ($ate) {
            $ate = str_replace('T', ' ', $ate);
            $endDt = new DateTime($ate);
        }
    } catch (Exception $e) {
        die('Formato de data/hora inválido.');
    }

    if (!isset($startDt) || !isset($endDt)) {
        die('Preencha data/hora inicial e final.');
    }

    if ($startDt > $endDt) {
        die('Data inicial deve ser menor ou igual à data final.');
    }
}

// Formatos para HTML (datetime-local) e SQL
$deHtml  = $startDt->format('Y-m-d H:i');
$ateHtml = $endDt->format('Y-m-d H:i');

$deSql  = $startDt->format('Y-m-d H:i:s');
$ateSql = $endDt->format('Y-m-d H:i:s');

// Busca info da estação (para título)
$stationStmt = $pdo->prepare('SELECT id, name, description FROM stations WHERE id = :id AND deleted_at IS NULL');
$stationStmt->execute([':id' => $idStation]);
$station = $stationStmt->fetch(PDO::FETCH_ASSOC);

$stationName = $station['name']        ?? ('Estação ' . $idStation);
$stationDesc = $station['description'] ?? '';

// Busca medições na tabela measurements.
// Para level_cm, também busca as colunas pré-computadas pelo filtro de cron (Issue #57).
if ($variavel === 'level_cm') {
    $sql = "
        SELECT timestamp, flag,
               `level_cm`       AS value,
               level_delta_cm,
               level_kalman_cm
        FROM measurements
        WHERE id_station = :id_station
          AND deleted_at IS NULL
          AND timestamp BETWEEN :de AND :ate
        ORDER BY timestamp ASC
    ";
} else {
    $sql = "
        SELECT timestamp, flag, `$variavel` AS value
        FROM measurements
        WHERE id_station = :id_station
          AND deleted_at IS NULL
          AND timestamp BETWEEN :de AND :ate
        ORDER BY timestamp ASC
    ";
}
$stmt = $pdo->prepare($sql);
$stmt->execute([
    ':id_station' => $idStation,
    ':de'         => $deSql,
    ':ate'        => $ateSql,
]);

$labels       = [];
$values       = [];
$valuesDelta  = []; // level_delta_cm — após filtro delta (null = rejeitado)
$valuesKalman = []; // level_kalman_cm — após Kalman (null = rejeitado)
$hasDbFiltered = false; // true se o cron já populou dados Kalman para este período

// Limites físicos da variável atual (null = sem limite definido)
$limMin = $varLimits[$variavel][0] ?? null;
$limMax = $varLimits[$variavel][1] ?? null;

$countOutliers = 0; // registros fora dos limites físicos
$countFlagged  = 0; // registros marcados como inválidos (flag='b')

while ($row = $stmt->fetch(PDO::FETCH_ASSOC)) {
    if ($row['value'] === null) {
        continue; // ignora leituras sem valor
    }

    // Exclui registros marcados manualmente como inválidos (flag='b')
    if (($row['flag'] ?? null) === 'b') {
        $countFlagged++;
        continue;
    }

    $v = (float)$row['value'];

    // Descarta valores fora dos limites físicos da variável (Issue #56)
    if ($limMin !== null && $v < $limMin) { $countOutliers++; continue; }
    if ($limMax !== null && $v > $limMax) { $countOutliers++; continue; }

    // Garante formato consistente de data/hora
    $ts = (new DateTime($row['timestamp']))->format('Y-m-d H:i:s');
    $labels[] = $ts;
    $values[] = $v;

    // Coleta séries pré-filtradas (Issue #57) para level_cm
    if ($variavel === 'level_cm') {
        $dv = isset($row['level_delta_cm'])  && $row['level_delta_cm']  !== null
              ? (float)$row['level_delta_cm']  : null;
        $kv = isset($row['level_kalman_cm']) && $row['level_kalman_cm'] !== null
              ? (float)$row['level_kalman_cm'] : null;
        $valuesDelta[]  = $dv;
        $valuesKalman[] = $kv;
        if (!$hasDbFiltered && $kv !== null) {
            $hasDbFiltered = true; // cron já processou pelo menos um ponto neste período
        }
    }
}

// MERGE overlay for precipitation_mm (Issue #135).
// Fetches satellite prec_mm for the same date range and aligns timestamps with
// the measurement series on a shared Y-axis (both in mm — single scale).
$mapMerge      = [];
$mergeExpanded = [];

if ($variavel === 'precipitation_mm') {
    $sqlMerge = "
        SELECT timestamp, prec_mm AS value
        FROM `merge`
        WHERE deleted_at IS NULL
          AND timestamp BETWEEN :de AND :ate
        ORDER BY timestamp ASC
    ";
    $stMerge = $pdo->prepare($sqlMerge);
    $stMerge->execute([':de' => $deSql, ':ate' => $ateSql]);
    while ($rowM = $stMerge->fetch(PDO::FETCH_ASSOC)) {
        if ($rowM['value'] === null) continue;
        $tsM = (new DateTime($rowM['timestamp']))->format('Y-m-d H:i:s');
        $mapMerge[$tsM] = (float)$rowM['value'];
    }

    if (!empty($mapMerge)) {
        // Expand to the union of measurement and MERGE timestamps so both
        // series share the same label array — null where a source has no data.
        $mapMeas       = array_combine($labels, $values);
        $allTs         = array_unique(array_merge($labels, array_keys($mapMerge)));
        sort($allTs);
        $labels        = $allTs;
        $values        = array_map(fn($ts) => $mapMeas[$ts]  ?? null, $allTs);
        $mergeExpanded = array_map(fn($ts) => $mapMerge[$ts] ?? null, $allTs);
    }
}

$tituloVariavel = $allowedVars[$variavel];
$periodoStr = $startDt->format('d/m/Y H:i') . ' até ' . $endDt->format('d/m/Y H:i');

// Limites do eixo Y baseados na série Kalman (Issue #61 — smart Y default).
// Quando hasDbFiltered=true os picos da série bruta não devem dominar a escala
// inicial; o eixo é inicializado com o intervalo da série Kalman × 1.3 de margem.
// Null quando não há dados Kalman (JS mantém auto-scale padrão do Chart.js).
$kalmanYMin = null;
$kalmanYMax = null;
if ($hasDbFiltered) {
    $nonNull = array_filter($valuesKalman, fn($v) => $v !== null);
    if (!empty($nonNull)) {
        $kMin = min($nonNull);
        $kMax = max($nonNull);
        $margin = ($kMax - $kMin) * 0.3;
        // Garante margem mínima de 5 cm para séries muito estáveis
        if ($margin < 5) $margin = 5;
        $kalmanYMin = max(0, $kMin - $margin);
        $kalmanYMax = $kMax + $margin;
    }
}

// Precipitation accumulation statistics (Issue #135).
// Computed server-side from the already-fetched arrays — no extra DB queries.
// All time windows are relative to the last timestamp present in the chart window.
$precipStats = null;
if ($variavel === 'precipitation_mm' && !empty($labels)) {
    $windowEndDt = new DateTime(end($labels));

    /**
     * Sums non-null values in $vals where the matching $lbs timestamp >= $from.
     *
     * @param string[]       $lbs  Label (timestamp) array
     * @param (float|null)[] $vals Aligned value array
     * @param DateTime       $from Inclusive lower bound
     * @return float Accumulated sum in mm
     */
    $sumFrom = function (array $lbs, array $vals, DateTime $from) use ($windowEndDt): float {
        $total = 0.0;
        foreach ($lbs as $i => $ts) {
            $dt = new DateTime($ts);
            if ($dt >= $from && $dt <= $windowEndDt && $vals[$i] !== null) {
                $total += (float)$vals[$i];
            }
        }
        return $total;
    };

    /**
     * Sums non-null values in $vals whose timestamp falls on calendar day $day.
     *
     * @param string[]       $lbs  Label array
     * @param (float|null)[] $vals Aligned value array
     * @param string         $day  Y-m-d string
     * @return float Accumulated sum in mm
     */
    $sumDay = function (array $lbs, array $vals, string $day): float {
        $total = 0.0;
        foreach ($lbs as $i => $ts) {
            if (substr($ts, 0, 10) === $day && $vals[$i] !== null) {
                $total += (float)$vals[$i];
            }
        }
        return $total;
    };

    /**
     * Sums non-null values in $vals whose timestamp falls in calendar month $ym.
     *
     * @param string[]       $lbs  Label array
     * @param (float|null)[] $vals Aligned value array
     * @param string         $ym   Y-m string
     * @return float Accumulated sum in mm
     */
    $sumMonth = function (array $lbs, array $vals, string $ym): float {
        $total = 0.0;
        foreach ($lbs as $i => $ts) {
            if (substr($ts, 0, 7) === $ym && $vals[$i] !== null) {
                $total += (float)$vals[$i];
            }
        }
        return $total;
    };

    $precipStats = [
        'window' => [
            'meas'  => array_sum(array_map(fn($v) => $v ?? 0.0, $values)),
            'merge' => array_sum(array_map(fn($v) => $v ?? 0.0, $mergeExpanded)),
        ],
        'h1' => [
            'meas'  => $sumFrom($labels, $values,        (clone $windowEndDt)->modify('-1 hour')),
            'merge' => $sumFrom($labels, $mergeExpanded, (clone $windowEndDt)->modify('-1 hour')),
        ],
        'h3' => [
            'meas'  => $sumFrom($labels, $values,        (clone $windowEndDt)->modify('-3 hours')),
            'merge' => $sumFrom($labels, $mergeExpanded, (clone $windowEndDt)->modify('-3 hours')),
        ],
        'h6' => [
            'meas'  => $sumFrom($labels, $values,        (clone $windowEndDt)->modify('-6 hours')),
            'merge' => $sumFrom($labels, $mergeExpanded, (clone $windowEndDt)->modify('-6 hours')),
        ],
        'day' => [
            'meas'  => $sumDay($labels, $values,        $windowEndDt->format('Y-m-d')),
            'merge' => $sumDay($labels, $mergeExpanded, $windowEndDt->format('Y-m-d')),
        ],
        'month' => [
            'meas'  => $sumMonth($labels, $values,        $windowEndDt->format('Y-m')),
            'merge' => $sumMonth($labels, $mergeExpanded, $windowEndDt->format('Y-m')),
        ],
    ];
}

// Parâmetros atuais (já devem existir no topo do view.php)
$idStation = $idStation ?? (int)($_GET['id_station'] ?? $_GET['idStation'] ?? 0);
$variavel  = $variavel  ?? ($_GET['var'] ?? '');
$deParam   = $_GET['de']  ?? ($deHtml  ?? '');
$ateParam  = $_GET['ate'] ?? ($ateHtml ?? '');
$modeParam = $_GET['mode'] ?? '';

// Monta query string para both.php com os mesmos filtros
$bothParams = [
    'id_station' => $idStation,
    'var'        => $variavel,
    'de'         => $deParam,
    'ate'        => $ateParam,
];

if ($modeParam !== '') {
    $bothParams['mode'] = $modeParam;
}

$bothUrl = 'both.php?' . http_build_query($bothParams);

?>

      <!--begin::App Main-->
      <main class="app-main">
        <!--begin::App Content Header-->
        <div class="app-content-header">
          <div class="container-fluid">
            <div class="row">
              <div class="col-sm-8">
                <h3 class="mb-0">
                  <?= htmlspecialchars($stationName) ?> — <?= htmlspecialchars($tituloVariavel) ?>
                </h3>
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
                      <h3 class="card-title mb-0 d-block w-100">Gráfico de medições</h3>
                      <div class="text-muted small">Período: <?= htmlspecialchars($periodoStr) ?></div>
                    </div>
                  </div>

                  <div class="card-body">

                    <?php if ($countOutliers > 0 || $countFlagged > 0): ?>
                      <div class="alert alert-warning alert-sm py-1 px-2 mb-2 small">
                        <i class="bi bi-exclamation-triangle-fill me-1"></i>
                        <?php if ($countOutliers > 0): ?>
                          <?= $countOutliers ?> leitura(s) fora dos limites físicos
                          (<?= htmlspecialchars($limMin) ?> – <?= htmlspecialchars($limMax) ?>)
                          ocultadas do gráfico.
                        <?php endif; ?>
                        <?php if ($countFlagged > 0): ?>
                          <?= $countFlagged ?> leitura(s) marcadas como inválidas (flag=b)
                          ocultadas do gráfico.
                        <?php endif; ?>
                        Os dados brutos permanecem no banco.
                      </div>
                    <?php endif; ?>

                    <!-- Filtro de datas -->
                    <form method="get"
                          class="row row-cols-1 row-cols-md-3 gx-2 gy-1 align-items-end mb-3">

                      <input type="hidden" name="id_station" value="<?= (int)$idStation ?>">
                      <input type="hidden" name="var" value="<?= htmlspecialchars($variavel) ?>">

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
                        <label class="form-label mb-1 small d-none d-md-block">&nbsp;</label>
                        <button type="submit" class="btn btn-primary btn-sm w-100">
                          Aplicar filtro
                        </button>
                      </div>
                    </form>


                    <?php if (empty($labels)): ?>
                      <div class="alert alert-warning mb-0">
                        Nenhum dado encontrado para este período, estação e variável.
                      </div>
                    <?php else: ?>

                                          <!-- Legenda das linhas -->
                    <div class="mb-2 text-center">
                      <small class="text-muted">Use scroll do mouse ou arraste (retângulo) para dar zoom.</small>
                    </div>

                    <!-- Container manda no tamanho, não o canvas -->
                    <div class="chart-container" style="position: relative; width: 100%; height: 320px;">
                      <canvas id="grafico"></canvas>
                    </div>

                    <div class="mt-3 mb-3 text-center text-dark small" id="estatisticas"></div>
                      <div class="mt-2 mt-md-0 text-center">

                        <!-- Botões de visibilidade das séries -->
                        <?php if ($hasDbFiltered): ?>
                        <!-- DB filtered: 3 botões independentes (Issue #57) -->
                        <button type="button" id="btnBruto"
                                class="btn btn-warning btn-sm me-1"
                                onclick="toggleSeries(0, this)">
                          Bruto
                        </button>
                        <button type="button" id="btnDelta"
                                class="btn btn-secondary btn-sm me-1"
                                onclick="toggleSeries(1, this)">
                          Δ Filtrado
                        </button>
                        <button type="button" id="btnKalmanDb"
                                class="btn btn-secondary btn-sm me-1"
                                onclick="toggleSeries(2, this)">
                          Kalman
                        </button>
                        <?php elseif (in_array($variavel, $kalmanVars)): ?>
                        <!-- Fallback JS Kalman (cron ainda não rodou para este período) -->
                        <button type="button" id="btnBrutoJs"
                                class="btn btn-warning btn-sm me-1"
                                onclick="toggleSeries(0, this)">
                          Bruto
                        </button>
                        <button type="button" id="btnKalmanJs"
                                class="btn btn-outline-secondary btn-sm me-1"
                                onclick="toggleKalman(this)">
                          <i class="bi bi-activity me-1"></i>Kalman
                        </button>
                        <?php endif; ?>

                        <!-- Botões de navegação -->
                        <button type="button" class="btn btn-outline-primary btn-sm me-1"
                                onclick="window.location.href='<?= htmlspecialchars($bothUrl, ENT_QUOTES, 'UTF-8') ?>'">
                          Ver precipitação
                        </button>
                        <button type="button" class="btn btn-outline-primary btn-sm me-1" onclick="chart.resetZoom()">
                          Redefinir zoom
                        </button>
                        <button type="button" class="btn btn-outline-primary btn-sm me-1" onclick="baixar()">
                          Baixar imagem
                        </button>
                        <button type="button" class="btn btn-outline-primary btn-sm" onclick="exportarCSV()">
                          Exportar CSV (visível)
                        </button>
                      </div>
                    <?php endif; ?>

                  </div>
                </div>

              </div>
            </div>

            <?php if ($precipStats): ?>
            <!-- Precipitation accumulation table (Issue #135) -->
            <div class="row mt-3">
              <div class="col-12 col-md-8 col-xl-6">
                <div class="card">
                  <div class="card-header">
                    <h3 class="card-title mb-0">
                      Precipitação acumulada
                      <span class="text-muted fw-normal small"> / Referência: fim da janela exibida (<?= htmlspecialchars($endDt->format('d/m/Y H:i')) ?> UTC)</span>
                    </h3>
                  </div>
                  <div class="card-body p-0">
                    <table class="table table-sm table-striped mb-0">
                      <thead>
                        <tr>
                          <th>Período</th>
                          <th class="text-end">
                            Estação-02<br>
                            <small class="text-muted fw-normal">medido (mm)</small>
                          </th>
                          <th class="text-end">
                            MERGE<br>
                            <small class="text-muted fw-normal">satélite (mm)</small>
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        <?php
                        $precRows = [
                            'Janela total'    => 'window',
                            'Última 1 hora'   => 'h1',
                            'Últimas 3 horas' => 'h3',
                            'Últimas 6 horas' => 'h6',
                            'Hoje'            => 'day',
                            'Este mês'        => 'month',
                        ];
                        $hasMergeData = !empty($mapMerge);
                        foreach ($precRows as $rowLabel => $key):
                            $measVal  = $precipStats[$key]['meas'];
                            $mergeVal = $precipStats[$key]['merge'];
                        ?>
                        <tr>
                          <td><?= htmlspecialchars($rowLabel) ?></td>
                          <td class="text-end"><?= number_format($measVal, 1) ?> mm</td>
                          <td class="text-end">
                            <?php if ($hasMergeData): ?>
                              <?= number_format($mergeVal, 1) ?> mm
                            <?php else: ?>
                              <span class="text-muted">—</span>
                            <?php endif; ?>
                          </td>
                        </tr>
                        <?php endforeach; ?>
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </div>
            <?php endif; ?>

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
  /**
   * Gráfico principal de medições (Issue #56).
   *
   * Melhorias implementadas:
   *   1. Limites físicos por variável já filtrados no PHP — dados brutos
   *      preservados no banco; apenas a exibição é filtrada.
   *   2. Estatísticas recalculadas sobre a janela de zoom visível
   *      (onZoomComplete / onPanComplete), não sobre todos os dados
   *      carregados — corrige distorção causada por outliers fora do zoom.
   *   3. Y-axis auto-escala com base nos dados limpos (sem suggestedMin/Max
   *      — a filtragem já ocorreu no PHP, então o auto-scale é confiável).
   */

  const labels  = <?= json_encode($labels) ?>;
  const valores = <?= json_encode($values, JSON_NUMERIC_CHECK) ?>;

  // Séries pré-filtradas pelo cron (Issue #57) — null = rejeitado/não processado
  const valoresDelta  = <?= json_encode($valuesDelta,  JSON_NUMERIC_CHECK) ?>;
  const valoresKalman = <?= json_encode($valuesKalman, JSON_NUMERIC_CHECK) ?>;
  const hasDbFiltered = <?= $hasDbFiltered ? 'true' : 'false' ?>;

  // MERGE satellite series (Issue #135) — populated only when var=precipitation_mm
  const serieMerge = <?= json_encode($mergeExpanded, JSON_NUMERIC_CHECK) ?>;
  const hasMerge   = Array.isArray(serieMerge) && serieMerge.some(v => v !== null);

  // Limites físicos da variável atual (vindos do PHP)
  const varLimMin = <?= json_encode($limMin) ?>;
  const varLimMax = <?= json_encode($limMax) ?>;

  let chart = null;

  /**
   * Calcula estatísticas descritivas apenas sobre os pontos visíveis
   * na janela de zoom atual do eixo X.
   *
   * @returns {Object|null} Objeto com media, mediana, moda, sigma, minimo, maximo
   */
  function calcularEstatisticasVisiveis() {
    const xScale = chart.scales.x;
    const xMin   = xScale.min;
    const xMax   = xScale.max;

    // Filtra apenas pontos cujo timestamp cai dentro da janela visível
    const vals = chart.data.labels
      .map((label, i) => ({ t: new Date(label).getTime(), v: chart.data.datasets[0].data[i] }))
      .filter(({ t, v }) => t >= xMin && t <= xMax && typeof v === 'number' && Number.isFinite(v))
      .map(({ v }) => v);

    if (!vals.length) return null;

    const soma  = vals.reduce((a, b) => a + b, 0);
    const media = soma / vals.length;

    const ordenados = [...vals].sort((a, b) => a - b);
    const meio      = Math.floor(ordenados.length / 2);
    const mediana   = ordenados.length % 2 === 0
      ? (ordenados[meio - 1] + ordenados[meio]) / 2
      : ordenados[meio];

    // Moda: valor com maior frequência
    const freq  = {};
    vals.forEach(v => { freq[v] = (freq[v] || 0) + 1; });
    const moda  = parseFloat(Object.keys(freq).reduce((a, b) => freq[a] > freq[b] ? a : b));

    const variancia = vals.reduce((acc, v) => acc + Math.pow(v - media, 2), 0) / vals.length;
    const sigma     = Math.sqrt(variancia);

    return {
      n:      vals.length,
      media,
      mediana,
      moda,
      sigma,
      minimo: Math.min(...vals),
      maximo: Math.max(...vals),
    };
  }

  /**
   * Atualiza o painel de estatísticas e as anotações do gráfico
   * com base nos dados atualmente visíveis.
   */
  function atualizarEstatisticas() {
    const stats = calcularEstatisticasVisiveis();
    const el    = document.getElementById('estatisticas');

    if (!stats) {
      el.innerHTML = '<div class="alert alert-info mb-0">Sem dados para calcular estatísticas.</div>';
      chart.options.plugins.annotation.annotations = {};
      chart.update('none');
      return;
    }

    el.innerHTML = `
      <div class="d-flex flex-wrap justify-content-center align-items-center gap-3 text-center mt-2">
        <div><strong>N</strong><br>${stats.n}</div>
        <div><strong>Média</strong><br>${stats.media.toFixed(2)}</div>
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

    // Monta anotações horizontais (média, min, max, ±1σ … ±3σ)
    const ann = {
      media: {
        type: 'line', yMin: stats.media, yMax: stats.media,
        borderColor: 'green', borderWidth: 1.5,
        label: { content: `Média: ${stats.media.toFixed(2)}`, display: true, position: 'start', backgroundColor: 'rgba(0,128,0,0.1)', color: 'green' }
      },
      min: {
        type: 'line', yMin: stats.minimo, yMax: stats.minimo,
        borderColor: 'blue', borderWidth: 1.5,
        label: { content: `Mín: ${stats.minimo.toFixed(2)}`, display: true, position: 'start', backgroundColor: 'rgba(0,0,255,0.1)', color: 'blue' }
      },
      max: {
        type: 'line', yMin: stats.maximo, yMax: stats.maximo,
        borderColor: 'red', borderWidth: 1.5,
        label: { content: `Máx: ${stats.maximo.toFixed(2)}`, display: true, position: 'start', backgroundColor: 'rgba(255,0,0,0.1)', color: 'red' }
      }
    };

    for (let i = 1; i <= 3; i++) {
      ann[`sigma_plus_${i}`] = {
        type: 'line', yMin: stats.media + i * stats.sigma, yMax: stats.media + i * stats.sigma,
        borderColor: '#ff9800', borderDash: [6, 6], borderWidth: 1,
        label: { content: `+${i}σ`, display: true, position: 'start', backgroundColor: 'rgba(255,152,0,0.1)', color: '#ff9800' }
      };
      ann[`sigma_minus_${i}`] = {
        type: 'line', yMin: stats.media - i * stats.sigma, yMax: stats.media - i * stats.sigma,
        borderColor: '#ff9800', borderDash: [6, 6], borderWidth: 1,
        label: { content: `-${i}σ`, display: true, position: 'start', backgroundColor: 'rgba(255,152,0,0.1)', color: '#ff9800' }
      };
    }

    chart.options.plugins.annotation.annotations = ann;
    chart.update('none'); // 'none' = sem animação, apenas redesenha
  }

  if (labels.length > 0) {
    const ctx = document.getElementById('grafico').getContext('2d');

    // Y-axis auto-escala com base nos dados já filtrados pelo PHP.
    // Quando hasDbFiltered=true (Issue #61) o eixo é inicializado com os limites
    // da série Kalman × 1.3 de margem para evitar que picos da série bruta
    // comprimam o nível real na base do gráfico.
    // O utilizador pode ver todos os dados (incluindo picos) com "Redefinir zoom"
    // ou duplo clique no gráfico.
    const yScaleOpts = {
      title: { display: true, text: '<?= addslashes($tituloVariavel) ?>' }
    };
    <?php if ($kalmanYMin !== null && $kalmanYMax !== null): ?>
    yScaleOpts.min = <?= json_encode($kalmanYMin) ?>;
    yScaleOpts.max = <?= json_encode($kalmanYMax) ?>;
    <?php endif; ?>

    // ── Datasets — ordem de renderização: raw → delta → kalman ──────────────
    // Raw: amarelo (background). Delta: laranja (camada intermediária).
    // Kalman: roxo (foreground, mais proeminente visualmente).
    // Chart.js renderiza datasets na ordem do array — o último fica por cima.
    const datasets = [{
      label: '<?= addslashes($tituloVariavel) ?>',
      data: valores,
      borderColor: '#eab308',               // amarelo — série bruta
      backgroundColor: 'rgba(234,179,8,0.10)',
      tension: 0.3,
      pointRadius: 2,
      pointHoverRadius: 4,
      borderWidth: 1.5,
      fill: true,
      spanGaps: true,                       // connect across nulls from MERGE timestamp expansion
    }];

    if (hasDbFiltered) {
      // Série delta: laranja tracejado — bruto pós-filtro de taxa de variação.
      // borderDash torna a série visualmente distinta do amarelo mesmo quando
      // se sobrepõem (dados limpos): amarelo sólido fino + laranja tracejado.
      datasets.push({
        label: '<?= addslashes($tituloVariavel) ?> (Δ filtrado)',
        data: valoresDelta,
        borderColor: '#f97316',             // laranja
        backgroundColor: 'rgba(249,115,22,0.08)',
        borderDash: [6, 4],                 // tracejado: 6px traço, 4px espaço
        tension: 0.3,
        pointRadius: 0,
        pointHoverRadius: 3,
        borderWidth: 2,
        fill: false,
        spanGaps: false,                    // interrompe linha em pontos rejeitados (null)
      });
      // Série Kalman: roxo sólido espesso — suavizado final (foreground).
      datasets.push({
        label: '<?= addslashes($tituloVariavel) ?> (Kalman)',
        data: valoresKalman,
        borderColor: '#8b5cf6',             // roxo
        backgroundColor: 'rgba(139,92,246,0.08)',
        tension: 0.4,
        pointRadius: 0,
        pointHoverRadius: 3,
        borderWidth: 2.5,
        fill: false,
        spanGaps: false,
      });
    }

    if (hasMerge) {
      // MERGE satellite estimates — same Y-axis as precipitation_mm (single shared scale)
      datasets.push({
        label: 'MERGE — prec_mm (satélite)',
        data: serieMerge,
        borderColor: '#0dcaf0',
        backgroundColor: 'rgba(13,202,240,0.15)',
        tension: 0.25,
        pointRadius: 0,
        pointHoverRadius: 3,
        borderWidth: 1.5,
        fill: true,
        spanGaps: true,
      });
    }

    chart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: datasets,
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        plugins: {
          legend: { position: 'top' },
          title: { display: true, text: 'Histórico de leituras' },
          zoom: {
            pan: { enabled: true, mode: 'xy',
              onPanComplete: () => atualizarEstatisticas()
            },
            zoom: {
              wheel: { enabled: true },
              pinch: { enabled: true },
              drag: { enabled: true },
              mode: 'xy',
              onZoomComplete: () => atualizarEstatisticas()
            }
          },
          annotation: { annotations: {} }
        },
        scales: {
          x: {
            type: 'time',
            time: {
              parser: 'yyyy-MM-dd HH:mm:ss',
              tooltipFormat: 'dd/MM/yyyy HH:mm',
              displayFormats: { hour: 'dd/MM HH:mm', minute: 'dd/MM HH:mm' }
            },
            title: { display: true, text: 'Data/Hora (UTC)' }
          },
          y: yScaleOpts
        }
      }
    });

    // Calcula estatísticas iniciais (janela completa)
    atualizarEstatisticas();

    // ── Botões de visibilidade de séries (Issue #57) ────────────────────────
    /**
     * Alterna a visibilidade de um dataset pelo índice.
     * Usa opacidade para indicar estado ativo/inativo — funciona com qualquer
     * estilo Bootstrap sem precisar trocar classes.
     *
     * @param {number}      datasetIdx - Índice do dataset no chart.data.datasets.
     * @param {HTMLElement} btn        - O elemento botão que disparou o evento.
     */
    function toggleSeries(datasetIdx, btn) {
      const vis = !chart.isDatasetVisible(datasetIdx);
      chart.setDatasetVisibility(datasetIdx, vis);
      chart.update('none');
      btn.style.opacity = vis ? '1' : '0.4';
    }
    window.toggleSeries = toggleSeries;

    // ── Filtro de Kalman JS (Issue #56 fallback) ─────────────────────────────
    // Mostrado apenas quando o cron ainda não populou level_kalman_cm (hasDbFiltered=false).
    // Quando hasDbFiltered=true, a série Kalman já foi adicionada via DB acima.
    <?php if (in_array($variavel, $kalmanVars) && !$hasDbFiltered): ?>
    /**
     * Aplica um filtro de Kalman escalar (1-D) à série de valores.
     *
     * Parâmetros padrão calibrados para level_cm (~1 min de amostragem):
     *   Q = variância do processo (ruído de transição de estado)
     *   R = variância da medição  (ruído do sensor)
     *
     * Para uma variável mais ruidosa (p.ex. nível com HC-SR04) use R maior.
     * Para variáveis mais estáveis (temperatura) reduza Q e R.
     *
     * Padrões calibrados para level_cm com amostragem ~1 min:
     *   Q=1, R=200 — rejeita bem picos esporádicos do HC-SR04 sem atrasar
     *               demais a resposta a mudanças reais de nível.
     *
     * @param {number[]} obs - Array de observações brutas
     * @param {number}   Q   - Process noise (padrão 1)
     * @param {number}   R   - Measurement noise (padrão 200)
     * @returns {number[]} Série suavizada
     */
    function kalman1D(obs, Q = 1, R = 200) {
      if (!obs.length) return [];
      let x = obs[0]; // estimativa inicial de estado
      let P = 1;      // estimativa inicial de covariância
      return obs.map(z => {
        // Predição
        const Pp = P + Q;
        // Atualização (ganho de Kalman)
        const K = Pp / (Pp + R);
        x = x + K * (z - x);
        P = (1 - K) * Pp;
        return x;
      });
    }

    // Índice do dataset Kalman (null = ainda não adicionado)
    let kalmanDatasetIndex = null;
    let kalmanVisible = false;

    /**
     * Alterna a visibilidade da série Kalman JS (fallback — só quando hasDbFiltered=false).
     * Na primeira ativação computa os valores filtrados e adiciona o dataset.
     *
     * @param {HTMLElement} btn - O elemento botão que disparou o evento.
     */
    function toggleKalman(btn) {
      if (kalmanDatasetIndex === null) {
        // Primeira vez: calcula Kalman e adiciona dataset
        const raw      = chart.data.datasets[0].data.map(v => (typeof v === 'number' ? v : parseFloat(v)));
        const smoothed = kalman1D(raw);

        chart.data.datasets.push({
          label: '<?= addslashes($tituloVariavel) ?> (Kalman)',
          data: smoothed,
          borderColor: '#8b5cf6',
          backgroundColor: 'rgba(139,92,246,0.08)',
          tension: 0.4,
          pointRadius: 0,
          pointHoverRadius: 3,
          fill: false,
          borderWidth: 2,
        });
        kalmanDatasetIndex = chart.data.datasets.length - 1;
        kalmanVisible = true;
        chart.update('none');
        btn.style.opacity = '1';
        btn.classList.replace('btn-outline-secondary', 'btn-secondary');
      } else {
        kalmanVisible = !kalmanVisible;
        chart.setDatasetVisibility(kalmanDatasetIndex, kalmanVisible);
        chart.update('none');
        btn.style.opacity = kalmanVisible ? '1' : '0.4';
        if (kalmanVisible) {
          btn.classList.replace('btn-outline-secondary', 'btn-secondary');
        } else {
          btn.classList.replace('btn-secondary', 'btn-outline-secondary');
        }
      }
    }
    window.toggleKalman = toggleKalman;
    <?php endif; // kalmanVars && !hasDbFiltered ?>

    // Exportações
    function baixar() {
      const link = document.createElement('a');
      link.href  = chart.toBase64Image();
      link.download = 'grafico-<?= addslashes($variavel) ?>.png';
      link.click();
    }
    window.baixar = baixar;

    function exportarCSV() {
      const xScale = chart.scales.x;
      const min    = xScale.min;
      const max    = xScale.max;

      const linhas = chart.data.labels.map((label, i) => {
        const valor     = chart.data.datasets[0].data[i];
        const timestamp = new Date(label).getTime();
        if (timestamp >= min && timestamp <= max) return `${label};${valor}`;
        return null;
      }).filter(l => l !== null);

      if (!linhas.length) { alert('Nenhum dado visível para exportar.'); return; }

      const blob = new Blob(['Data;Valor\n' + linhas.join('\n')], { type: 'text/csv;charset=utf-8;' });
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement('a');
      a.href     = url;
      a.download = 'medicoes-<?= addslashes($variavel) ?>.csv';
      a.click();
      URL.revokeObjectURL(url);
    }
    window.exportarCSV = exportarCSV;

  } else {
    function baixar()      { alert('Sem dados para baixar gráfico.'); }
    function exportarCSV() { alert('Sem dados para exportar.'); }
    window.baixar      = baixar;
    window.exportarCSV = exportarCSV;
  }
</script>



<?php require_once 'footer.php'; ?>
