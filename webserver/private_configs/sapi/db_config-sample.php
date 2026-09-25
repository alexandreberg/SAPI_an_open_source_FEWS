<?php
/**
 * @file db_config.php
 * @brief Database configuration and connection management
 * 
 * SECURITY: This file contains sensitive credentials.
 * 
 * CRITICAL SECURITY REQUIREMENTS:
 * 1. ⚠️ Must be stored OUTSIDE public_html directory
 *    Recommended location: /home/<HOSTINGER_USER>/private_configs/sapi/db_config.php
 * 2. Never commit to version control (add to .gitignore)
 * 3. Set restrictive file permissions: chmod 600
 * 4. Never echo/print credentials in production
 * 
 * @author Alexandre Nuernberg
 * @date 2025-12-29
 * @version 1.0.0
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

// ============================================================================
// CRITICAL SECURITY WARNING: 
// This file MUST be stored OUTSIDE the public_html directory!
// 
// Correct location:   /home/<HOSTINGER_USER>/private_configs/sapi/db_config.php
// WRONG location:     /home/username/public_html/sensordata/db_config.php
// 
// If this file is accessible via web browser, your credentials are exposed!
// Test: Try accessing https://yourdomain.com/path/to/db_config.php
// If you can see this file in browser, it's in the WRONG location!
// ============================================================================

// Database configuration
define('DB_HOST', 'localhost');           // Database host
define('DB_NAME', '<HOSTINGER_USER>_sapi');     // Database name
define('DB_USER', '<HOSTINGER_USER>_sapi');    // Database username
define('DB_PASS', 'xxxxxxxxxxxxxxxx');    // Database password
define('DB_CHARSET', 'utf8mb4');          // Character set

// API Key for authentication (use strong random key)
// Generate with: openssl rand -hex 32
$VALID_API_KEY = 'xxxxxxxxxxxxxxxxxxxxxxxxxxx'; // Replace with your actual API key

/**
 * @brief Create PDO database connection
 * @return PDO Database connection object
 * @throws PDOException If connection fails
 */
function getDatabaseConnection() {
    static $pdo = null;
    
    // Return existing connection if available (singleton pattern)
    if ($pdo !== null) {
        return $pdo;
    }
    
    try {
        $dsn = sprintf(
            'mysql:host=%s;dbname=%s;charset=%s',
            DB_HOST,
            DB_NAME,
            DB_CHARSET
        );
        
        $options = [
            PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,     // Throw exceptions on errors
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,           // Fetch as associative array
            PDO::ATTR_EMULATE_PREPARES   => false,                      // Use real prepared statements
            PDO::ATTR_PERSISTENT         => false,                      // Don't use persistent connections
            PDO::MYSQL_ATTR_INIT_COMMAND => "SET time_zone = '+00:00'" // Force UTC timezone
        ];
        
        $pdo = new PDO($dsn, DB_USER, DB_PASS, $options);
        
        return $pdo;
        
    } catch (PDOException $e) {
        // Log error securely (don't expose credentials)
        error_log('Database connection failed: ' . $e->getMessage());
        
        // Throw generic error to client
        throw new PDOException('Database connection failed. Please try again later.');
    }
}
