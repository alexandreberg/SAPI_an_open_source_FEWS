<?php
/**
 * @file mail_config-sample.php
 * @brief SMTP credentials for Gmail-based email sending via PHPMailer.
 *
 * Copy this file to the Hostinger private_configs directory as mail_config.php
 * and fill in the Gmail App Password:
 *
 *   cp mail_config-sample.php /home/<HOSTINGER_USER>/private_configs/sapi/mail_config.php
 *   chmod 600 /home/<HOSTINGER_USER>/private_configs/sapi/mail_config.php
 *
 * How to generate a Gmail App Password:
 *   1. Log into alerta.ilha3d@gmail.com
 *   2. Google Account → Security → 2-Step Verification (enable if not already)
 *   3. Google Account → Security → App passwords
 *   4. Create one for "Mail" — copy the 16-char code (no spaces)
 *
 * NEVER commit the real mail_config.php — it is in .gitignore.
 *
 * Constants use the SAPI_SMTP_ prefix to avoid conflict with sapi.php
 * which defines SMTP_HOST for Hostinger's own relay (smtp.hostinger.com).
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

define('SAPI_SMTP_HOST',      'smtp.gmail.com');
define('SAPI_SMTP_PORT',      587);
define('SAPI_SMTP_USER',      'alerta.ilha3d@gmail.com');
define('SAPI_SMTP_PASS',      'xxxxxxxxxxxxxxxx');   // ← replace with App Password (16 chars, NO spaces)
define('SAPI_SMTP_FROM',      'alerta.ilha3d@gmail.com');
define('SAPI_SMTP_FROM_NAME', 'SAPI - Alertas');
