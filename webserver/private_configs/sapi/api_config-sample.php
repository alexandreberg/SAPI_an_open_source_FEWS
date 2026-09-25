<?php
/**
 * @file api_config-sample.php
 * @brief RPi prediction pipeline API key configuration (Issue #108).
 *
 * SECURITY: Copy this file to the production location and fill in the real key.
 * NEVER commit the real file to version control.
 *
 * Production location on Hostinger:
 *   /home/<HOSTINGER_USER>/private_configs/sapi/api_config.php
 *
 * Required by:
 *   /sapi/api/data.php        — GET sensor data for the RPi cron
 *   /sapi/api/predictions.php — POST prediction results from the RPi cron
 *
 * This key is SEPARATE from the IoT gateway key in db_config.php so the two
 * can be rotated independently.
 *
 * Generate a new key with:
 *   openssl rand -hex 32
 *
 * Store the same key on the RPi at:
 *   /home/ilha3d/SAPI/LightGBM_Production/config/api_key.txt  (chmod 600)
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

/**
 * @brief API key authorised for the RPi prediction pipeline.
 *
 * The RPi sends this value in the X-API-Key request header.
 */
$PREDICT_API_KEY = 'REPLACE_WITH_OPENSSL_RAND_HEX_32_OUTPUT';
