<?php
/**
 * @file setup_admin.php
 * @brief One-time admin user creation tool.
 *
 * SECURITY: Delete this file immediately after use!
 * This script is intentionally NOT protected by session auth so it can
 * be used to bootstrap the first admin user.
 *
 * Usage:
 *   1. Upload to public_html/sapi/setup_admin.php on the server.
 *   2. Open https://sapi.ilha3d.com/sapi/setup_admin.php in the browser.
 *   3. Fill in email + password and submit.
 *   4. DELETE this file from the server.
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

require_once 'functions.php';

$message = '';
$success = false;
$alreadyHasUser = false;

// Check if users table already has rows (prevent re-seeding)
$count = db()->query('SELECT COUNT(*) FROM users')->fetchColumn();
if ($count > 0) {
    $alreadyHasUser = true;
}

if ($_SERVER['REQUEST_METHOD'] === 'POST' && !$alreadyHasUser) {
    $email    = trim($_POST['email'] ?? '');
    $password = $_POST['password'] ?? '';
    $confirm  = $_POST['password_confirm'] ?? '';

    if (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
        $message = 'E-mail inválido.';
    } elseif (strlen($password) < 8) {
        $message = 'A senha deve ter pelo menos 8 caracteres.';
    } elseif ($password !== $confirm) {
        $message = 'As senhas não conferem.';
    } else {
        $hash = password_hash($password, PASSWORD_DEFAULT);
        $stmt = db()->prepare('INSERT INTO users (email, password_hash) VALUES (?, ?)');
        $stmt->execute([$email, $hash]);
        $success = true;
        $message = 'Usuário admin criado com sucesso! DELETE este arquivo do servidor agora.';
    }
}
?>
<!doctype html>
<html lang="pt-BR">
<head>
    <meta charset="utf-8" />
    <title>SAPI — Criar usuário admin</title>
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <link rel="stylesheet"
          href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.7/dist/css/bootstrap.min.css"
          crossorigin="anonymous" />
    <style>
        body { background:#f4f6f9; display:flex; justify-content:center;
               align-items:center; min-height:100vh; }
        .card { max-width:420px; width:100%; }
    </style>
</head>
<body>
<div class="card shadow-sm">
    <div class="card-body p-4">
        <h5 class="card-title mb-3">Criar usuário admin (uso único)</h5>

        <?php if ($alreadyHasUser): ?>
            <div class="alert alert-warning">
                Já existe um usuário admin. Esta ferramenta não pode ser usada novamente.
                <a href="login.php">Ir para o login</a>.
            </div>
        <?php elseif ($success): ?>
            <div class="alert alert-success">
                <strong><?= htmlspecialchars($message) ?></strong>
            </div>
            <div class="alert alert-danger mt-2">
                ⚠️ <strong>DELETE este arquivo do servidor imediatamente!</strong><br>
                <code>public_html/sapi/setup_admin.php</code>
            </div>
        <?php else: ?>
            <?php if ($message): ?>
                <div class="alert alert-danger"><?= htmlspecialchars($message) ?></div>
            <?php endif; ?>
            <form method="post">
                <div class="mb-3">
                    <label for="email" class="form-label">E-mail do admin</label>
                    <input type="email" class="form-control" id="email" name="email" required
                           value="<?= htmlspecialchars($_POST['email'] ?? '') ?>" />
                </div>
                <div class="mb-3">
                    <label for="password" class="form-label">Senha (mínimo 8 caracteres)</label>
                    <input type="password" class="form-control" id="password" name="password" required />
                </div>
                <div class="mb-4">
                    <label for="password_confirm" class="form-label">Confirmar senha</label>
                    <input type="password" class="form-control" id="password_confirm"
                           name="password_confirm" required />
                </div>
                <button type="submit" class="btn btn-primary w-100">Criar usuário</button>
            </form>
        <?php endif; ?>
    </div>
</div>
</body>
</html>
