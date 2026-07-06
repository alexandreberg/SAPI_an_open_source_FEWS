-- ============================================================
-- SAPI Issue #52 — DB Migration
-- ============================================================
-- Creates tables: users, alert_rules, alert_contacts,
--   contact_stations, alert_state, alert_log
-- Adds column: alert_contacts.whatsapp_apikey
-- Seeds: alert_rules (stations 1/2/3), alert_state initial rows
--
-- HOW TO RUN:
--   1. BACKUP first:
--      phpMyAdmin → database <HOSTINGER_USER>_sapi
--      → Export → Quick → SQL → Go → Save the .sql file.
--   2. Open this file in phpMyAdmin → SQL tab → Execute.
--
-- Idempotent: uses IF NOT EXISTS / IF NOT EXISTS on ALTER.
-- Safe to re-run — duplicate INSERTs will be silently ignored
-- due to the INSERT IGNORE used for seed data.
-- ============================================================

USE <HOSTINGER_USER>_sapi;

-- Disable strict mode for this session (same as phpMyAdmin export header).
-- Required to allow ENUM DEFAULT values on MariaDB with STRICT_TRANS_TABLES.
SET SESSION sql_mode = 'NO_ENGINE_SUBSTITUTION';

-- --------------------------------------------------------
-- Table: users
-- Single admin user. Password stored as bcrypt hash.
-- --------------------------------------------------------

