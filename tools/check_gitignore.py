#!/usr/bin/env python3
"""Prove that a .gitignore keeps fake credential files out of `git add -A`.

Usage: check_gitignore.py /path/to/.gitignore

Builds a throw-away git repository from scratch, creates every file name in
MUST_IGNORE and MUST_TRACK, runs `git add -A` and reports leaks (a credential
that got staged) and false positives (a sample that was ignored).
Exit status 0 only if both lists are empty.
"""
import os
import shutil
import subprocess
import sys
import tempfile

MUST_IGNORE = """firmware/gateway-01/include/credentials.h
firmware/gateway-01/include/credentials_old.h
firmware/gateway-01/include/secrets.h
firmware/gateway-01/include/arduino_secrets.h
firmware/gateway-01/.pio/build/esp32dev/firmware.bin
firmware/gateway-01/firmware.bin
firmware/station-03/build/x.elf
firmware/station-03/build/x.hex
webserver/private_configs/sapi/db_config.php
webserver/private_configs/sapi/mail_config.php
webserver/private_configs/sapi/api_config.php
webserver/private_configs/sapi.php
webserver/cron/credenciais.php
webserver/wp-config.php
webserver/.htpasswd
webserver/public_html/sapi/sensorData/error.log
webserver/public_html/sapi/error_log
webserver/vendor/autoload.php
pipelines/merge2mysql/python/config_mysql.py
pipelines/merge2mysql/.env
predictive-models/.env
predictive-models/.env.local
predictive-models/production/config/telegram_config.json
predictive-models/production_m6/config/api_key.txt
predictive-models/production/config/anything.json
predictive-models/telegram_config.json
predictive-models/api_key.txt
predictive-models/models/model4_lgbm.pkl
predictive-models/results_final_m4_lgbm/output/continuous_predictions.csv
predictive-models/results_final_m6_mlr/output/continuous_predictions_m6.csv
predictive-models/data/station01_level_raw.csv
data/merge_20260404.csv
deploy/id_rsa
deploy/id_ed25519
deploy/server.pem
deploy/server.key
deploy/client.p12
deploy/known_hosts
service-account-prod.json
client_secret_123.json
webserver/u912345678_full_dump_20260313.sql
webserver/backup.sql.gz
webserver/local.sqlite
webserver/data.db
.claude/settings.local.json
CLAUDE.local.md
CLAUDE.md
docs/CLAUDE.md
CLAUDE_notes.md
CLAUDE.md_tooLong.txt
.claude/commands/x.md
.vscode/settings.json
docs/notes.log
hardware/x/x-backups/a.kicad_pcb
hardware/x/x.kicad_prl
secrets.json
token.txt""".split()

MUST_TRACK = """firmware/gateway-01/include/credentials_sample.h
webserver/private_configs/sapi-sample.php
webserver/private_configs/sapi/db_config-sample.php
webserver/private_configs/sapi/mail_config-sample.php
webserver/private_configs/sapi/api_config-sample.php
webserver/private_configs/sapi/telegram_config-sample.json
webserver/cron/credenciais-sample.php
pipelines/merge2mysql/python/config_mysql_SAMPLE.py
predictive-models/.env.sample
predictive-models/results_final_m4_lgbm/event_windows_v3.csv
predictive-models/results_final_m6_mlr/output/compare_m4_vs_m6.csv
webserver/migration_issue52.sql
webserver/database/schema_20260313.sql
firmware/station-01/src/main.cpp
firmware/station-01/platformio.ini
hardware/x/x.kicad_pcb
predictive-models/output_audit/auditoria_eventos_A3.pdf""".split()


def main() -> int:
    gi = os.path.abspath(sys.argv[1])
    tmp = tempfile.mkdtemp(prefix="gi_proof_")
    try:
        subprocess.run(["git", "init", "-q", tmp], check=True)
        shutil.copy(gi, os.path.join(tmp, ".gitignore"))
        for p in MUST_IGNORE + MUST_TRACK:
            full = os.path.join(tmp, p)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w") as fh:
                fh.write("x")
        subprocess.run(["git", "-C", tmp, "add", "-A"], check=True)
        staged = set(
            subprocess.check_output(["git", "-C", tmp, "diff", "--cached", "--name-only"])
            .decode()
            .split("\n")
        ) - {""}
        leaks = [p for p in MUST_IGNORE if p in staged]
        wrong = [p for p in MUST_TRACK if p not in staged]
        print(f"credential-like files tried : {len(MUST_IGNORE)}  -> leaked into index: {len(leaks)}")
        for p in leaks:
            print("  LEAK:", p)
        print(f"sample/legit files tried    : {len(MUST_TRACK)}  -> wrongly ignored : {len(wrong)}")
        for p in wrong:
            print("  WRONGLY IGNORED:", p)
        return 1 if (leaks or wrong) else 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


sys.exit(main())
