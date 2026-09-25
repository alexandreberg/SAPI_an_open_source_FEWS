# SAPI Web Interface — Design Specification

**Issue:** #52
**Branch:** `feature/webserver-ui`
**Status:** Planning (pre-coding)
**Last updated:** 2026-03-14

---

## 1. Overview

The SAPI web interface runs on Hostinger shared hosting (PHP 7.4+ / MariaDB).
Framework: AdminLTE (Bootstrap 5) + Leaflet maps + Chart.js.

### Access model

| Area | Login required? |
|---|---|
| `index.php` — map with stations | No (public) |
| `view.php` — time-series charts | No (public) |
| `both.php` — level + precipitation chart | No (public) |
| `/admin/*` — station management, alert rules, contacts | Yes |
| `login.php` / `logout.php` | N/A |

One admin user. No self-registration. User is seeded once via SQL.

---

## 2. Database Schema Changes

### New tables (to be added via migration SQL)

#### `users`
```sql
CREATE TABLE users (
  id           INT UNSIGNED    NOT NULL AUTO_INCREMENT,
  email        VARCHAR(100)    NOT NULL UNIQUE,
  password_hash VARCHAR(255)   NOT NULL,
  created_at   DATETIME        NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (id)
);
```

#### `alert_rules`
One row per station + variable + alert level.
Different stations may have different thresholds for the same level.

```sql
CREATE TABLE alert_rules (
  id          INT UNSIGNED    NOT NULL AUTO_INCREMENT,
  id_station  INT UNSIGNED    NOT NULL,
  variable    VARCHAR(50)     NOT NULL,   -- e.g. 'level_cm', 'precipitation_mm'
  level       ENUM('attention','alert','flood') NOT NULL,
  operator    ENUM('>','>=','<','<=')     NOT NULL DEFAULT '>=',
  threshold   DECIMAL(8,2)    NOT NULL,
  enabled     TINYINT(1)      NOT NULL DEFAULT 1,
  created_at  DATETIME        NOT NULL DEFAULT current_timestamp(),
  deleted_at  DATETIME        DEFAULT NULL,
  PRIMARY KEY (id),
  FOREIGN KEY (id_station) REFERENCES stations(id)
);
```

Example seed data (adjust thresholds after field calibration):

| Station | Variable | Level | Threshold |
|---|---|---|---|
| 1 (level) | level_cm | attention | 80 |
| 1 (level) | level_cm | alert | 120 |
| 1 (level) | level_cm | flood | 160 |
| 2 (rain) | precipitation_mm | attention | 25 |
| 2 (rain) | precipitation_mm | alert | 50 |
| 2 (rain) | precipitation_mm | flood | 100 |
| 3 (level) | level_cm | attention | 60 |
| 3 (level) | level_cm | alert | 100 |
| 3 (level) | level_cm | flood | 140 |

> **Note for Station-02:** `precipitation_mm` in the alert context refers to the accumulated value over the last 60 minutes (sum of `precipitation_mm` rows WHERE timestamp >= NOW() - 1 HOUR). The cron must aggregate before comparing.

#### `alert_contacts`
```sql
CREATE TABLE alert_contacts (
  id               INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  name             VARCHAR(100)  NOT NULL,
  email            VARCHAR(150)  DEFAULT NULL,
  whatsapp_number  VARCHAR(20)   DEFAULT NULL,  -- E.164 format: +5548999999999
  enabled          TINYINT(1)    NOT NULL DEFAULT 1,
  created_at       DATETIME      NOT NULL DEFAULT current_timestamp(),
  deleted_at       DATETIME      DEFAULT NULL,
  PRIMARY KEY (id)
);
```

#### `contact_stations`
Junction table: which contact receives alerts for which station.

```sql
CREATE TABLE contact_stations (
  id_contact  INT UNSIGNED  NOT NULL,
  id_station  INT UNSIGNED  NOT NULL,
  PRIMARY KEY (id_contact, id_station),
  FOREIGN KEY (id_contact) REFERENCES alert_contacts(id),
  FOREIGN KEY (id_station) REFERENCES stations(id)
);
```

#### `alert_state`
Tracks the current alert level per station+variable. Updated by the cron job.

