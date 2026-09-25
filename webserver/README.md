# Web interface

PHP/MariaDB application of SAPI: real-time and historical monitoring, station, contact and
alert management, the predictions dashboard, the endpoint that receives the gateway's
data, and the alert cron jobs. In operation at <https://ilha3d.com/sapi/>.

Releases: `webserver-v1.0.0` (first release, 2026-07-06) and `webserver-v1.1.0` (the
version deployed today).

## Layout

| Path | Contents |
|------|----------|
| `public_html/sapi/` | The application: dashboard, admin panel, predictions, API, the gateway endpoint (`sensorData/receive-data.php`) |
| `cron/` | Alert engine (e-mail, Telegram) and level-filter cron jobs |
| `private_configs/` | **Templates only** (`*-sample.*`) of the files that hold the database, mail, API and Telegram credentials; they live outside the web root |
| `database/schema_20260313.sql` | Schema snapshot (structure only) |
| `migration_*.sql` | Schema migrations, applied after the snapshot in issue order |

## Deploying

The full guide is [`docs/webserver/deployment-guide.md`](../docs/webserver/deployment-guide.md).
In short:

1. Every path in the code uses `/home/<HOSTINGER_USER>/…`; replace `<HOSTINGER_USER>` with
   your own hosting account (or adapt the paths to your server).
2. Copy each `*-sample.*` file in `private_configs/` and `cron/credenciais-sample.php` to
   its real name (without `-sample`) and fill in your own values. The real names are in
   `.gitignore` — never commit them.
3. The API key in `private_configs/sapi/db_config.php` must match the gateway's
   `apiKey` (see [`../firmware/gateway-01/`](../firmware/gateway-01/README.md)).
4. Create the database from `database/schema_20260313.sql`, then apply
   `migration_issue52.sql` → `migration_issue57.sql` → `migration_issue108.sql` →
   `migration_issue110.sql` → `migration_m6_mlr.sql`.
5. Install the PHP dependencies with Composer (`composer.json`).

Design notes: [`docs/webserver/`](../docs/webserver/).
