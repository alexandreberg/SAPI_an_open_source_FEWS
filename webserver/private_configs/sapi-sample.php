<?php
/**
 * @file sapi-sample.php
 * @brief Database credentials used by the web UI (functions.php → db())
 *
 * SECURITY: Copy this file to the correct location on the server and fill in
 * real credentials. NEVER commit the real file to version control.
 *
 * On Hostinger, the real file must be placed at:
 *   /home/<HOSTINGER_USER>/sapi.php
 *
 * Hostinger folder layout:
 *   /home/<HOSTINGER_USER>/
 *   ├── public_html  →  domains/ilha3d.com/public_html  (symlink)
 *   │   └── sapi/functions.php   (__DIR__ resolves via symlink to real path)
 *   ├── private_configs/sapi/db_config.php
 *   └── sapi.php                 ← THIS FILE goes here
 *
 * Path resolved by functions.php via:
 *   require_once dirname(__DIR__, 2) . '/sapi.php';
 * where __DIR__ = /home/<HOSTINGER_USER>/public_html/sapi
 * so dirname(__DIR__, 2) = /home/<HOSTINGER_USER>
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

// Database host
define('servidor', 'localhost');

// Database name
define('banco', '<HOSTINGER_USER>_sapi');

// Database username
define('usuario', '<HOSTINGER_USER>_sapi');

// Database password — REPLACE with your actual password
define('senhaDB', 'REPLACE_WITH_YOUR_PASSWORD');

// SMTP credentials for alert email sending
define('SMTP_HOST', 'smtp.hostinger.com');
define('SMTP_PORT', 587);
define('SMTP_USER', 'sapi@ilha3d.com');       // REPLACE with your Hostinger email
define('SMTP_PASS', 'REPLACE_WITH_YOUR_PASSWORD');
define('SMTP_FROM', 'sapi@ilha3d.com');
define('SMTP_FROM_NAME', 'SAPI - Alerta de Inundação');
