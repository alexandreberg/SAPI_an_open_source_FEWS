#!/bin/bash

# Wrapper COMPLETO para MERGE: sincroniza, processa E importa para MySQL
# Com proteção contra execuções simultâneas

# Configurações
LOCKFILE="/var/lock/merge-crontab.lock"
LOCKFD=200
LOG_FILE="/var/log/merge-crontab.log"
SCRIPT_DIR="/dados/Pessoal/Mestrado/MERGE"

# Função para cleanup ao sair
cleanup() {
    flock -u $LOCKFD
    rm -f "$LOCKFILE"
}

# Registrar trap para cleanup
trap cleanup EXIT

# Tentar obter o lock (não bloqueante)
exec 200>"$LOCKFILE"
flock -n $LOCKFD

if [ $? -ne 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] AVISO: Outra instância já está em execução. Saindo..." >> "$LOG_FILE"
    exit 0
fi

# Gravar PID no arquivo de lock
echo $$ >&200

echo "" >> "$LOG_FILE"
echo "===============================================" >> "$LOG_FILE"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Iniciando wrapper MERGE COMPLETO" >> "$LOG_FILE"
echo "PID: $$" >> "$LOG_FILE"
echo "===============================================" >> "$LOG_FILE"

# ===================================================
# ETAPA 1: Sincronização
# ===================================================
echo "[$(date '+%Y-%m-%d %H:%M:%S')] [1/3] Iniciando sincronização..." >> "$LOG_FILE"
"$SCRIPT_DIR/0-sincroniza_repo_merge_crontab.sh" >> "$LOG_FILE" 2>&1
SYNC_EXIT=$?

if [ $SYNC_EXIT -eq 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✓ Sincronização concluída" >> "$LOG_FILE"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✗ ERRO na sincronização (exit: $SYNC_EXIT)" >> "$LOG_FILE"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Abortando pipeline" >> "$LOG_FILE"
    exit $SYNC_EXIT
fi

echo "" >> "$LOG_FILE"

# ===================================================
# ETAPA 2: Processamento (GRIB2 → CSV)
# ===================================================
echo "[$(date '+%Y-%m-%d %H:%M:%S')] [2/3] Iniciando processamento..." >> "$LOG_FILE"
"$SCRIPT_DIR/2-processa_dia_completo_crontab.sh" >> "$LOG_FILE" 2>&1
PROC_EXIT=$?

if [ $PROC_EXIT -eq 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✓ Processamento concluído" >> "$LOG_FILE"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✗ ERRO no processamento (exit: $PROC_EXIT)" >> "$LOG_FILE"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Pulando importação devido a erro" >> "$LOG_FILE"
    exit $PROC_EXIT
fi

echo "" >> "$LOG_FILE"

# ===================================================
# ETAPA 3: Importação (CSV → MySQL)
# ===================================================
echo "[$(date '+%Y-%m-%d %H:%M:%S')] [3/3] Iniciando importação..." >> "$LOG_FILE"
"$SCRIPT_DIR/3-importar_dados_crontab.sh" >> "$LOG_FILE" 2>&1
IMPORT_EXIT=$?

if [ $IMPORT_EXIT -eq 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✓ Importação concluída" >> "$LOG_FILE"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✗ ERRO na importação (exit: $IMPORT_EXIT)" >> "$LOG_FILE"
fi

echo "" >> "$LOG_FILE"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Wrapper finalizado" >> "$LOG_FILE"
echo "===============================================" >> "$LOG_FILE"

# Retorna o exit code da última etapa com erro (ou 0 se tudo OK)
if [ $IMPORT_EXIT -ne 0 ]; then
    exit $IMPORT_EXIT
elif [ $PROC_EXIT -ne 0 ]; then
    exit $PROC_EXIT
else
    exit 0
fi