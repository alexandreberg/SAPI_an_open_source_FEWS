-- =============================================================================
-- migration_issue108.sql
-- Issue #108 — Real-time LightGBM prediction pipeline
--
-- Creates two tables:
--   predictions       — one row per 5-min cron run per station
--   prediction_alerts — alert state-transition events (fired / cleared)
--
-- INSTRUCTIONS: Run each CREATE separately in phpMyAdmin.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- Table 1 of 2: predictions
-- Stores every 5-min prediction result for both Station-01 and Station-03.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `predictions` (
    `id`              INT UNSIGNED   NOT NULL AUTO_INCREMENT,
    `id_station`      TINYINT        NOT NULL COMMENT 'Station identifier (1 or 3)',
    `timestamp`       DATETIME       NOT NULL COMMENT 'UTC timestamp of the prediction run',
    `h_pred_30`       DECIMAL(6,2)   DEFAULT NULL COMMENT 'Level prediction at +30 min (cm)',
    `h_pred_60`       DECIMAL(6,2)   DEFAULT NULL COMMENT 'Level prediction at +60 min (cm)',
    `h_pred_90`       DECIMAL(6,2)   DEFAULT NULL COMMENT 'Level prediction at +90 min (cm)',
    `h_pred_120`      DECIMAL(6,2)   DEFAULT NULL COMMENT 'Level prediction at +120 min (cm)',
    `precip_rolling`  DECIMAL(7,3)   DEFAULT NULL COMMENT '6-hour rolling precipitation sum (mm)',
    `precip_source`   VARCHAR(16)    DEFAULT NULL COMMENT 'station02 or merge',
    `gate_active`     TINYINT(1)     NOT NULL DEFAULT 0 COMMENT '1 if precip gate is active',
    `raw_alert_level` VARCHAR(16)    NOT NULL DEFAULT 'none' COMMENT 'Alert level before debounce (none/atencao/alerta/inundacao)',
    `alert_level`     VARCHAR(16)    NOT NULL DEFAULT 'none' COMMENT 'Debounced alert level after DEBOUNCE_STEPS filter',
    `created_at`      DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    INDEX `idx_pred_station_ts` (`id_station`, `timestamp` DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- -----------------------------------------------------------------------------
-- Table 2 of 2: prediction_alerts
-- Records each alert state transition: fired (none→level) or cleared (level→none).
-- Intended for the alert log display and future notification triggers.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `prediction_alerts` (
    `id`                INT UNSIGNED  NOT NULL AUTO_INCREMENT,
    `id_station`        TINYINT       NOT NULL COMMENT 'Station identifier',
    `event_type`        VARCHAR(16)   NOT NULL COMMENT 'fired or cleared',
    `alert_level`       VARCHAR(16)   NOT NULL COMMENT 'Alert level at transition (none on cleared)',
    `timestamp`         DATETIME      NOT NULL COMMENT 'UTC timestamp of the transition',
    `consecutive_steps` TINYINT       NOT NULL DEFAULT 0 COMMENT 'Debounce counter value at transition',
    `precip_rolling`    DECIMAL(7,3)  DEFAULT NULL COMMENT '6-hour precip sum at transition (mm)',
    `notification_sent` TINYINT(1)    NOT NULL DEFAULT 0 COMMENT 'Reserved for future notification feature',
    `created_at`        DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    INDEX `idx_alert_station_ts` (`id_station`, `timestamp` DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