```sql
CREATE TABLE alert_state (
  id_station       INT UNSIGNED   NOT NULL,
  variable         VARCHAR(50)    NOT NULL,
  current_level    ENUM('none','attention','alert','flood') NOT NULL DEFAULT 'none',
  entered_at       DATETIME       DEFAULT NULL,
  last_alert_sent_at DATETIME     DEFAULT NULL,
  event_max_level  ENUM('none','attention','alert','flood') NOT NULL DEFAULT 'none',
  PRIMARY KEY (id_station, variable),
  FOREIGN KEY (id_station) REFERENCES stations(id)
);
```

#### `alert_log`
Immutable audit log of every notification sent. Useful for thesis documentation.

```sql
CREATE TABLE alert_log (
  id               BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  id_station       INT UNSIGNED    NOT NULL,
  variable         VARCHAR(50)     NOT NULL,
  level            ENUM('none','attention','alert','flood') NOT NULL,
  event_type       ENUM('escalation','de-escalation','normalized','summary') NOT NULL,
  value_at_trigger DECIMAL(8,2)    DEFAULT NULL,
  id_contact       INT UNSIGNED    DEFAULT NULL,
  channel          ENUM('email','whatsapp') NOT NULL,
  status           ENUM('sent','failed') NOT NULL,
  sent_at          DATETIME        NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (id),
  FOREIGN KEY (id_station) REFERENCES stations(id)
);
```

---

## 3. Alert State Machine

### Level hierarchy (ascending severity)
```
none  <  attention  <  alert  <  flood
```

### Recovery thresholds
Recovery is implicit: the thresholds for lower levels act as recovery thresholds for higher levels.

| Current level | Recovery condition | Transitions to |
|---|---|---|
| flood | value drops below alert threshold | alert |
| alert | value drops below attention threshold | attention |
| attention | value drops below attention threshold | none |

### Notification events

| Event | Trigger | Message sent |
|---|---|---|
| `escalation` | Level rises (none→attention, attention→alert, alert→flood) | "Level X reached: value Y cm" |
| `de-escalation` | Level drops (flood→alert, alert→attention) | "Returning to level X" |
| `normalized` | Level drops to none | "Water level normalized" |
| `summary` | After `normalized` | "Event summary: max level reached was FLOOD at HH:MM" |

### Cron timing
Hostinger crontab: `* * * * *` (every 1 minute)
```
* * * * * /usr/bin/php /home/<HOSTINGER_USER>/cron/check_alerts.php
```

### Outlier filtering (Phase 2 — future)
Not implemented in Phase 1. Future approach: only trigger alert if the last N consecutive readings all exceed the threshold.

---

## 4. Notification Channels

### Email
- Transport: SMTP via Hostinger email account (`sapi@ilha3d.com`)
- Credentials: defined in `private_configs/sapi.php` (SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS)
- Library: PHP `mail()` with SMTP headers OR PHPMailer (to be decided during implementation)
- Email body: HTML, includes current value, level, station name, and link to chart

### WhatsApp (CallMeBot)
- Contact must opt-in once: send "I allow callmebot to send me messages" to +34 644 44 78 85 on WhatsApp
- After opt-in, CallMeBot sends an API key to the contact's number
- That API key is stored in `alert_contacts.whatsapp_apikey` (additional column)
- Sending: HTTP GET to `https://api.callmebot.com/whatsapp.php?phone=PHONE&text=MESSAGE&apikey=KEY`
- Limitation: free tier, low volume — suitable for a research system with ~10 contacts

**Schema addition for WhatsApp:**
```sql
ALTER TABLE alert_contacts ADD COLUMN whatsapp_apikey VARCHAR(20) DEFAULT NULL AFTER whatsapp_number;
```

> **Design principle:** the notification code is channel-agnostic. A `sendAlert($contact, $message)` function dispatches to email and/or WhatsApp depending on what is configured for that contact.

---

## 5. Admin Pages (protected by session)

All under `admin/` subdirectory. Each page checks for valid session at top; redirects to `login.php` if not authenticated.

| Page | Purpose |
|---|---|
| `admin/stations.php` | List, add, edit stations (name, description, lat, lon) |
| `admin/alert_rules.php` | List, add, edit, enable/disable alert rules per station |
| `admin/contacts.php` | List, add, edit contacts; assign to stations |
| `admin/alert_log.php` | View alert history (read-only) |

