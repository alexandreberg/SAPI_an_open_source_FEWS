<?php
/**
 * @file login.php
 * @brief Admin login page for the SAPI web interface.
 *
 * Standalone page — does NOT include header.php.
 * On successful authentication, regenerates the session ID to
 * prevent session-fixation attacks and redirects to admin area.
 *
 * @author Alexandre Nuernberg
 */

session_start();

// Already logged in — redirect
if (isset($_SESSION['user_id'])) {
    header('Location: admin/stations.php');
    exit;
}

// CSRF token for login form
if (empty($_SESSION['csrf_token'])) {
    $_SESSION['csrf_token'] = bin2hex(random_bytes(32));
}

require_once 'functions.php';

$error = '';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    // CSRF check
    if (!hash_equals($_SESSION['csrf_token'] ?? '', $_POST['csrf_token'] ?? '')) {
        $error = 'Requisição inválida. Recarregue a página e tente novamente.';
    } else {
        $email = trim($_POST['email'] ?? '');
        $pass  = $_POST['password'] ?? '';

        $stmt = db()->prepare('SELECT id, password_hash FROM users WHERE email = ? LIMIT 1');
        $stmt->execute([$email]);
        $user = $stmt->fetch();

        if ($user && password_verify($pass, $user['password_hash'])) {
            session_regenerate_id(true);
            $_SESSION['user_id'] = $user['id'];
            header('Location: admin/stations.php');
            exit;
        }

        // Generic error — do not reveal whether email or password is wrong
        $error = 'E-mail ou senha incorretos.';
    }
}
?>
<!doctype html>
<html lang="pt-BR">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>SAPI — Login</title>
    <link rel="stylesheet"
          href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.7/dist/css/bootstrap.min.css"
          crossorigin="anonymous" />
    <link rel="stylesheet"
          href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.13.1/font/bootstrap-icons.min.css"
          crossorigin="anonymous" />
    <style>
        body {
            background-color: #f4f6f9;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
        }
        .login-card {
            width: 100%;
            max-width: 400px;
        }
        .login-logo {
            text-align: center;
            margin-bottom: 1.5rem;
            font-size: 1.4rem;
            font-weight: 600;
            color: #495057;
        }
    </style>
</head>
<body>
<div class="login-card">
    <div class="login-logo">
        <i class="bi bi-water text-primary" style="font-size:2rem;"></i><br>
        SAPI — Área Administrativa
    </div>
    <div class="card shadow-sm">
        <div class="card-body p-4">
            <h5 class="card-title mb-4">Entrar</h5>

            <?php if ($error): ?>
                <div class="alert alert-danger" role="alert">
                    <?= htmlspecialchars($error) ?>
                </div>
            <?php endif; ?>

            <form method="post" action="login.php" novalidate>
                <input type="hidden" name="csrf_token"
                       value="<?= htmlspecialchars($_SESSION['csrf_token']) ?>">

                <div class="mb-3">
                    <label for="email" class="form-label">E-mail</label>
                    <input type="email" class="form-control" id="email" name="email"
                           autocomplete="email" required autofocus
                           value="<?= htmlspecialchars($_POST['email'] ?? '') ?>">
                </div>

                <div class="mb-4">
                    <label for="password" class="form-label">Senha</label>
                    <input type="password" class="form-control" id="password" name="password"
                           autocomplete="current-password" required>
                </div>

                <div class="d-grid">
                    <button type="submit" class="btn btn-primary">
                        <i class="bi bi-box-arrow-in-right me-1"></i> Entrar
                    </button>
                </div>
            </form>
        </div>
    </div>

    <p class="text-center text-muted small mt-3">
        <a href="index.php" class="text-muted">← Voltar ao painel público</a>
    </p>
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.7/dist/js/bootstrap.bundle.min.js"
        crossorigin="anonymous"></script>
</body>
</html>
