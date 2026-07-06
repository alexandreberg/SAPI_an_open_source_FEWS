<?php
/**
 * @file alert_log.php
 * @brief Public read-only alert event history.
 *
 * Shows all alert_log entries filterable by station, level and date range.
 * Paginated at 50 rows per page.
 *
 * Differs from admin/alert_log.php:
 *  - No authentication required.
 *  - Contact name, channel and send status columns are hidden (private info).
 *
 * @author Alexandre Nuernberg
 */

require_once 'functions.php';

$pdo = db();

// ── Pagination ─────────────────────────────────────────────────────────
const LOG_PAGE_SIZE = 50;
$page = max(1, (int)($_GET['page'] ?? 1));

// ── Filters ────────────────────────────────────────────────────────────
$filterStation = (int)($_GET['station'] ?? 0);
$filterLevel   = $_GET['level'] ?? '';
$filterFrom    = $_GET['from']  ?? '';
$filterTo      = $_GET['to']    ?? '';

$validLevels = ['none', 'attention', 'alert', 'flood'];

$whereClauses = [];
$params       = [];

if ($filterStation > 0) {
    $whereClauses[] = 'al.id_station = ?';
    $params[]       = $filterStation;
}
if ($filterLevel !== '' && in_array($filterLevel, $validLevels, true)) {
    $whereClauses[] = 'al.level = ?';
    $params[]       = $filterLevel;
}
if ($filterFrom !== '') {
    $whereClauses[] = 'al.sent_at >= ?';
    $params[]       = $filterFrom . ' 00:00:00';
}
if ($filterTo !== '') {
    $whereClauses[] = 'al.sent_at <= ?';
    $params[]       = $filterTo . ' 23:59:59';
}

$whereSql = $whereClauses ? ('WHERE ' . implode(' AND ', $whereClauses)) : '';

// Count for pagination
$countStmt = $pdo->prepare("SELECT COUNT(*) FROM alert_log al $whereSql");
$countStmt->execute($params);
$totalRows  = (int)$countStmt->fetchColumn();
$totalPages = max(1, (int)ceil($totalRows / LOG_PAGE_SIZE));
$page       = min($page, $totalPages);
$offset     = ($page - 1) * LOG_PAGE_SIZE;

// Fetch page rows — contact/channel/status intentionally excluded
$paramsPage = array_merge($params, [LOG_PAGE_SIZE, $offset]);
$rowsStmt   = $pdo->prepare(
    "SELECT al.sent_at, s.name AS station_name,
            al.variable, al.level, al.event_type,
            al.value_at_trigger
     FROM alert_log al
     LEFT JOIN stations s ON s.id = al.id_station
     $whereSql
     ORDER BY al.sent_at DESC
     LIMIT ? OFFSET ?"
);
$rowsStmt->execute($paramsPage);
$rows = $rowsStmt->fetchAll();

// ── Stations for filter dropdown ───────────────────────────────────────
$stations = $pdo->query(
    'SELECT id, name FROM stations WHERE deleted_at IS NULL ORDER BY id'
)->fetchAll();