CREATE TABLE IF NOT EXISTS `users` (
    `id`            INT UNSIGNED    NOT NULL AUTO_INCREMENT,
    `email`         VARCHAR(100)    NOT NULL,
    `password_hash` VARCHAR(255)    NOT NULL,
    `created_at`    DATETIME        NOT NULL DEFAULT current_timestamp(),
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_users_email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------
-- Table: alert_rules
-- One row per station + variable + alert level.
-- --------------------------------------------------------

CREATE TABLE IF NOT EXISTS `alert_rules` (
    `id`         INT UNSIGNED    NOT NULL AUTO_INCREMENT,
    `id_station` INT UNSIGNED    NOT NULL,
    `variable`   VARCHAR(50)     NOT NULL,
    `level`      ENUM('attention','alert','flood') NOT NULL,
    `operator`   ENUM('>','>=','<','<=')           NOT NULL DEFAULT '>=',
    `threshold`  DECIMAL(8,2)    NOT NULL,
    `enabled`    TINYINT(1)      NOT NULL DEFAULT 1,
    `created_at` DATETIME        NOT NULL DEFAULT current_timestamp(),
    `deleted_at` DATETIME        DEFAULT NULL,
    PRIMARY KEY (`id`),
    CONSTRAINT `fk_alert_rules_station`
        FOREIGN KEY (`id_station`) REFERENCES `stations` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------
-- Table: alert_contacts
-- Persons who receive alert notifications.
-- --------------------------------------------------------

CREATE TABLE IF NOT EXISTS `alert_contacts` (
    `id`               INT UNSIGNED  NOT NULL AUTO_INCREMENT,
    `name`             VARCHAR(100)  NOT NULL,
    `email`            VARCHAR(150)  DEFAULT NULL,
    `whatsapp_number`  VARCHAR(20)   DEFAULT NULL,
    `whatsapp_apikey`  VARCHAR(20)   DEFAULT NULL,
    `enabled`          TINYINT(1)    NOT NULL DEFAULT 1,
    `created_at`       DATETIME      NOT NULL DEFAULT current_timestamp(),
    `deleted_at`       DATETIME      DEFAULT NULL,
    PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- If alert_contacts was already created without whatsapp_apikey, add it:
-- (MariaDB: this is a no-op if the column already exists in a fresh install)
SET @col_exists = (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME   = 'alert_contacts'
      AND COLUMN_NAME  = 'whatsapp_apikey'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE alert_contacts ADD COLUMN whatsapp_apikey VARCHAR(20) DEFAULT NULL AFTER whatsapp_number',
    'SELECT "whatsapp_apikey column already exists, skipping"'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- --------------------------------------------------------
-- Table: contact_stations
-- Junction: which contact receives alerts for which station.
-- --------------------------------------------------------

CREATE TABLE IF NOT EXISTS `contact_stations` (
    `id_contact` INT UNSIGNED NOT NULL,
    `id_station` INT UNSIGNED NOT NULL,
    PRIMARY KEY (`id_contact`, `id_station`),
    CONSTRAINT `fk_cs_contact`
        FOREIGN KEY (`id_contact`) REFERENCES `alert_contacts` (`id`),
    CONSTRAINT `fk_cs_station`
        FOREIGN KEY (`id_station`) REFERENCES `stations` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------
-- Table: alert_state
-- Current alert level per station+variable. Updated by cron.
-- --------------------------------------------------------

CREATE TABLE IF NOT EXISTS `alert_state` (
    `id_station`          INT UNSIGNED  NOT NULL,
    `variable`            VARCHAR(50)   NOT NULL,
    `current_level`       ENUM('none','attention','alert','flood') NOT NULL DEFAULT 'none',
    `entered_at`          DATETIME      DEFAULT NULL,
    `last_alert_sent_at`  DATETIME      DEFAULT NULL,
    `event_max_level`     ENUM('none','attention','alert','flood') NOT NULL DEFAULT 'none',
    PRIMARY KEY (`id_station`, `variable`),
    CONSTRAINT `fk_alert_state_station`
        FOREIGN KEY (`id_station`) REFERENCES `stations` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------
-- Table: alert_log
-- Immutable audit log of every notification sent.
-- --------------------------------------------------------

CREATE TABLE IF NOT EXISTS `alert_log` (
    `id`               BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `id_station`       INT UNSIGNED    NOT NULL,
    `variable`         VARCHAR(50)     NOT NULL,
    `level`            ENUM('none','attention','alert','flood') NOT NULL,
    `event_type`       ENUM('escalation','de-escalation','normalized','summary') NOT NULL,
    `value_at_trigger` DECIMAL(8,2)    DEFAULT NULL,
    `id_contact`       INT UNSIGNED    DEFAULT NULL,
    `channel`          ENUM('email','whatsapp') NOT NULL,
    `status`           ENUM('sent','failed') NOT NULL,
    `sent_at`          DATETIME        NOT NULL DEFAULT current_timestamp(),
    PRIMARY KEY (`id`),
    CONSTRAINT `fk_alert_log_station`
        FOREIGN KEY (`id_station`) REFERENCES `stations` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- SEED DATA: alert_rules (stations 1, 2, 3)
-- Adjust thresholds after field calibration.
-- INSERT IGNORE skips if rows already exist (re-run safe).
-- ============================================================

-- Station 1: level_cm
INSERT IGNORE INTO `alert_rules` (`id`, `id_station`, `variable`, `level`, `operator`, `threshold`) VALUES
    (1, 1, 'level_cm', 'attention', '>=', 80.00),
    (2, 1, 'level_cm', 'alert',     '>=', 120.00),
    (3, 1, 'level_cm', 'flood',     '>=', 160.00);

-- Station 2: precipitation_mm (accumulated last 60 min)
INSERT IGNORE INTO `alert_rules` (`id`, `id_station`, `variable`, `level`, `operator`, `threshold`) VALUES
    (4, 2, 'precipitation_mm', 'attention', '>=', 25.00),
    (5, 2, 'precipitation_mm', 'alert',     '>=', 50.00),
    (6, 2, 'precipitation_mm', 'flood',     '>=', 100.00);

-- Station 3: level_cm
INSERT IGNORE INTO `alert_rules` (`id`, `id_station`, `variable`, `level`, `operator`, `threshold`) VALUES
    (7, 3, 'level_cm', 'attention', '>=', 60.00),
    (8, 3, 'level_cm', 'alert',     '>=', 100.00),
    (9, 3, 'level_cm', 'flood',     '>=', 140.00);

-- ============================================================
-- SEED DATA: alert_state (initial rows, all 'none')
-- ============================================================

INSERT IGNORE INTO `alert_state` (`id_station`, `variable`) VALUES
    (1, 'level_cm'),
    (2, 'precipitation_mm'),
    (3, 'level_cm');

-- ============================================================
-- ADMIN USER
-- Run setup_admin.php (one-time script) to create the user.
-- OR manually:
--   INSERT INTO users (email, password_hash) VALUES
--     ('your@email.com', '$2y$12$...bcrypt_hash...');
-- Generate the hash with: php -r "echo password_hash('yourpassword', PASSWORD_DEFAULT);"
-- ============================================================
