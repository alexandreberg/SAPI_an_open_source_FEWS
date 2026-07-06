-- =============================================================================
-- migration_issue57.sql
-- Issue #57 — Delta filter + Kalman filter columns in measurements table
--
-- Adds two pre-computed filtered level columns:
--   level_delta_cm  — level_cm after hard-limit + delta (rate-of-change) filter
--   level_kalman_cm — level_delta_cm after 1-D Kalman smoother
--
-- Populated by cron/filter_level.php (runs every 5 min on Hostinger).
-- NULL means: row not yet processed, OR rejected by the delta filter.
--
-- INSTRUCTIONS: Run each query separately in phpMyAdmin.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- Query 1 of 2
-- Add level_delta_cm column (result after hard-limit + delta filter)
-- DECIMAL(6,2) supports sub-cm precision; NULL = not processed or rejected
-- -----------------------------------------------------------------------------
ALTER TABLE `measurements`
  ADD COLUMN `level_delta_cm` DECIMAL(6,2) DEFAULT NULL
  AFTER `level_cm`;


-- -----------------------------------------------------------------------------
-- Query 2 of 2
-- Add level_kalman_cm column (result after Kalman smoother on delta output)
-- NULL on rejected rows (mirrors level_delta_cm = NULL)
-- -----------------------------------------------------------------------------
ALTER TABLE `measurements`
  ADD COLUMN `level_kalman_cm` DECIMAL(6,2) DEFAULT NULL
  AFTER `level_delta_cm`;