---

## 6. Hostinger Server Layout

The actual directory structure on the Hostinger server is:

```
/home/<HOSTINGER_USER>/
├── domains/ilha3d.com/public_html/
│   └── sapi/
│       ├── *.php               ← web UI files
│       └── sensorData/
│           └── receive-data.php
├── public_html  →  domains/ilha3d.com/public_html   (symlink)
├── private_configs/
│   └── sapi/
│       └── db_config.php       ← credentials for receive-data.php (NOT in git)
├── cron/
│   └── check_alerts.php        ← NOT web-accessible (outside public_html)
└── sapi.php                    ← credentials for web UI/functions.php (NOT in git)
```

The cron scripts live at `/home/<HOSTINGER_USER>/cron/` — a sibling of `public_html` and `private_configs`, **never inside the web root**. This prevents anyone from triggering `check_alerts.php` via HTTP, avoiding alert spam and DB probing without needing `.htaccess` protection.

`functions.php` resolves its credential file via:
```php
require_once dirname(__DIR__, 2) . '/sapi.php';
// __DIR__ = /home/<HOSTINGER_USER>/public_html/sapi
// dirname x2 = /home/<HOSTINGER_USER>
// result: /home/<HOSTINGER_USER>/sapi.php
```

---

## 7. File Structure (this repository)

```
webserver/
├── .gitignore
├── database/schema_20260313.sql         ← current DB schema snapshot
│
├── public_html/
│   └── sapi/
│       ├── index.php                   ← public: map
│       ├── view.php                    ← public: time-series chart
│       ├── both.php                    ← public: level + precipitation chart
│       ├── merge.php                   ← public: MERGE overlay chart
│       ├── merge_tool.php              ← public: MERGE data tool
│       ├── header.php                  ← shared layout header
│       ├── footer.php                  ← shared layout footer
│       ├── functions.php               ← db() helper
│       ├── login.php                   ← [TO CREATE] login form
│       ├── logout.php                  ← [TO CREATE] session destroy
│       ├── admin/
│       │   ├── stations.php            ← [TO CREATE]
│       │   ├── alert_rules.php         ← [TO CREATE]
│       │   ├── contacts.php            ← [TO CREATE]
│       │   └── alert_log.php           ← [TO CREATE]
│       └── sensorData/
│           ├── receive-data.php        ← IoT data ingestion endpoint
│           ├── composer.json
│           ├── composer.lock
│           └── vendor/                 ← .gitignored (run: composer install)
│
├── private_configs/
│   ├── sapi-sample.php                 ← template for /home/<HOSTINGER_USER>/sapi.php
│   └── sapi/
│       └── db_config-sample.php        ← template for db_config.php (IoT endpoint)
│
└── cron/                               ← maps to /home/<HOSTINGER_USER>/cron/ (outside web root)
    ├── check_alerts.php                ← [TO CREATE] main alert cron
    ├── alerta_sensor-01.php            ← legacy cron (old system, reference only)
    └── credenciais-sample.php          ← credentials template
```

---

## 7. Implementation Order

1. **DB migration SQL** — create 6 new tables + seed initial alert rules
2. **Login** — `login.php`, `logout.php`, session guard in `admin/` pages
3. **Station management** — `admin/stations.php` (CRUD)
4. **Alert rules UI** — `admin/alert_rules.php`
5. **Contacts UI** — `admin/contacts.php` with station assignment
6. **`check_alerts.php` cron** — state machine + email + WhatsApp
7. **Alert log UI** — `admin/alert_log.php` (read-only, for thesis documentation)

---

## 8. Security Checklist

- [ ] Passwords stored as `password_hash()` (bcrypt, `PASSWORD_DEFAULT`)
- [ ] Session regenerated on login (`session_regenerate_id(true)`)
- [ ] All DB queries use PDO prepared statements (already established pattern)
- [ ] All output escaped with `htmlspecialchars()`
- [ ] No credentials in `public_html/` tree
- [ ] `db_config.php` and `sapi.php` outside web root (`private_configs/`)
- [ ] `.htaccess` in `admin/` to block direct PHP execution if session check fails (belt-and-suspenders)
- [ ] WhatsApp API keys stored in DB (not in code)

---

*Design version: 1.0 — 2026-03-14*
