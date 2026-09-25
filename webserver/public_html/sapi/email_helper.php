<?php
/**
 * @file email_helper.php
 * @brief Shared SMTP email sender using PHPMailer + Gmail SMTP (Issue #110).
 *
 * Included by any script that needs to send alert emails:
 *   - cron/check_alerts.php
 *   - public_html/sapi/api/predictions.php
 *   - cron/test_prediction_email.php
 *
 * Requires:
 *   - PHPMailer installed via Composer: composer install (run from AppTest/webserver/)
 *   - /home/<HOSTINGER_USER>/private_configs/sapi/mail_config.php with SMTP credentials
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

// ── Load SMTP credentials once ────────────────────────────────────────────────
// Uses SAPI_SMTP_* prefix to avoid conflict with sapi.php which defines SMTP_HOST
// for Hostinger's own SMTP relay (smtp.hostinger.com).
if (!defined('SAPI_SMTP_HOST')) {
    $mailConfigPath = '/home/<HOSTINGER_USER>/private_configs/sapi/mail_config.php';
    if (!file_exists($mailConfigPath)) {
        error_log('[email_helper] mail_config.php not found: ' . $mailConfigPath);
    } else {
        require_once $mailConfigPath;
    }
}

// ── Load PHPMailer autoloader ─────────────────────────────────────────────────
if (!class_exists('PHPMailer\PHPMailer\PHPMailer')) {
    // PHPMailer installed at the Hostinger account root via:
    //   composer install  (run from /home/<HOSTINGER_USER>/)
    $autoload = '/home/<HOSTINGER_USER>/vendor/autoload.php';
    if (!file_exists($autoload)) {
        error_log('[email_helper] PHPMailer not found: ' . $autoload
                  . ' — run: composer install from /home/<HOSTINGER_USER>/');
    } else {
        require_once $autoload;
    }
}

use PHPMailer\PHPMailer\PHPMailer;
use PHPMailer\PHPMailer\SMTP;
use PHPMailer\PHPMailer\Exception as MailException;

/**
 * @brief Sends an HTML email via Gmail SMTP using PHPMailer.
 *
 * Falls back to a logged error (no mail sent) if PHPMailer is unavailable
 * or credentials are missing — never throws.
 *
 * @param string      $to                  Recipient email address.
 * @param string      $subject             Email subject.
 * @param string      $htmlBody            Full HTML body string. If it references
 *                                         an embedded image, it must use
 *                                         `src="cid:$embeddedImageCid"`.
 * @param string      $fromName            Display name shown in the From header.
 *                                         Defaults to SMTP_FROM_NAME from mail_config.php.
 * @param string|null $embeddedImageBytes  Raw binary image bytes to embed inline
 *                                         (Issue #190 — must be attached per-message,
 *                                         never referenced by a mutable public URL,
 *                                         since a URL can be overwritten by a later
 *                                         alert before the recipient opens the email).
 * @param string      $embeddedImageCid    Content-ID referenced by the HTML body's
 *                                         `cid:` src. Required when
 *                                         $embeddedImageBytes is not null.
 * @return bool                            True if PHPMailer accepted the message, false otherwise.
 */
function sendEmailViaSMTP(
    string  $to,
    string  $subject,
    string  $htmlBody,
    string  $fromName = '',
    ?string $embeddedImageBytes = null,
    string  $embeddedImageCid = ''
): bool {
    if (!class_exists('PHPMailer\PHPMailer\PHPMailer')) {
        error_log('[email_helper] PHPMailer class not available — cannot send to ' . $to);
        return false;
    }

    if (!defined('SAPI_SMTP_HOST') || !defined('SAPI_SMTP_USER') || !defined('SAPI_SMTP_PASS')) {
        error_log('[email_helper] SMTP credentials not configured — cannot send to ' . $to);
        return false;
    }

    $displayName = $fromName !== '' ? $fromName : (defined('SAPI_SMTP_FROM_NAME') ? SAPI_SMTP_FROM_NAME : 'SAPI');

    try {
        $mail = new PHPMailer(true);

        $mail->isSMTP();
        $mail->Host       = SAPI_SMTP_HOST;
        $mail->SMTPAuth   = true;
        $mail->Username   = SAPI_SMTP_USER;
        $mail->Password   = SAPI_SMTP_PASS;
        $mail->SMTPSecure = PHPMailer::ENCRYPTION_STARTTLS;
        $mail->Port       = SAPI_SMTP_PORT;
        $mail->CharSet    = 'UTF-8';
        $mail->SMTPDebug  = SMTP::DEBUG_OFF;

        $mail->setFrom(SAPI_SMTP_FROM, $displayName);
        $mail->addAddress($to);

        if ($embeddedImageBytes !== null && $embeddedImageCid !== '') {
            $mail->addStringEmbeddedImage($embeddedImageBytes, $embeddedImageCid, 'chart.png', 'base64', 'image/png');
        }

        $mail->isHTML(true);
        $mail->Subject = $subject;
        $mail->Body    = $htmlBody;
        $mail->AltBody = strip_tags(str_replace(['<br>', '<br/>'], "\n", $htmlBody));

        $mail->send();
        return true;

    } catch (MailException $e) {
        error_log('[email_helper] PHPMailer error → ' . $to . ': ' . $e->getMessage());
        return false;
    }
}
