-- =============================================================================
-- Migration: M6 MLR production tables (Issue #120)
-- Creates predictions_m6 and prediction_alerts_m6 — mirrors of the M4 tables.
-- Run via Hostinger phpMyAdmin or SSH: mysql -u USER -p DBNAME < migration_m6_mlr.sql
-- =============================================================================

SET SESSION sql_mode = 'NO_ENGINE_SUBSTITUTION';

-- ---------------------------------------------------------------------------
-- predictions_m6 — one row per 5-min cron run per station
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS predictions_m6 (
    id               INT UNSIGNED     NOT NULL AUTO_INCREMENT,
    id_station       TINYINT UNSIGNED NOT NULL,
    timestamp        DATETIME         NOT NULL,
    h_pred_30        DECIMAL(6,2)     DEFAULT NULL,
    h_pred_60        DECIMAL(6,2)     DEFAULT NULL,
    h_pred_90        DECIMAL(6,2)     DEFAULT NULL,
    h_pred_120       DECIMAL(6,2)     DEFAULT NULL,
    precip_rolling   DECIMAL(8,3)     DEFAULT NULL COMMENT '6-hour rolling precipitation (mm)',
    precip_source    VARCHAR(20)      DEFAULT NULL COMMENT 'station02 | merge',
    gate_active      TINYINT(1)       NOT NULL DEFAULT 0,
    raw_alert_level  ENUM('none','atencao','alerta','inundacao') NOT NULL DEFAULT 'none',
    alert_level      ENUM('none','atencao','alerta','inundacao') NOT NULL DEFAULT 'none',
    created_at       TIMESTAMP        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_station_ts (id_station, timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='M6 MLR real-time prediction results (Issue #120)';

-- ---------------------------------------------------------------------------
-- prediction_alerts_m6 — alert state transitions only
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS prediction_alerts_m6 (
    id                INT UNSIGNED     NOT NULL AUTO_INCREMENT,
    id_station        TINYINT UNSIGNED NOT NULL,
    event_type        ENUM('fired','cleared') NOT NULL,
    alert_level       ENUM('none','atencao','alerta','inundacao') NOT NULL DEFAULT 'none',
    timestamp         DATETIME         NOT NULL,
    consecutive_steps TINYINT UNSIGNED NOT NULL DEFAULT 0,
    precip_rolling    DECIMAL(8,3)     DEFAULT NULL,
    notification_sent TINYINT(1)       NOT NULL DEFAULT 0,
    created_at        TIMESTAMP        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_station_ts (id_station, timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='M6 MLR alert state transitions (Issue #120)';
