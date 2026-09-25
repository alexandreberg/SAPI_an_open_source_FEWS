<?php
/**
 * @file contacts.php
 * @brief Admin page: manage alert contacts and their station assignments.
 *
 * Supported actions (via $_GET['action']):
 *   - (default)  : list all non-deleted contacts with assigned stations
 *   - form        : show add/edit form
 *   - save        : process add/edit POST (also updates contact_stations)
 *   - toggle      : enable/disable a contact (POST)
 *   - delete      : soft-delete a contact (POST)
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

$pageTitle  = 'Contatos';
$activePage = 'contacts';

$pdo    = db();
$action = $_GET['action'] ?? 'list';
$flash  = '';
$error  = '';

// ── TOGGLE ────────────────────────────────────────────────────────────
if ($action === 'toggle' && $_SERVER['REQUEST_METHOD'] === 'POST') {
    validateCsrf();
    $id = (int)($_POST['id'] ?? 0);
    if ($id > 0) {
        $pdo->prepare('UPDATE alert_contacts SET enabled = NOT enabled WHERE id = ?')
            ->execute([$id]);
        $flash = 'Contato atualizado.';
    }
    $action = 'list';
}

// ── DELETE ─────────────────────────────────────────────────────────────
if ($action === 'delete' && $_SERVER['REQUEST_METHOD'] === 'POST') {
    validateCsrf();
    $id = (int)($_POST['id'] ?? 0);
    if ($id > 0) {
        $pdo->prepare('UPDATE alert_contacts SET deleted_at = NOW() WHERE id = ?')
            ->execute([$id]);
        $flash = 'Contato removido.';
    }
    $action = 'list';
}

// ── SAVE ───────────────────────────────────────────────────────────────
if ($action === 'save' && $_SERVER['REQUEST_METHOD'] === 'POST') {
    validateCsrf();

    $id              = (int)($_POST['id'] ?? 0);
    $name            = trim($_POST['name']            ?? '');
    $email           = trim($_POST['email']           ?? '');
    $whatsappNumber  = trim($_POST['whatsapp_number'] ?? '');
    $whatsappApikey  = trim($_POST['whatsapp_apikey'] ?? '');
    $telegramChatId  = trim($_POST['telegram_chat_id'] ?? '');
    $stationIds      = array_map('intval', (array)($_POST['stations'] ?? []));

    // Validation
    if ($name === '') {
        $error = 'O nome é obrigatório.';
    } elseif ($email !== '' && !filter_var($email, FILTER_VALIDATE_EMAIL)) {
        $error = 'E-mail inválido.';
    } elseif ($email === '' && $whatsappNumber === '' && $telegramChatId === '') {
        $error = 'Informe pelo menos um canal de notificação (e-mail, WhatsApp ou Telegram).';
    } elseif ($whatsappNumber !== '' && !preg_match('/^\+?[0-9]{7,20}$/', $whatsappNumber)) {
        $error = 'Número de WhatsApp inválido. Use formato E.164: +5548999999999';
    } elseif ($telegramChatId !== '' && !preg_match('/^-?[0-9]{5,20}$/', $telegramChatId)) {
        $error = 'Telegram Chat ID inválido. Use o ID numérico retornado pelo getUpdates (ex: -1001234567890).';
    }

    if ($error === '') {
        if ($id > 0) {
            $pdo->prepare(
                'UPDATE alert_contacts
                 SET name=?, email=?, whatsapp_number=?, whatsapp_apikey=?, telegram_chat_id=?
                 WHERE id=? AND deleted_at IS NULL'
            )->execute([
                $name,
                $email           ?: null,
                $whatsappNumber  ?: null,
                $whatsappApikey  ?: null,
                $telegramChatId  ?: null,
                $id,
            ]);
        } else {
            $pdo->prepare(
                'INSERT INTO alert_contacts (name, email, whatsapp_number, whatsapp_apikey, telegram_chat_id)
                 VALUES (?,?,?,?,?)'
            )->execute([
                $name,
                $email           ?: null,
                $whatsappNumber  ?: null,
                $whatsappApikey  ?: null,
                $telegramChatId  ?: null,
            ]);
            $id = (int)$pdo->lastInsertId();
        }

        // Sync contact_stations: delete all then re-insert selected
        $pdo->prepare('DELETE FROM contact_stations WHERE id_contact = ?')->execute([$id]);
        if (!empty($stationIds)) {
            $insStmt = $pdo->prepare(
                'INSERT IGNORE INTO contact_stations (id_contact, id_station) VALUES (?,?)'
            );
            foreach ($stationIds as $sid) {
                if ($sid > 0) {
                    $insStmt->execute([$id, $sid]);
                }
            }
        }

        $flash  = $id > 0 ? 'Contato atualizado.' : 'Contato adicionado.';
        $action = 'list';
    } else {
        $action = 'form';
    }
}

// ── All stations (for checkboxes) ─────────────────────────────────────
$stations = $pdo->query(
    'SELECT id, name FROM stations WHERE deleted_at IS NULL ORDER BY id'
)->fetchAll();

// ── FORM data ─────────────────────────────────────────────────────────
$editing            = null;
$editingStationIds  = [];

if ($action === 'form') {
    $editId = (int)($_GET['id'] ?? $_POST['id'] ?? 0);
    if ($editId > 0) {
        $stmt = $pdo->prepare(
            'SELECT * FROM alert_contacts WHERE id = ? AND deleted_at IS NULL'
        );
        $stmt->execute([$editId]);
        $editing = $stmt->fetch();
        if (!$editing) {
            $action = 'list';
        } else {
            // Load currently assigned stations
            $stmtCs = $pdo->prepare(
                'SELECT id_station FROM contact_stations WHERE id_contact = ?'
            );
            $stmtCs->execute([$editId]);
            $editingStationIds = array_column($stmtCs->fetchAll(), 'id_station');
        }
    }
    // On POST re-display, keep submitted station checkboxes
    if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['stations'])) {
        $editingStationIds = array_map('intval', (array)$_POST['stations']);
    }
}

// ── LIST data ─────────────────────────────────────────────────────────
$contacts = [];
if ($action === 'list') {
    $contacts = $pdo->query(
        'SELECT c.*,
                GROUP_CONCAT(s.name ORDER BY s.id SEPARATOR ", ") AS assigned_stations
         FROM alert_contacts c
         LEFT JOIN contact_stations cs ON cs.id_contact = c.id
         LEFT JOIN stations s ON s.id = cs.id_station AND s.deleted_at IS NULL
         WHERE c.deleted_at IS NULL
         GROUP BY c.id
         ORDER BY c.id'
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
                    <i class="bi bi-plus-circle me-1"></i> Novo contato
                  </a>
                <?php else: ?>
                  <a href="contacts.php" class="btn btn-secondary btn-sm">
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
                <h3 class="card-title">Contatos cadastrados</h3>
              </div>
              <div class="card-body p-0">
                <table class="table table-striped table-hover mb-0">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Nome</th>
                      <th>E-mail</th>
                      <th>WhatsApp</th>
                      <th>Telegram Chat ID</th>
                      <th>Estações</th>
                      <th>Ativo</th>
                      <th>Ações</th>
                    </tr>
                  </thead>
                  <tbody>
                    <?php if (empty($contacts)): ?>
                      <tr><td colspan="8" class="text-center text-muted py-4">
                        Nenhum contato cadastrado.
                      </td></tr>
                    <?php else: ?>
                      <?php foreach ($contacts as $c): ?>
                        <tr>
                          <td><?= $c['id'] ?></td>
                          <td><?= htmlspecialchars($c['name']) ?></td>
                          <td><?= htmlspecialchars($c['email'] ?? '—') ?></td>
                          <td>
                            <?php if ($c['whatsapp_number']): ?>
                              <?= htmlspecialchars($c['whatsapp_number']) ?>
                              <?php if ($c['whatsapp_apikey']): ?>
                                <span class="badge text-bg-success ms-1" title="API key configurada">
                                  <i class="bi bi-check"></i>
                                </span>
                              <?php else: ?>
                                <span class="badge text-bg-warning ms-1" title="API key não configurada">
                                  sem key
                                </span>
                              <?php endif; ?>
                            <?php else: ?>
                              —
                            <?php endif; ?>
                          </td>
                          <td>
                            <?php if (!empty($c['telegram_chat_id'])): ?>
                              <code><?= htmlspecialchars($c['telegram_chat_id']) ?></code>
                            <?php else: ?>
                              —
                            <?php endif; ?>
                          </td>
                          <td><?= htmlspecialchars($c['assigned_stations'] ?? '—') ?></td>
                          <td>
                            <form method="post" action="?action=toggle" class="d-inline">
                              <input type="hidden" name="csrf_token"
                                     value="<?= htmlspecialchars($_SESSION['csrf_token']) ?>">
                              <input type="hidden" name="id" value="<?= $c['id'] ?>">
                              <button type="submit"
                                      class="btn btn-sm <?= $c['enabled'] ? 'btn-success' : 'btn-secondary' ?>"
                                      title="<?= $c['enabled'] ? 'Desativar' : 'Ativar' ?>">
                                <i class="bi <?= $c['enabled'] ? 'bi-toggle-on' : 'bi-toggle-off' ?>"></i>
                              </button>
                            </form>
                          </td>
                          <td>
                            <a href="?action=form&id=<?= $c['id'] ?>"
                               class="btn btn-sm btn-outline-primary me-1">
                              <i class="bi bi-pencil"></i>
                            </a>
                            <form method="post" action="?action=delete" class="d-inline"
                                  onsubmit="return confirm('Remover contato <?= htmlspecialchars(addslashes($c['name'])) ?>?')">
                              <input type="hidden" name="csrf_token"
                                     value="<?= htmlspecialchars($_SESSION['csrf_token']) ?>">
                              <input type="hidden" name="id" value="<?= $c['id'] ?>">
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
                  <?= $editing ? 'Editar contato' : 'Novo contato' ?>
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
                    <input type="text" class="form-control" id="name" name="name" maxlength="100"
                           required
                           value="<?= htmlspecialchars($_POST['name'] ?? $editing['name'] ?? '') ?>">
                  </div>

                  <div class="row">
                    <div class="col-md-6 mb-3">
                      <label for="email" class="form-label">E-mail</label>
                      <input type="email" class="form-control" id="email" name="email"
                             maxlength="150"
                             value="<?= htmlspecialchars($_POST['email'] ?? $editing['email'] ?? '') ?>">
                    </div>
                    <div class="col-md-6 mb-3">
                      <label for="whatsapp_number" class="form-label">WhatsApp (E.164)</label>
                      <input type="text" class="form-control" id="whatsapp_number"
                             name="whatsapp_number" maxlength="20"
                             placeholder="+5548999999999"
                             value="<?= htmlspecialchars($_POST['whatsapp_number'] ?? $editing['whatsapp_number'] ?? '') ?>">
                    </div>
                  </div>

                  <div class="mb-3">
                    <label for="whatsapp_apikey" class="form-label">
                      CallMeBot API Key
                      <small class="text-muted">(obtenha ao ativar o CallMeBot pelo WhatsApp)</small>
                    </label>
                    <input type="text" class="form-control" id="whatsapp_apikey"
                           name="whatsapp_apikey" maxlength="20"
                           value="<?= htmlspecialchars($_POST['whatsapp_apikey'] ?? $editing['whatsapp_apikey'] ?? '') ?>">
                  </div>

                  <div class="mb-3">
                    <label for="telegram_chat_id" class="form-label">
                      Telegram Chat ID
                      <small class="text-muted">
                        (ID numérico do usuário ou grupo — obtenha via
                        <code>api.telegram.org/bot&lt;TOKEN&gt;/getUpdates</code>)
                      </small>
                    </label>
                    <input type="text" class="form-control" id="telegram_chat_id"
                           name="telegram_chat_id" maxlength="64"
                           placeholder="-1001234567890"
                           value="<?= htmlspecialchars($_POST['telegram_chat_id'] ?? $editing['telegram_chat_id'] ?? '') ?>">
                  </div>

                  <div class="mb-4">
                    <label class="form-label">Estações que este contato monitora</label>
                    <?php if (empty($stations)): ?>
                      <p class="text-muted small">Nenhuma estação cadastrada.</p>
                    <?php else: ?>
                      <div class="row">
                        <?php foreach ($stations as $s): ?>
                          <div class="col-sm-4">
                            <div class="form-check">
                              <input class="form-check-input" type="checkbox"
                                     name="stations[]"
                                     value="<?= $s['id'] ?>"
                                     id="sta_<?= $s['id'] ?>"
                                     <?= in_array((int)$s['id'], $editingStationIds, true) ? 'checked' : '' ?>>
                              <label class="form-check-label" for="sta_<?= $s['id'] ?>">
                                <?= htmlspecialchars($s['name']) ?>
                              </label>
                            </div>
                          </div>
                        <?php endforeach; ?>
                      </div>
                    <?php endif; ?>
                  </div>

                  <div class="d-flex gap-2">
                    <button type="submit" class="btn btn-primary">
                      <i class="bi bi-check-circle me-1"></i>
                      <?= $editing ? 'Salvar alterações' : 'Adicionar contato' ?>
                    </button>
                    <a href="contacts.php" class="btn btn-secondary">Cancelar</a>
                  </div>
                </form>
              </div>
            </div>
            <?php endif; ?>

          </div>
        </div>
      </main>

<?php require_once 'footer.php'; ?>
