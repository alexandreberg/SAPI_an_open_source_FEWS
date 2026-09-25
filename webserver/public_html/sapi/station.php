<?php
/**
 * station.php — Página de seleção de variáveis de uma estação (Issue #56 Phase 2).
 *
 * Detecta automaticamente quais variáveis possuem dados para a estação
 * solicitada via uma única query agregada, sem necessidade de alterações
 * no schema do banco de dados.
 *
 * Parâmetros GET:
 *   id  (int) — ID da estação
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
require_once 'header.php';

$pdo = db();

// ── Parâmetro obrigatório ──────────────────────────────────────────────────
$idStation = isset($_GET['id']) ? (int)$_GET['id'] : 0;

if (!$idStation) {
    die('Estação não especificada (parâmetro id).');
}

// ── Dados da estação ───────────────────────────────────────────────────────
$stmtStation = $pdo->prepare(
    "SELECT id, name, description, lat, lon
     FROM stations
     WHERE id = :id AND deleted_at IS NULL"
);
$stmtStation->execute([':id' => $idStation]);
$station = $stmtStation->fetch(PDO::FETCH_ASSOC);

if (!$station) {
    die('Estação não encontrada ou removida.');
}

$stationName = $station['name']        ?? ('Estação ' . $idStation);
$stationDesc = $station['description'] ?? '';

// ── Mapa completo de variáveis (mesma whitelist de view.php) ──────────────
$allVars = [
    'level_cm'              => ['label' => 'Nível (cm)',               'icon' => 'bi-water',           'color' => 'primary'],
    'temperature_C'         => ['label' => 'Temperatura do ar (°C)',   'icon' => 'bi-thermometer-half', 'color' => 'danger'],
    'pressure'              => ['label' => 'Pressão (hPa)',             'icon' => 'bi-speedometer2',    'color' => 'secondary'],
    'humidity_percentual'   => ['label' => 'Umidade relativa (%)',      'icon' => 'bi-droplet-half',    'color' => 'info'],
    'surface_temperature_C' => ['label' => 'Temperatura superfície (°C)', 'icon' => 'bi-thermometer', 'color' => 'warning'],
    'precipitation_pulses'  => ['label' => 'Pulsos de precipitação',   'icon' => 'bi-cloud-rain',      'color' => 'info'],
    'precipitation_mm'      => ['label' => 'Precipitação (mm)',         'icon' => 'bi-cloud-rain-fill', 'color' => 'primary'],
    'bat_voltage'           => ['label' => 'Tensão bateria (V)',        'icon' => 'bi-battery-half',    'color' => 'success'],
    'panel_voltage'         => ['label' => 'Tensão painel (V)',         'icon' => 'bi-sun',             'color' => 'warning'],
    'rssi'                  => ['label' => 'RSSI',                     'icon' => 'bi-wifi',             'color' => 'secondary'],
    's_wifi'                => ['label' => 'Sinal Wi-Fi',              'icon' => 'bi-wifi-2',           'color' => 'secondary'],
    's_gsm'                 => ['label' => 'Sinal GSM',                'icon' => 'bi-signal',           'color' => 'secondary'],
];

// ── Detecta variáveis com dados (uma única query agregada) ─────────────────
// Conta registros não-nulos para cada coluna de medição nesta estação.
// Evita N queries separadas e não requer alterações no schema.
$selectClauses = [];
foreach (array_keys($allVars) as $col) {
    $selectClauses[] = "SUM(`{$col}` IS NOT NULL) AS `cnt_{$col}`";
}

$sqlDetect = "SELECT " . implode(', ', $selectClauses) . "
              FROM measurements
              WHERE id_station = :id AND deleted_at IS NULL";

$stmtDetect = $pdo->prepare($sqlDetect);
$stmtDetect->execute([':id' => $idStation]);
$counts = $stmtDetect->fetch(PDO::FETCH_ASSOC);

// Filtra apenas variáveis que têm ao menos 1 leitura
$activeVars = [];
foreach ($allVars as $col => $meta) {
    if (!empty($counts["cnt_{$col}"])) {
        $activeVars[$col] = $meta;
    }
}

// ── Última leitura (para exibir status na página) ─────────────────────────
// AND timestamp <= NOW() excludes corrupted future timestamps caused by
// 32-bit Unix overflow from firmware crashes (e.g. year 2106 readings).
$stmtLast = $pdo->prepare(
    "SELECT timestamp FROM measurements
     WHERE id_station = :id AND deleted_at IS NULL
       AND timestamp <= NOW()
     ORDER BY timestamp DESC LIMIT 1"
);
$stmtLast->execute([':id' => $idStation]);
$lastRow   = $stmtLast->fetch(PDO::FETCH_ASSOC);
$lastSeen  = $lastRow ? (new DateTime($lastRow['timestamp']))->format('d/m/Y H:i') : 'Sem dados';
?>

      <!--begin::App Main-->
      <main class="app-main">
        <!--begin::App Content Header-->
        <div class="app-content-header">
          <div class="container-fluid">
            <div class="row">
              <div class="col-sm-8">
                <h3 class="mb-0"><?= htmlspecialchars($stationName) ?></h3>
                <?php if ($stationDesc): ?>
                  <p class="text-muted mb-0 small"><?= htmlspecialchars($stationDesc) ?></p>
                <?php endif; ?>
              </div>
              <div class="col-sm-4 text-sm-end mt-2 mt-sm-0">
                <span class="badge text-bg-secondary">Estação #<?= $idStation ?></span>
              </div>
            </div>
          </div>
        </div>
        <!--end::App Content Header-->

        <!--begin::App Content-->
        <div class="app-content">
          <div class="container-fluid">

            <!-- Info da estação -->
            <div class="row mb-3">
              <div class="col-12">
                <div class="card">
                  <div class="card-body py-2">
                    <div class="d-flex flex-wrap gap-4 align-items-center small text-muted">
                      <?php if ($station['lat'] && $station['lon']): ?>
                        <span>
                          <i class="bi bi-geo-alt-fill me-1"></i>
                          <?= round($station['lat'], 5) ?>, <?= round($station['lon'], 5) ?>
                        </span>
                      <?php endif; ?>
                      <span>
                        <i class="bi bi-clock me-1"></i>
                        Última leitura: <strong><?= htmlspecialchars($lastSeen) ?></strong>
                      </span>
                      <span>
                        <i class="bi bi-bar-chart me-1"></i>
                        <?= count($activeVars) ?> variável(is) com dados
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Grade de variáveis disponíveis -->
            <?php if (empty($activeVars)): ?>
              <div class="alert alert-warning">
                Nenhuma leitura encontrada para esta estação.
              </div>
            <?php else: ?>
              <div class="row g-3">
                <?php foreach ($activeVars as $col => $meta): ?>
                  <div class="col-6 col-sm-4 col-md-3 col-xl-2">
                    <a href="/sapi/view.php?id_station=<?= $idStation ?>&var=<?= urlencode($col) ?>"
                       class="text-decoration-none">
                      <div class="card h-100 shadow-sm border-<?= htmlspecialchars($meta['color']) ?> border-opacity-50
                                  text-center p-3 var-card">
                        <div class="mb-2">
                          <i class="bi <?= htmlspecialchars($meta['icon']) ?> fs-2
                                      text-<?= htmlspecialchars($meta['color']) ?>"></i>
                        </div>
                        <div class="small fw-semibold text-body">
                          <?= htmlspecialchars($meta['label']) ?>
                        </div>
                      </div>
                    </a>
                  </div>
                <?php endforeach; ?>
              </div>

              <!-- Link rápido para comparação -->
              <div class="mt-4">
                <a href="/sapi/compare.php?stations[]=<?= $idStation ?>"
                   class="btn btn-outline-secondary btn-sm">
                  <i class="bi bi-bar-chart-line me-1"></i> Comparar com outras estações
                </a>
              </div>

              <!-- Foto da estação (Issue #67) —————————————————————————————
                   Arquivo: /assets/img/stations/station-{id}.jpg
                   A seção só é renderizada se o arquivo existir no servidor. -->
              <?php
              $photoFile = __DIR__ . "/assets/img/stations/station-{$idStation}.jpg";
              $photoUrl  = "/sapi/assets/img/stations/station-{$idStation}.jpg";
              ?>
              <?php if (file_exists($photoFile)): ?>
              <div class="mt-4">
                <h6 class="text-muted mb-2">
                  <i class="bi bi-camera me-1"></i> Foto da estação
                </h6>
                <img src="<?= htmlspecialchars($photoUrl) ?>"
                     alt="Foto da estação <?= htmlspecialchars($stationName) ?>"
                     class="img-fluid rounded shadow-sm"
                     style="max-width: 600px; width: 100%;">
              </div>
              <?php endif; ?>

            <?php endif; ?>

          </div>
        </div>
        <!--end::App Content-->
      </main>
      <!--end::App Main-->

<style>
/** Efeito hover nos cartões de variável */
.var-card {
  transition: transform 0.15s ease, box-shadow 0.15s ease;
  cursor: pointer;
}
.var-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 6px 16px rgba(0,0,0,0.12) !important;
}
</style>

<?php require_once 'footer.php'; ?>
