#!/usr/bin/env bash
# =============================================================================
# SAPI credential / identifier audit.
#
# Fails (exit 1) if the repository contains anything that must never be public:
#   1. gitleaks findings, in the working tree AND in the whole git history
#   2. tracked files with credential-like names (credentials.h, .env, *.pem,
#      firmware binaries, models, database dumps, ...)
#   3. real identifiers in tracked text: Hostinger account id, SIM ICCID, IMEI,
#      Telegram chat id / bot token, private-key blocks
#   4. large tracked files that are not stored in Git LFS
#   5. a .gitignore that fails the fake-credential proof (tools/check_gitignore.py)
#
# Usage:   tools/audit.sh
# Needs:   git, python3 and gitleaks (>= 8.25) — set GITLEAKS=/path/to/gitleaks
#          if it is not on PATH. A missing tool is a FAILURE, never a skip.
# =============================================================================
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"

fail=0
ok()  { printf '  \033[32mOK\033[0m   %s\n' "$*"; }
bad() { printf '  \033[31mFAIL\033[0m %s\n' "$*"; fail=1; }
hdr() { printf '\n== %s\n' "$*"; }

# Files that define the patterns themselves are excluded from pattern scans.
SELF=(':(exclude).gitignore' ':(exclude)tools/audit.sh' ':(exclude)tools/check_gitignore.py' ':(exclude).gitleaks.toml')
# CAD exchange files hold long numeric coordinates that look like ICCIDs; they are also huge (Git LFS).
CAD=(':(exclude)*.step' ':(exclude)*.STEP' ':(exclude)*.stp' ':(exclude)*.STP' ':(exclude)*.stl' ':(exclude)*.STL' ':(exclude)*.wrl' ':(exclude)*.WRL')

# ---- 1. gitleaks ------------------------------------------------------------
hdr "1. gitleaks (working tree + full history)"
GL="${GITLEAKS:-$(command -v gitleaks || true)}"
if [[ -z "$GL" || ! -x "$GL" ]]; then
  bad "gitleaks not found (install it or set GITLEAKS=/path/to/gitleaks)"
else
  if "$GL" dir . --config .gitleaks.toml --redact --no-banner --max-target-megabytes 10 --exit-code 1 >/tmp/gl_dir.$$ 2>&1; then
    ok "working tree clean"
  else
    bad "gitleaks found something in the working tree:"; sed 's/^/       /' /tmp/gl_dir.$$ | tail -25
  fi
  if git rev-parse --verify -q HEAD >/dev/null; then
    if "$GL" git . --config .gitleaks.toml --log-opts="--all" --redact --no-banner --exit-code 1 >/tmp/gl_git.$$ 2>&1; then
      ok "history clean"
    else
      bad "gitleaks found something in the git history:"; sed 's/^/       /' /tmp/gl_git.$$ | tail -25
    fi
  else
    ok "no commits yet (history scan skipped: nothing to scan)"
  fi
  rm -f /tmp/gl_dir.$$ /tmp/gl_git.$$
fi

# ---- 2. forbidden tracked file names ----------------------------------------
hdr "2. credential-like file names among tracked files"
forbidden='(^|/)(credentials\.h|credentials_(?!sample)[^/]*\.h|secrets?\.[a-z]+|arduino_secrets\.h|db_config\.php|mail_config\.php|api_config\.php|wp-config\.php|\.htpasswd|telegram_config\.json|api_key[^/]*\.txt|config_mysql\.py|\.env|\.env\.(?!sample|example)[^/]*|id_(rsa|ed25519|ecdsa)[^/]*|known_hosts|token\.txt|settings\.local\.json|CLAUDE[^/]*\.(md|txt))$'
forbidden_ext='\.(pem|key|crt|cer|p12|pfx|ppk|ovpn|bin|elf|hex|uf2|pkl|joblib|sqlite3?|db|sql\.gz|dump)$'
hits=$(git ls-files | grep -P "$forbidden" || true)
hits2=$(git ls-files | grep -P "$forbidden_ext" || true)
# private_configs/sapi.php and cron/credenciais.php are real-credential names too
hits3=$(git ls-files | grep -E '(^|/)(private_configs/sapi\.php|cron/credenciais\.php)$|(^|/)\.claude(/|$)' || true)
if [[ -z "$hits$hits2$hits3" ]]; then ok "no forbidden file names"; else bad "forbidden tracked files:"; printf '%s\n' "$hits" "$hits2" "$hits3" | sed '/^$/d;s/^/       /'; fi

# ---- 3. identifiers in tracked text -----------------------------------------
hdr "3. real identifiers in tracked text files"
scan() { # $1 = label, $2 = -E regex
  local out; out=$(git grep -InE -e "$2" -- . "${SELF[@]}" "${CAD[@]}" 2>/dev/null | cut -c1-140 || true)
  if [[ -z "$out" ]]; then ok "$1"; else bad "$1"; printf '%s\n' "$out" | head -8 | sed 's/^/       /'; fi
}
scan "no Hostinger account id (u + 9 digits)"       '\bu9[0-9]{8}\b'
scan "no SIM ICCID (89 + 17-19 digits)"             '\b89[0-9]{17,19}\b'
scan "no IMEI next to the word IMEI"                '[Ii][Mm][Ee][Ii][^0-9]{0,12}[0-9]{15}\b'
scan "no Telegram chat_id with digits"              'chat_?id["'"'"' :=]{1,6}-?[0-9]{7,}'
scan "no Telegram bot token"                        '\b[0-9]{8,10}:AA[A-Za-z0-9_-]{33}\b'
scan "no private-key block"                         '-----BEGIN [A-Z ]*PRIVATE KEY-----'
scan "no reference to the private CLAUDE.md"        'CLAUDE\.md'

# ---- 4. large files outside Git LFS ------------------------------------------
hdr "4. tracked files > 5 MB must be in Git LFS"
big=""
while IFS= read -r f; do
  [[ -f "$f" ]] || continue
  size=$(stat -c %s "$f" 2>/dev/null || echo 0)
  if (( size > 5*1024*1024 )); then
    if ! git check-attr filter -- "$f" | grep -q 'filter: lfs'; then big+="$f ($((size/1024/1024)) MB)"$'\n'; fi
  fi
done < <(git ls-files)
if [[ -z "$big" ]]; then ok "no large non-LFS files"; else bad "large files not in LFS:"; printf '%s' "$big" | sed 's/^/       /'; fi

# ---- 5. .gitignore proof ------------------------------------------------------
hdr "5. .gitignore keeps fake credentials out of 'git add -A'"
if python3 tools/check_gitignore.py .gitignore >/tmp/gi.$$ 2>&1; then ok "$(head -1 /tmp/gi.$$)"; else bad ".gitignore proof failed"; sed 's/^/       /' /tmp/gi.$$; fi
rm -f /tmp/gi.$$

hdr "Result"
if (( fail )); then printf '\033[31mAUDIT FAILED\033[0m — do not push.\n'; exit 1; fi
printf '\033[32mAUDIT PASSED\033[0m\n'
