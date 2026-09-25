<?php
/**
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
require_once 'header.php';

// Conexão PDO
$pdo = db();

/**
 * Página para visualizar a tabela `merge`
 * Plota prec_mm em função do timestamp
 * com filtro por intervalo de datas e por mode.
 */

// ------------------------
// Leitura de parâmetros GET
// ------------------------
$mode = isset($_GET['mode']) ? trim((string)$_GET['mode']) : '';

// Intervalo de datas (campo texto com flatpickr: Y-m-d H:i)
$de  = isset($_GET['de'])  ? trim((string)$_GET['de'])  : '';
$ate = isset($_GET['ate']) ? trim((string)$_GET['ate']) : '';

$now         = new DateTime('now');
$defaultEnd   = clone $now;
$defaultStart = (clone $now)->modify('-7 days');

// Tenta montar objetos DateTime a partir do GET
if ($de || $ate) {
    try {
        if ($de) {
            $deNorm  = str_replace('T', ' ', $de);
            $startDt = new DateTime($deNorm);
        } else {
            $startDt = $defaultStart;
        }

        if ($ate) {
            $ateNorm = str_replace('T', ' ', $ate);
            $endDt   = new DateTime($ateNorm);
        } else {
            $endDt = $defaultEnd;
        }

        if ($startDt > $endDt) {
            // garante que início <= fim
            [$startDt, $endDt] = [$endDt, $startDt];
        }
    } catch (Exception $e) {
        // Se formato vier bizarro, cai no padrão
        $startDt = $defaultStart;
        $endDt   = $defaultEnd;
    }
} else {
    $startDt = $defaultStart;
    $endDt   = $defaultEnd;
}

// Formatos para HTML (flatpickr) e SQL
$deHtml  = $startDt->format('Y-m-d H:i');
$ateHtml = $endDt->format('Y-m-d H:i');

$deSql  = $startDt->format('Y-m-d H:i:s');
$ateSql = $endDt->format('Y-m-d H:i:s');

// ------------------------
// Carrega lista de modes distintos
// ------------------------
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
    // Se não houver coluna mode ou algo der errado, ignora
    $modes = [];
}

// Se o mode enviado não existir na lista, considera "todos"
if ($mode !== '' && !in_array($mode, $modes, true)) {
    $mode = '';
}

// ------------------------
// Busca dados da tabela merge
// ------------------------
$sql = "
    SELECT timestamp, prec_mm AS value, mode
    FROM `merge`
    WHERE deleted_at IS NULL
      AND timestamp BETWEEN :de AND :ate
";
$params = [
    ':de'  => $deSql,
    ':ate' => $ateSql,
];

if ($mode !== '') {
    $sql .= " AND mode = :mode";
    $params[':mode'] = $mode;
}

$sql .= " ORDER BY timestamp ASC";

$st = $pdo->prepare($sql);
$st->execute($params);

$labels  = [];
$values  = [];
$modesRow = [];

while ($row = $st->fetch(PDO::FETCH_ASSOC)) {
    if ($row['value'] === null) {
        continue;
    }
    $ts = (new DateTime($row['timestamp']))->format('Y-m-d H:i:s');
    $labels[]   = $ts;
    $values[]   = (float)$row['value'];
    $modesRow[] = (string)$row['mode'];
}

