<?php
/**
 * @file alert_rules.php
 * @brief Admin page: manage alert rules per station.
 *
 * Supported actions (via $_GET['action']):
 *   - (default)  : list all non-deleted rules grouped by station
 *   - form        : show add/edit form
 *   - save        : process add/edit POST
 *   - toggle      : enable/disable a rule (POST)
 *   - delete      : soft-delete a rule (POST)
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

require_once '_auth.php';
require_once '../functions.php';

$pageTitle  = 'Regras de Alerta';
$activePage = 'alert_rules';

$pdo    = db();
$action = $_GET['action'] ?? 'list';
$flash  = '';
$error  = '';

/** Whitelist of variables that can be monitored. */
const ALERT_VARIABLES = [
    'level_cm'              => 'Nível (cm)',
    'precipitation_mm'      => 'Precipitação acum. 60 min (mm)',
    'temperature_C'         => 'Temperatura do ar (°C)',
    'surface_temperature_C' => 'Temperatura superfície (°C)',
    'bat_voltage'           => 'Tensão bateria (V)',
    'panel_voltage'         => 'Tensão painel (V)',
];

const ALERT_LEVELS = ['attention' => 'Atenção', 'alert' => 'Alerta', 'flood' => 'Inundação'];
const OPERATORS    = ['>=' => '≥ (maior ou igual)', '>' => '> (maior que)',
                      '<=' => '≤ (menor ou igual)', '<' => '< (menor que)'];

// ── TOGGLE enabled/disabled ────────────────────────────────────────────
if ($action === 'toggle' && $_SERVER['REQUEST_METHOD'] === 'POST') {
    validateCsrf();
    $id = (int)($_POST['id'] ?? 0);
    if ($id > 0) {
        $pdo->prepare('UPDATE alert_rules SET enabled = NOT enabled WHERE id = ?')->execute([$id]);
        $flash = 'Regra atualizada.';
    }
    $action = 'list';
}

// ── DELETE ─────────────────────────────────────────────────────────────
if ($action === 'delete' && $_SERVER['REQUEST_METHOD'] === 'POST') {
    validateCsrf();
    $id = (int)($_POST['id'] ?? 0);
    if ($id > 0) {
        $pdo->prepare('UPDATE alert_rules SET deleted_at = NOW() WHERE id = ?')->execute([$id]);
        $flash = 'Regra removida.';
    }
    $action = 'list';
}

// ── SAVE ───────────────────────────────────────────────────────────────
if ($action === 'save' && $_SERVER['REQUEST_METHOD'] === 'POST') {
    validateCsrf();

    $id         = (int)($_POST['id'] ?? 0);
    $idStation  = (int)($_POST['id_station'] ?? 0);
    $variable   = $_POST['variable'] ?? '';
    $level      = $_POST['level']    ?? '';
    $operator   = $_POST['operator'] ?? '>=';
    $threshold  = trim($_POST['threshold'] ?? '');

    // Validation
    if ($idStation <= 0) {
        $error = 'Selecione uma estação.';
    } elseif (!array_key_exists($variable, ALERT_VARIABLES)) {
        $error = 'Variável inválida.';
    } elseif (!array_key_exists($level, ALERT_LEVELS)) {
        $error = 'Nível inválido.';
    } elseif (!array_key_exists($operator, OPERATORS)) {
        $error = 'Operador inválido.';
    } elseif (!is_numeric($threshold)) {
        $error = 'O limiar deve ser um número.';
    } else {
        // Verify station exists
        $stmt = $pdo->prepare('SELECT id FROM stations WHERE id = ? AND deleted_at IS NULL');
        $stmt->execute([$idStation]);
        if (!$stmt->fetch()) {
            $error = 'Estação não encontrada.';
        }
    }

    if ($error === '') {
        if ($id > 0) {
            $pdo->prepare(
                'UPDATE alert_rules SET id_station=?, variable=?, level=?, operator=?, threshold=?
                 WHERE id=? AND deleted_at IS NULL'
            )->execute([$idStation, $variable, $level, $operator, (float)$threshold, $id]);
            $flash = 'Regra atualizada.';
        } else {
            $pdo->prepare(
                'INSERT INTO alert_rules (id_station, variable, level, operator, threshold)
                 VALUES (?,?,?,?,?)'
            )->execute([$idStation, $variable, $level, $operator, (float)$threshold]);
            $flash = 'Regra adicionada.';
        }
        $action = 'list';
    } else {
        $action = 'form';
    }
}

// ── FORM data ─────────────────────────────────────────────────────────
$editing  = null;
$stations = $pdo->query(
    'SELECT id, name FROM stations WHERE deleted_at IS NULL ORDER BY id'
)->fetchAll();

