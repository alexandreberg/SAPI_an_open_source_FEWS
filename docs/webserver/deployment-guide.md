# SAPI Web Interface — Deployment Guide (Issue #52)

**Server**: Hostinger shared hosting
**User**: `<HOSTINGER_USER>` (placeholder — your Hostinger account ID, e.g. `u123456789`; it also prefixes the database name and user)
**SCP port**: 65002
**SCP alias**: `<HOSTINGER_USER>@hostinger`

---

## Directory mapping: repo → server

| Repository path | Server path |
|---|---|
| `webserver/public_html/sapi/` | `/home/<HOSTINGER_USER>/domains/ilha3d.com/public_html/sapi/` |
| `webserver/cron/` | `/home/<HOSTINGER_USER>/cron/` |
| *(not in repo)* `sapi.php` | `/home/<HOSTINGER_USER>/domains/ilha3d.com/sapi.php` |

> **Note:** `public_html` at `/home/<HOSTINGER_USER>/public_html/` is a symlink to
> `domains/ilha3d.com/public_html/`. Both paths resolve to the same location.
> The `scp` commands below use the shorter `public_html` form which works fine.

---

## Files to deploy

### Web UI — upload once

```bash
scp -P 65002 \
  webserver/public_html/sapi/login.php \
  webserver/public_html/sapi/logout.php \
  <HOSTINGER_USER>@hostinger:/home/<HOSTINGER_USER>/public_html/sapi/
```

### Admin pages — upload all at once

```bash
scp -P 65002 \
  webserver/public_html/sapi/admin/_auth.php \
  webserver/public_html/sapi/admin/header.php \
  webserver/public_html/sapi/admin/footer.php \
  webserver/public_html/sapi/admin/.htaccess \
  webserver/public_html/sapi/admin/stations.php \
  webserver/public_html/sapi/admin/alert_rules.php \
  webserver/public_html/sapi/admin/contacts.php \
  webserver/public_html/sapi/admin/alert_log.php \
  <HOSTINGER_USER>@hostinger:/home/<HOSTINGER_USER>/public_html/sapi/admin/
```

### Predictive dashboard (Issues #108/#120)

```bash
scp -P 65002 \
  webserver/public_html/sapi/predictions.php \
  <HOSTINGER_USER>@hostinger:/home/<HOSTINGER_USER>/public_html/sapi/
```

### Cron

```bash
scp -P 65002 \
  webserver/cron/check_alerts.php \
  webserver/cron/filter_level.php \
  <HOSTINGER_USER>@hostinger:/home/<HOSTINGER_USER>/cron/
```

---

## First-time setup (run once)

### 1. Create admin user

Upload and run `setup_admin.php`, then **delete it immediately**:

```bash
scp -P 65002 webserver/public_html/sapi/setup_admin.php \
    <HOSTINGER_USER>@hostinger:/home/<HOSTINGER_USER>/public_html/sapi/

# Open https://ilha3d.com/sapi/setup_admin.php in browser
# Fill email + password → submit

# Delete from server:
ssh -p 65002 <HOSTINGER_USER>@hostinger \
    "rm /home/<HOSTINGER_USER>/public_html/sapi/setup_admin.php"
```

### 2. Credential file on server

`sapi.php` is at `/home/<HOSTINGER_USER>/domains/ilha3d.com/sapi.php` (outside web root).
It must define at minimum:

```php
define('servidor',   'localhost');
define('usuario',    '<HOSTINGER_USER>_sapi');
define('senhaDB',    'your-db-password');
define('banco',      '<HOSTINGER_USER>_sapi');
define('DB_CHARSET', 'utf8mb4');
```

> Email is sent via PHP native `mail()` — no SMTP constants needed.
> The From address is hardcoded in `check_alerts.php` as `sapi@ilha3d.com`.

### 3. Cron job

Set in **Hostinger hPanel → Advanced → Cron Jobs**:

```
* * * * *   /usr/bin/php /home/<HOSTINGER_USER>/cron/check_alerts.php
```

> `crontab -l` will show empty — hPanel manages crons separately. That is normal.

---

## DB migration

### Issue #52 (initial setup)

1. **Backup**: phpMyAdmin → select `<HOSTINGER_USER>_sapi` → Operations →
   Copy database to `<HOSTINGER_USER>_sapibkp01` (uncheck "CREATE DATABASE").
2. **Run migration**: phpMyAdmin → `<HOSTINGER_USER>_sapi` → Import → `migration_issue52.sql`.

### Issue #57 (delta + Kalman columns)

Run each query **separately** in phpMyAdmin (SQL tab) from `migration_issue57.sql`:

```sql
-- Query 1 of 2
ALTER TABLE `measurements`
  ADD COLUMN `level_delta_cm` DECIMAL(6,2) DEFAULT NULL AFTER `level_cm`;

-- Query 2 of 2
ALTER TABLE `measurements`
  ADD COLUMN `level_kalman_cm` DECIMAL(6,2) DEFAULT NULL AFTER `level_delta_cm`;
```

After migration, create the cron lock directory and run the initial backfill manually:

```bash
ssh -p 65002 <HOSTINGER_USER>@hostinger "mkdir -p /home/<HOSTINGER_USER>/tmp"
ssh -p 65002 <HOSTINGER_USER>@hostinger "php /home/<HOSTINGER_USER>/cron/filter_level.php"
```

Then activate the filter cron in hPanel → Advanced → Cron Jobs:

```
*/5 * * * *   /usr/bin/php /home/<HOSTINGER_USER>/cron/filter_level.php
```

See `delta-kalman-filter-issue57.md` for full details.

---

## WhatsApp alerts (CallMeBot)

Each contact who wants WhatsApp alerts must opt-in once:

1. Save **+34 644 44 78 85** in their phone contacts.
2. Send from their WhatsApp: `I allow callmebot to send me messages`
3. Wait for reply with API key (e.g. `1234567`).
4. Enter number (E.164: `+5548999999999`) + API key in
   **Admin → Contatos → Novo contato**.

---

## URLs

| Purpose | URL |
|---|---|
| Public dashboard | `https://ilha3d.com/sapi/` |
| Admin login | `https://ilha3d.com/sapi/login.php` |
| Admin area | `https://ilha3d.com/sapi/admin/stations.php` |

---

*Last updated: 2026-07-11 — added `predictions.php` deploy command (UTC tooltip fix).*
