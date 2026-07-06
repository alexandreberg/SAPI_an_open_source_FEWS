-- =============================================================================
-- migration_issue110.sql
-- Issue #110 — Telegram + email notifications on predictive alert transitions
--
-- Adds telegram_chat_id to alert_contacts so each contact can optionally
-- receive Telegram messages from the server-side PHP pipeline (future use).
-- The RPi pipeline reads chat IDs from its own telegram_config.json file.
--
-- INSTRUCTIONS: Run in phpMyAdmin or via MySQL CLI before deploying the code.
-- =============================================================================

ALTER TABLE `alert_contacts`
    ADD COLUMN `telegram_chat_id` VARCHAR(64) DEFAULT NULL
        COMMENT 'Telegram chat or group ID for server-side notifications (optional)'
    AFTER `whatsapp_apikey`;