if ($action === 'form') {
    $editId = (int)($_GET['id'] ?? $_POST['id'] ?? 0);
    if ($editId > 0) {
        $stmt = $pdo->prepare('SELECT * FROM alert_rules WHERE id = ? AND deleted_at IS NULL');
        $stmt->execute([$editId]);
        $editing = $stmt->fetch();
        if (!$editing) {
            $action = 'list';
        }
    }
}

// ── LIST data ─────────────────────────────────────────────────────────
$rules = [];
if ($action === 'list') {
    $rules = $pdo->query(
        'SELECT ar.*, s.name AS station_name
         FROM alert_rules ar
         JOIN stations s ON s.id = ar.id_station
         WHERE ar.deleted_at IS NULL
         ORDER BY ar.id_station, ar.variable,
                  FIELD(ar.level,"attention","alert","flood")'
    )->fetchAll();
}

require_once 'header.php';
?>

      <main class="app-main">
        <div class="app-content-header">
          <div class="container-fluid">
            <div class="row align-items-center">
              <div class="col-sm-6"><h3 class="mb-0"><?= htmlspecialchars($pageTitle) ?></h3></div>
              <div class="col-sm-6 text-sm-end">
                <?php if ($action === 'list'): ?>
                  <a href="?action=form" class="btn btn-primary btn-sm">
                    <i class="bi bi-plus-circle me-1"></i> Nova regra
                  </a>
                <?php else: ?>
                  <a href="alert_rules.php" class="btn btn-secondary btn-sm">
                    <i class="bi bi-arrow-left me-1"></i> Voltar para a lista
                  </a>
                <?php endif; ?>
              </div>
            </div>
          </div>
        </div>

        <div class="app-content">
          <div class="container-fluid">

            <?php if ($flash): ?>
              <div class="alert alert-success alert-dismissible fade show">
                <?= htmlspecialchars($flash) ?>
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
              </div>
            <?php endif; ?>

            <?php if ($error): ?>
              <div class="alert alert-danger alert-dismissible fade show">
                <?= htmlspecialchars($error) ?>
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
              </div>
            <?php endif; ?>

            <?php if ($action === 'list'): ?>
            <!-- ── LIST ──────────────────────────────────────────────── -->
            <div class="card">
              <div class="card-header">
                <h3 class="card-title">Regras cadastradas</h3>
              </div>
              <div class="card-body p-0">
                <table class="table table-striped table-hover mb-0">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Estação</th>
                      <th>Variável</th>
                      <th>Nível</th>
                      <th>Condição</th>
                      <th>Limiar</th>
                      <th>Ativa</th>
                      <th>Ações</th>
                    </tr>
                  </thead>
                  <tbody>
                    <?php if (empty($rules)): ?>
                      <tr><td colspan="8" class="text-center text-muted py-4">
                        Nenhuma regra cadastrada.
                      </td></tr>
                    <?php else: ?>
                      <?php foreach ($rules as $r): ?>
                        <?php
                        $levelLabel = ALERT_LEVELS[$r['level']] ?? $r['level'];
                        $varLabel   = ALERT_VARIABLES[$r['variable']] ?? $r['variable'];
                        // 🟡 attention=yellow  🟠 alert=orange  🔴 flood=red  (all black text)
                        $levelStyle = match($r['level']) {
                            'attention' => 'background-color:#ffc107;color:#000;',
                            'alert'     => 'background-color:#fd7e14;color:#000;',
                            'flood'     => 'background-color:#dc3545;color:#000;',
                            default     => 'background-color:#6c757d;color:#000;',
                        };
                        ?>
                        <tr>
                          <td><?= $r['id'] ?></td>
                          <td><?= htmlspecialchars($r['station_name']) ?></td>
                          <td><?= htmlspecialchars($varLabel) ?></td>
                          <td>
                            <span class="badge" style="<?= $levelStyle ?>">
                              <?= htmlspecialchars($levelLabel) ?>
                            </span>
                          </td>
                          <td><?= htmlspecialchars($r['operator']) ?></td>
                          <td><?= $r['threshold'] ?></td>
                          <td>
                            <form method="post" action="?action=toggle" class="d-inline">
                              <input type="hidden" name="csrf_token"
                                     value="<?= htmlspecialchars($_SESSION['csrf_token']) ?>">
                              <input type="hidden" name="id" value="<?= $r['id'] ?>">
                              <button type="submit"
                                      class="btn btn-sm <?= $r['enabled'] ? 'btn-success' : 'btn-secondary' ?>"
                                      title="<?= $r['enabled'] ? 'Desativar' : 'Ativar' ?>">
                                <i class="bi <?= $r['enabled'] ? 'bi-toggle-on' : 'bi-toggle-off' ?>"></i>
                              </button>
                            </form>
                          </td>
                          <td>
                            <a href="?action=form&id=<?= $r['id'] ?>"
                               class="btn btn-sm btn-outline-primary me-1">
                              <i class="bi bi-pencil"></i>
                            </a>
                            <form method="post" action="?action=delete" class="d-inline"
                                  onsubmit="return confirm('Remover esta regra?')">
                              <input type="hidden" name="csrf_token"
                                     value="<?= htmlspecialchars($_SESSION['csrf_token']) ?>">
                              <input type="hidden" name="id" value="<?= $r['id'] ?>">
                              <button type="submit" class="btn btn-sm btn-outline-danger">
                                <i class="bi bi-trash"></i>
                              </button>
                            </form>
                          </td>
                        </tr>
                      <?php endforeach; ?>
                    <?php endif; ?>
                  </tbody>
                </table>
              </div>
            </div>

            <?php else: ?>
            <!-- ── ADD / EDIT FORM ────────────────────────────────────── -->
            <div class="card">
              <div class="card-header">
                <h3 class="card-title">
                  <?= $editing ? 'Editar regra' : 'Nova regra' ?>
                </h3>
              </div>
              <div class="card-body">
                <form method="post" action="?action=save" novalidate>
                  <input type="hidden" name="csrf_token"
                         value="<?= htmlspecialchars($_SESSION['csrf_token']) ?>">
                  <input type="hidden" name="id"
                         value="<?= (int)($editing['id'] ?? 0) ?>">

                  <div class="mb-3">
                    <label for="id_station" class="form-label">
                      Estação <span class="text-danger">*</span>
                    </label>
                    <select class="form-select" id="id_station" name="id_station" required>
                      <option value="">Selecione...</option>
                      <?php foreach ($stations as $s): ?>
                        <?php
                        $sel = (int)($_POST['id_station'] ?? $editing['id_station'] ?? 0);
                        ?>
                        <option value="<?= $s['id'] ?>"
                                <?= $sel === (int)$s['id'] ? 'selected' : '' ?>>
                          <?= htmlspecialchars($s['name']) ?>
                        </option>
                      <?php endforeach; ?>
                    </select>
                  </div>

                  <div class="mb-3">
                    <label for="variable" class="form-label">
                      Variável <span class="text-danger">*</span>
                    </label>
                    <select class="form-select" id="variable" name="variable" required>
                      <option value="">Selecione...</option>
                      <?php foreach (ALERT_VARIABLES as $val => $lbl): ?>
                        <?php
                        $sel = $_POST['variable'] ?? $editing['variable'] ?? '';
                        ?>
                        <option value="<?= $val ?>" <?= $sel === $val ? 'selected' : '' ?>>
                          <?= htmlspecialchars($lbl) ?>
                        </option>
                      <?php endforeach; ?>
                    </select>
                    <div class="form-text">
                      Para precipitação (estação-02), o cron acumula os últimos 60 minutos.
                    </div>
                  </div>

                  <div class="row">
                    <div class="col-md-4 mb-3">
                      <label for="level" class="form-label">
                        Nível <span class="text-danger">*</span>
                      </label>
                      <select class="form-select" id="level" name="level" required>
                        <option value="">Selecione...</option>
                        <?php foreach (ALERT_LEVELS as $val => $lbl): ?>
                          <?php $sel = $_POST['level'] ?? $editing['level'] ?? ''; ?>
                          <option value="<?= $val ?>" <?= $sel === $val ? 'selected' : '' ?>>
                            <?= htmlspecialchars($lbl) ?>
                          </option>
                        <?php endforeach; ?>
                      </select>
                    </div>

                    <div class="col-md-4 mb-3">
                      <label for="operator" class="form-label">
                        Operador <span class="text-danger">*</span>
                      </label>
                      <select class="form-select" id="operator" name="operator" required>
                        <?php foreach (OPERATORS as $val => $lbl): ?>
                          <?php $sel = $_POST['operator'] ?? $editing['operator'] ?? '>='; ?>
                          <option value="<?= htmlspecialchars($val) ?>"
                                  <?= $sel === $val ? 'selected' : '' ?>>
                            <?= htmlspecialchars($lbl) ?>
                          </option>
                        <?php endforeach; ?>
                      </select>
                    </div>

                    <div class="col-md-4 mb-3">
                      <label for="threshold" class="form-label">
                        Limiar <span class="text-danger">*</span>
                      </label>
                      <input type="number" step="0.01" class="form-control"
                             id="threshold" name="threshold" required
                             value="<?= htmlspecialchars($_POST['threshold'] ?? $editing['threshold'] ?? '') ?>">
                    </div>
                  </div>

                  <div class="d-flex gap-2">
                    <button type="submit" class="btn btn-primary">
                      <i class="bi bi-check-circle me-1"></i>
                      <?= $editing ? 'Salvar alterações' : 'Adicionar regra' ?>
                    </button>
                    <a href="alert_rules.php" class="btn btn-secondary">Cancelar</a>
                  </div>
                </form>
              </div>
            </div>
            <?php endif; ?>

          </div>
        </div>
      </main>

<?php require_once 'footer.php'; ?>