require_once 'header.php';
?>

      <main class="app-main">
        <div class="app-content-header">
          <div class="container-fluid">
            <div class="row align-items-center">
              <div class="col-sm-6">
                <h3 class="mb-0">Log de Alertas</h3>
              </div>
              <div class="col-sm-6 text-sm-end text-muted small">
                <?= $totalRows ?> registro(s) encontrado(s)
              </div>
            </div>
          </div>
        </div>

        <div class="app-content">
          <div class="container-fluid">

            <!-- ── Filters ──────────────────────────────────────────────── -->
            <div class="card mb-3">
              <div class="card-body">
                <form method="get" action="alert_log.php"
                      class="row g-2 align-items-end">
                  <input type="hidden" name="page" value="1">

                  <div class="col-md-3">
                    <label class="form-label">Estação</label>
                    <select name="station" class="form-select form-select-sm">
                      <option value="">Todas</option>
                      <?php foreach ($stations as $s): ?>
                        <option value="<?= $s['id'] ?>"
                                <?= $filterStation === (int)$s['id'] ? 'selected' : '' ?>>
                          <?= htmlspecialchars($s['name']) ?>
                        </option>
                      <?php endforeach; ?>
                    </select>
                  </div>

                  <div class="col-md-2">
                    <label class="form-label">Nível</label>
                    <select name="level" class="form-select form-select-sm">
                      <option value="">Todos</option>
                      <option value="attention" <?= $filterLevel === 'attention' ? 'selected' : '' ?>>Atenção</option>
                      <option value="alert"     <?= $filterLevel === 'alert'     ? 'selected' : '' ?>>Alerta</option>
                      <option value="flood"     <?= $filterLevel === 'flood'     ? 'selected' : '' ?>>Inundação</option>
                      <option value="none"      <?= $filterLevel === 'none'      ? 'selected' : '' ?>>Normalizado</option>
                    </select>
                  </div>

                  <div class="col-md-2">
                    <label class="form-label">De</label>
                    <input type="date" name="from" class="form-control form-control-sm"
                           value="<?= htmlspecialchars($filterFrom) ?>">
                  </div>

                  <div class="col-md-2">
                    <label class="form-label">Até</label>
                    <input type="date" name="to" class="form-control form-control-sm"
                           value="<?= htmlspecialchars($filterTo) ?>">
                  </div>

                  <div class="col-md-2 d-flex gap-2">
                    <button type="submit" class="btn btn-primary btn-sm">
                      <i class="bi bi-funnel me-1"></i> Filtrar
                    </button>
                    <a href="alert_log.php" class="btn btn-secondary btn-sm">
                      <i class="bi bi-x"></i>
                    </a>
                  </div>
                </form>
              </div>
            </div>

            <!-- ── Table ────────────────────────────────────────────────── -->
            <div class="card">
              <div class="card-body p-0">
                <table class="table table-striped table-hover table-sm mb-0">
                  <thead>
                    <tr>
                      <th>Data/hora (UTC)</th>
                      <th>Estação</th>
                      <th>Variável</th>
                      <th>Nível</th>
                      <th>Evento</th>
                      <th>Valor</th>
                    </tr>
                  </thead>
                  <tbody>
                    <?php if (empty($rows)): ?>
                      <tr>
                        <td colspan="6" class="text-center text-muted py-4">
                          Nenhum registro encontrado.
                        </td>
                      </tr>
                    <?php else: ?>
                      <?php foreach ($rows as $r): ?>
                        <?php
                        $levelStyle = match($r['level']) {
                            'attention' => 'background-color:#ffc107;color:#000;',
                            'alert'     => 'background-color:#fd7e14;color:#000;',
                            'flood'     => 'background-color:#dc3545;color:#fff;',
                            default     => 'background-color:#0eca7aff;color:#000;',
                        };
                        $levelLabel = match($r['level']) {
                            'attention' => 'Atenção',
                            'alert'     => 'Alerta',
                            'flood'     => 'Inundação',
                            default     => 'Normal',
                        };
                        $eventLabel = match($r['event_type']) {
                            'escalation'    => 'Escalada',
                            'de-escalation' => 'Redução',
                            'normalized'    => 'Normalizado',
                            'summary'       => 'Resumo',
                            default         => htmlspecialchars($r['event_type']),
                        };
                        ?>
                        <tr>
                          <td class="text-nowrap"><?= htmlspecialchars($r['sent_at']) ?></td>
                          <td><?= htmlspecialchars($r['station_name'] ?? '—') ?></td>
                          <td><?= htmlspecialchars($r['variable']) ?></td>
                          <td>
                            <span class="badge" style="<?= $levelStyle ?>">
                              <?= $levelLabel ?>
                            </span>
                          </td>
                          <td><?= $eventLabel ?></td>
                          <td>
                            <?= $r['value_at_trigger'] !== null
                                ? htmlspecialchars($r['value_at_trigger']) . ' cm'
                                : '—' ?>
                          </td>
                        </tr>
                      <?php endforeach; ?>
                    <?php endif; ?>
                  </tbody>
                </table>
              </div>

              <!-- Pagination -->
              <?php if ($totalPages > 1): ?>
              <div class="card-footer">
                <nav>
                  <ul class="pagination pagination-sm mb-0">
                    <?php
                    $baseUrl = '?' . http_build_query(array_filter([
                        'station' => $filterStation ?: null,
                        'level'   => $filterLevel   ?: null,
                        'from'    => $filterFrom     ?: null,
                        'to'      => $filterTo       ?: null,
                    ]));
                    $sep = strlen($baseUrl) > 1 ? '&' : '?';
                    ?>
                    <li class="page-item <?= $page <= 1 ? 'disabled' : '' ?>">
                      <a class="page-link"
                         href="<?= $baseUrl . $sep ?>page=<?= $page - 1 ?>">‹</a>
                    </li>
                    <?php for ($p = max(1, $page - 2); $p <= min($totalPages, $page + 2); $p++): ?>
                      <li class="page-item <?= $p === $page ? 'active' : '' ?>">
                        <a class="page-link"
                           href="<?= $baseUrl . $sep ?>page=<?= $p ?>"><?= $p ?></a>
                      </li>
                    <?php endfor; ?>
                    <li class="page-item <?= $page >= $totalPages ? 'disabled' : '' ?>">
                      <a class="page-link"
                         href="<?= $baseUrl . $sep ?>page=<?= $page + 1 ?>">›</a>
                    </li>
                  </ul>
                </nav>
              </div>
              <?php endif; ?>

            </div>

          </div>
        </div>
      </main>

<?php require_once 'footer.php'; ?>
