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
 */

/**
 * @brief API key authorised for the RPi prediction pipeline.
 *
 * The RPi sends this value in the X-API-Key request header.
 */
$PREDICT_API_KEY = 'REPLACE_WITH_OPENSSL_RAND_HEX_32_OUTPUT';
