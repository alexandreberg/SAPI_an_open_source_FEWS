<?php
/**
 * @file stations.php
 * @brief Admin page: CRUD management of monitoring stations.
 *
 * Supported actions (via $_GET['action']):
 *   - (default)  : list all non-deleted stations
 *   - form        : show add/edit form (edit when $_GET['id'] is present)
 *   - save        : process add/edit POST
 *   - delete      : soft-delete a station (sets deleted_at)
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

$pageTitle  = 'Estações';
$activePage = 'stations';

$pdo    = db();
$action = $_GET['action'] ?? 'list';
$flash  = '';
$error  = '';

// ── DELETE ─────────────────────────────────────────────────────────────
if ($action === 'delete' && $_SERVER['REQUEST_METHOD'] === 'POST') {
    validateCsrf();
    $id = (int)($_POST['id'] ?? 0);
    if ($id > 0) {
        $pdo->prepare('UPDATE stations SET deleted_at = NOW() WHERE id = ?')->execute([$id]);
        $flash = 'Estação removida.';
    }
    $action = 'list';
}

// ── SAVE (add / edit) ──────────────────────────────────────────────────
if ($action === 'save' && $_SERVER['REQUEST_METHOD'] === 'POST') {
    validateCsrf();

    $id          = (int)($_POST['id'] ?? 0);
    $name        = trim($_POST['name']        ?? '');
    $description = trim($_POST['description'] ?? '');
    $lat         = trim($_POST['lat']         ?? '');
    $lon         = trim($_POST['lon']         ?? '');

    // Validation
    if ($name === '') {
        $error = 'O nome da estação é obrigatório.';
    } elseif (!is_numeric($lat) || !is_numeric($lon)) {
        $error = 'Latitude e longitude devem ser números.';
    } elseif ((float)$lat < -90 || (float)$lat > 90) {
        $error = 'Latitude inválida (deve estar entre -90 e 90).';
    } elseif ((float)$lon < -180 || (float)$lon > 180) {
        $error = 'Longitude inválida (deve estar entre -180 e 180).';
    }

    if ($error === '') {
        if ($id > 0) {
            // Edit
            $pdo->prepare(
                'UPDATE stations SET name=?, description=?, lat=?, lon=? WHERE id=?'
            )->execute([$name, $description ?: null, (float)$lat, (float)$lon, $id]);
            $flash = 'Estação atualizada.';
        } else {
            // Add
            $pdo->prepare(
                'INSERT INTO stations (name, description, lat, lon) VALUES (?,?,?,?)'
            )->execute([$name, $description ?: null, (float)$lat, (float)$lon]);
            $flash = 'Estação adicionada.';
        }
        $action = 'list';
    } else {
        $action = 'form'; // Re-display form with error
    }
}

// ── FORM data (pre-fill for edit) ─────────────────────────────────────
$editing = null;
if ($action === 'form') {
    $editId = (int)($_GET['id'] ?? $_POST['id'] ?? 0);
    if ($editId > 0) {
        $stmt = $pdo->prepare('SELECT * FROM stations WHERE id = ? AND deleted_at IS NULL');
        $stmt->execute([$editId]);
        $editing = $stmt->fetch();
        if (!$editing) {
            $action = 'list';
        }
    }
}

// ── LIST data ─────────────────────────────────────────────────────────
$stations = [];
if ($action === 'list') {
    $stations = $pdo->query(
        'SELECT id, name, description, lat, lon FROM stations WHERE deleted_at IS NULL ORDER BY id'
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
                    <i class="bi bi-plus-circle me-1"></i> Nova estação
                  </a>
                <?php else: ?>
                  <a href="stations.php" class="btn btn-secondary btn-sm">
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
                <h3 class="card-title">Estações cadastradas</h3>
              </div>
              <div class="card-body p-0">
                <table class="table table-striped table-hover mb-0">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Nome</th>
                      <th>Descrição</th>
                      <th>Lat</th>
                      <th>Lon</th>
                      <th>Ações</th>
                    </tr>
                  </thead>
                  <tbody>
                    <?php if (empty($stations)): ?>
                      <tr><td colspan="6" class="text-center text-muted py-4">Nenhuma estação cadastrada.</td></tr>
                    <?php else: ?>
                      <?php foreach ($stations as $s): ?>
                        <tr>
                          <td><?= $s['id'] ?></td>
                          <td><?= htmlspecialchars($s['name']) ?></td>
                          <td><?= htmlspecialchars($s['description'] ?? '—') ?></td>
                          <td><?= $s['lat'] ?></td>
                          <td><?= $s['lon'] ?></td>
                          <td>
                            <a href="?action=form&id=<?= $s['id'] ?>"
                               class="btn btn-sm btn-outline-primary me-1">
                              <i class="bi bi-pencil"></i>
                            </a>
                            <form method="post" action="?action=delete" class="d-inline"
                                  onsubmit="return confirm('Remover estação <?= htmlspecialchars(addslashes($s['name'])) ?>?')">
                              <input type="hidden" name="csrf_token"
                                     value="<?= htmlspecialchars($_SESSION['csrf_token']) ?>">
                              <input type="hidden" name="id" value="<?= $s['id'] ?>">
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
                  <?= $editing ? 'Editar estação' : 'Nova estação' ?>
                </h3>
              </div>
              <div class="card-body">
                <form method="post" action="?action=save" novalidate>
                  <input type="hidden" name="csrf_token"
                         value="<?= htmlspecialchars($_SESSION['csrf_token']) ?>">
                  <input type="hidden" name="id"
                         value="<?= (int)($editing['id'] ?? 0) ?>">

                  <div class="mb-3">
                    <label for="name" class="form-label">Nome <span class="text-danger">*</span></label>
                    <input type="text" class="form-control" id="name" name="name" maxlength="30"
                           required
                           value="<?= htmlspecialchars($_POST['name'] ?? $editing['name'] ?? '') ?>">
                  </div>

                  <div class="mb-3">
                    <label for="description" class="form-label">Descrição</label>
                    <input type="text" class="form-control" id="description" name="description"
                           maxlength="150"
                           value="<?= htmlspecialchars($_POST['description'] ?? $editing['description'] ?? '') ?>">
                  </div>

                  <div class="row">
                    <div class="col-md-6 mb-3">
                      <label for="lat" class="form-label">Latitude <span class="text-danger">*</span></label>
                      <input type="text" class="form-control" id="lat" name="lat"
                             placeholder="-27.430000" required
                             value="<?= htmlspecialchars($_POST['lat'] ?? $editing['lat'] ?? '') ?>">
                      <div class="form-text">Ex: -27.430925 (negativo para Sul)</div>
                    </div>
                    <div class="col-md-6 mb-3">
                      <label for="lon" class="form-label">Longitude <span class="text-danger">*</span></label>
                      <input type="text" class="form-control" id="lon" name="lon"
                             placeholder="-48.420000" required
                             value="<?= htmlspecialchars($_POST['lon'] ?? $editing['lon'] ?? '') ?>">
                      <div class="form-text">Ex: -48.421886 (negativo para Oeste)</div>
                    </div>
                  </div>

                  <div class="d-flex gap-2">
                    <button type="submit" class="btn btn-primary">
                      <i class="bi bi-check-circle me-1"></i>
                      <?= $editing ? 'Salvar alterações' : 'Adicionar estação' ?>
                    </button>
                    <a href="stations.php" class="btn btn-secondary">Cancelar</a>
                  </div>
                </form>
              </div>
            </div>
            <?php endif; ?>

          </div><!-- /.container-fluid -->
        </div><!-- /.app-content -->
      </main>

<?php require_once 'footer.php'; ?>