$periodoStr = $startDt->format('d/m/Y H:i') . ' até ' . $endDt->format('d/m/Y H:i');
$labelModo  = $mode === '' ? 'Todos os modos' : ('Modo: ' . $mode);
?>
      <!--begin::App Main-->
      <main class="app-main">
        <!--begin::App Content Header-->
        <div class="app-content-header">
          <div class="container-fluid">
            <div class="row">
              <div class="col-sm-8">
                <h3 class="mb-0">
                  Tabela merge — Precipitação (prec_mm)
                </h3>
                <p class="text-muted mb-0 small">
                  <?= htmlspecialchars($periodoStr) ?> &middot; <?= htmlspecialchars($labelModo) ?>
                </p>
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
                      <h3 class="card-title mb-0 d-block w-100">Gráfico prec_mm x timestamp</h3>
                      <div class="text-muted small">Filtre por data e por modo de agregação.</div>
                    </div>
                  </div>

                  <div class="card-body">

                    <!-- Filtro de datas e mode -->
                    <form method="get"
                          class="row row-cols-1 row-cols-md-4 gx-2 gy-1 align-items-end mb-3">

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
                        <label for="mode" class="form-label mb-1 small">Mode</label>
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

                    <?php if (empty($labels)): ?>
                      <div class="alert alert-warning mb-0">
                        Nenhum dado encontrado na tabela <code>merge</code> para o período/modo informados.
                      </div>
                    <?php else: ?>

                      <div class="mb-2 text-center">
                        <small class="text-muted">
                          Use o scroll do mouse ou arraste no eixo X para dar zoom.
                        </small>
                      </div>

                      <div class="chart-container" style="position: relative; width: 100%; height: 360px;">
                        <canvas id="grafico_merge"></canvas>
                      </div>

                      <div class="mt-3 mb-3 text-center text-dark small" id="estatisticas_merge"></div>

                      <div class="mt-2 mt-md-0 text-center">
                        <button type="button" class="btn btn-outline-secondary btn-sm me-1" onclick="chartMerge.resetZoom()">
                          Redefinir zoom
                        </button>
                        <button type="button" class="btn btn-outline-primary btn-sm me-1" onclick="baixarMerge()">
                          Baixar imagem
                        </button>
                        <button type="button" class="btn btn-outline-success btn-sm" onclick="exportarCSVmerge()">
                          Exportar CSV (visível)
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
  const labelsMerge  = <?= json_encode($labels) ?>;
  const valoresMerge = <?= json_encode($values, JSON_NUMERIC_CHECK) ?>;

  let chartMerge = null;

  if (labelsMerge.length > 0) {
    const ctxMerge = document.getElementById('grafico_merge').getContext('2d');

    chartMerge = new Chart(ctxMerge, {
      type: 'line',
      data: {
        labels: labelsMerge,
        datasets: [{
          label: 'prec_mm (mm)',
          data: valoresMerge,
          borderColor: '#0d6efd',
          backgroundColor: 'rgba(13,110,253,0.2)',
          tension: 0.25,
          pointRadius: 0,
          pointHoverRadius: 3,
          fill: true,
        }]
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
              drag: { enabled: true },
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
            type: 'time',
            time: {
              parser: 'yyyy-MM-dd HH:mm:ss',
              tooltipFormat: 'dd/MM/yyyy HH:mm',
              displayFormats: {
                minute: 'dd/MM HH:mm',
                hour: 'dd/MM HH:mm',
                day: 'dd/MM',
              }
            },
            title: { display: true, text: 'Data/Hora' }
          },
          y: {
            title: { display: true, text: 'prec_mm (mm)' }
          }
        }
      }
    });

    function calcularEstatisticasGlobaisMerge() {
      const vals = chartMerge.data.datasets[0].data
        .map(v => (typeof v === 'number' ? v : parseFloat(v)))
        .filter(v => Number.isFinite(v));

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

    function atualizarEstatisticasGlobaisMerge() {
      const stats = calcularEstatisticasGlobaisMerge();
      const el = document.getElementById('estatisticas_merge');

      if (!stats) {
        el.innerHTML = '<div class="alert alert-info mb-0">Sem dados para calcular estatísticas.</div>';
        chartMerge.options.plugins.annotation.annotations = {};
        chartMerge.update();
        return;
      }

      el.innerHTML = `
        <div class="d-flex flex-wrap justify-content-center align-items-center gap-3 text-center mt-2">
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

      const m  = stats.media;
      const s  = stats.sigma;

      const ann = {
        mean: {
          type: 'line',
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
          yMin: m + 2 * s,
          yMax: m + 2 * s,
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
          yMin: m - 2 * s,
          yMax: m - 2 * s,
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
          yMin: m + 3 * s,
          yMax: m + 3 * s,
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
          yMin: m - 3 * s,
          yMax: m - 3 * s,
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

      chartMerge.options.plugins.annotation.annotations = ann;
      chartMerge.update();
    }


    atualizarEstatisticasGlobaisMerge();

    function baixarMerge() {
      const link = document.createElement('a');
      link.href = chartMerge.toBase64Image();
      link.download = 'grafico-merge.png';
      link.click();
    }
    window.baixarMerge = baixarMerge;

    function exportarCSVmerge() {
      if (!chartMerge || !chartMerge.data.labels.length) {
        alert('Sem dados na tabela merge para exportar.');
        return;
      }

      const linhas = ['timestamp;prec_mm'];

      chartMerge.data.labels.forEach((label, index) => {
        const v = chartMerge.data.datasets[0].data[index];
        linhas.push(`${label};${v}`);
      });

      const blob = new Blob([linhas.join('\n')], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'merge_prec_mm.csv';
      a.click();
      URL.revokeObjectURL(url);
    }

    window.exportarCSVmerge = exportarCSVmerge;

  } else {
    function baixarMerge()  { alert('Sem dados na tabela merge para baixar gráfico.'); }
    function exportarCSVmerge() { alert('Sem dados na tabela merge para exportar.'); }
    window.baixarMerge = baixarMerge;
    window.exportarCSVmerge = exportarCSVmerge;
  }
</script>

<?php require_once 'footer.php'; ?>
