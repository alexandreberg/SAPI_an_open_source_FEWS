#!/bin/bash

# Script automático para importar CSVs MERGE para MySQL (uso em crontab)
# Rastreia última DATA+HORA importada e importa apenas novos registros

# Configurações
VENV_DIR="venv_merge"
SCRIPT_DIR="/dados/Pessoal/Mestrado/MERGE/python"
CSV_DIR="/dados/Pessoal/Mestrado/MERGE/CSV"
LOG_IMPORTACAO="/dados/Pessoal/Mestrado/MERGE/ultima_importacao.log"
LOG_PROCESSAMENTO="/dados/Pessoal/Mestrado/MERGE/ultimo_processamento.log"
SCRIPT_PYTHON="importar_csv_mysql_incremental.py"
LOG_EXECUCAO="/dados/Pessoal/Mestrado/MERGE/log_importacao_$(date +%Y%m%d_%H%M%S).log"

# Redirecionar saída para log
exec > >(tee -a "$LOG_EXECUCAO") 2>&1

echo "=========================================="
echo "Importação automática MERGE → MySQL"
echo "Início: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
echo ""

# Verificar ambiente virtual
if [ ! -d "$SCRIPT_DIR/$VENV_DIR" ]; then
    echo "ERRO: Ambiente virtual não encontrado!"
    echo "Execute: ./setup_ambiente.sh"
    exit 1
fi

# Verificar script Python
if [ ! -f "$SCRIPT_DIR/$SCRIPT_PYTHON" ]; then
    echo "ERRO: Script $SCRIPT_PYTHON não encontrado!"
    exit 1
fi

# Criar log de importação se não existir
if [ ! -f "$LOG_IMPORTACAO" ]; then
    echo "AVISO: Arquivo $LOG_IMPORTACAO não encontrado!"
    echo "Criando com data inicial: 2025-01-01 00:00"
    echo "2025-01-01 00:00" > "$LOG_IMPORTACAO"
fi

# Verificar se existe log de processamento
if [ ! -f "$LOG_PROCESSAMENTO" ]; then
    echo "ERRO: Arquivo $LOG_PROCESSAMENTO não encontrado!"
    echo "Execute primeiro os scripts de sincronização/processamento."
    exit 1
fi

# Ler logs (remover apenas newlines, manter espaços internos)
ULTIMA_IMPORTACAO=$(cat "$LOG_IMPORTACAO" | tail -n 1 | tr -d '\n' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
ULTIMO_PROCESSAMENTO=$(cat "$LOG_PROCESSAMENTO" | tail -n 1 | tr -d '\n' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')

echo "Última importação: $ULTIMA_IMPORTACAO"
echo "Último processamento: $ULTIMO_PROCESSAMENTO"
echo ""

# Validar formato (deve ser YYYY-MM-DD HH:MM ou apenas YYYY-MM-DD)
if [[ ! "$ULTIMA_IMPORTACAO" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}( [0-9]{2}:[0-9]{2})?$ ]]; then
    echo "ERRO: Formato inválido em $LOG_IMPORTACAO"
    echo "Formato esperado: YYYY-MM-DD HH:MM ou YYYY-MM-DD"
    exit 1
fi

# Extrair data da última importação
if [[ "$ULTIMA_IMPORTACAO" =~ ^([0-9]{4}-[0-9]{2}-[0-9]{2})( ([0-9]{2}:[0-9]{2}))?$ ]]; then
    DATA_ULTIMA_IMP="${BASH_REMATCH[1]}"
    HORA_ULTIMA_IMP="${BASH_REMATCH[3]:-00:00}"
else
    DATA_ULTIMA_IMP="$ULTIMA_IMPORTACAO"
    HORA_ULTIMA_IMP="00:00"
fi

echo "Data base: $DATA_ULTIMA_IMP"
echo "Hora base: $HORA_ULTIMA_IMP"
echo ""

# Converter datas para timestamp
TS_ULTIMA_IMP=$(date -d "$DATA_ULTIMA_IMP" +%s)
TS_ULTIMO_PROC=$(date -d "$ULTIMO_PROCESSAMENTO" +%s)

# Verificar se há dados novos para importar
if [ $TS_ULTIMA_IMP -gt $TS_ULTIMO_PROC ]; then
    echo "Importação atualizada. Nenhum dado novo para importar."
    echo "Fim: $(date '+%Y-%m-%d %H:%M:%S')"
    exit 0
fi

# Ativar ambiente virtual
echo "Ativando ambiente virtual..."
source "$SCRIPT_DIR/$VENV_DIR/bin/activate"

if [ $? -ne 0 ]; then
    echo "ERRO: Falha ao ativar ambiente virtual"
    exit 1
fi

echo "✓ Ambiente virtual ativado"
echo ""

# Contadores
total_arquivos=0
total_registros_novos=0
total_registros_atualizados=0
arquivos_processados=0
arquivos_com_dados_novos=0

# Processar desde a data da última importação até a última processada
DATA_ATUAL="$DATA_ULTIMA_IMP"

while [ $(date -d "$DATA_ATUAL" +%s) -le $TS_ULTIMO_PROC ]; do
    ANO=$(date -d "$DATA_ATUAL" +%Y)
    MES=$(date -d "$DATA_ATUAL" +%m)
    DIA=$(date -d "$DATA_ATUAL" +%d)
    
    # Arquivo CSV do dia
    CSV_FILE="$CSV_DIR/$ANO/$MES/estacao01_MERGE_${ANO}${MES}${DIA}.csv"
    
    if [ ! -f "$CSV_FILE" ]; then
        # Arquivo não existe, avançar para próximo dia
        DATA_ATUAL=$(date -I -d "$DATA_ATUAL + 1 day")
        continue
    fi
    
    total_arquivos=$((total_arquivos + 1))
    
    echo "=========================================="
    echo "Processando: $DATA_ATUAL"
    echo "Arquivo: $(basename $CSV_FILE)"
    echo "=========================================="
    
    # Determinar hora inicial para este arquivo
    if [ "$DATA_ATUAL" == "$DATA_ULTIMA_IMP" ]; then
        # Mesmo dia da última importação - importar apenas após a última hora
        HORA_INICIAL="$HORA_ULTIMA_IMP"
        echo "Hora inicial: $HORA_INICIAL (incremental)"
    else
        # Dia diferente - importar tudo
        HORA_INICIAL="00:00"
        echo "Hora inicial: $HORA_INICIAL (dia completo)"
    fi
    
    # Executar importação
    python3 "$SCRIPT_DIR/$SCRIPT_PYTHON" "$CSV_FILE" "$HORA_INICIAL"
    EXIT_CODE=$?
    
    if [ $EXIT_CODE -eq 0 ]; then
        arquivos_processados=$((arquivos_processados + 1))
        
        # Obter última linha do CSV (última hora processada)
        ULTIMA_LINHA=$(tail -n 1 "$CSV_FILE")
        
        if [[ "$ULTIMA_LINHA" =~ ^([0-9]{4}-[0-9]{2}-[0-9]{2}),([0-9]{2}:[0-9]{2}):[0-9]{2}, ]]; then
            DATA_ULTIMA="${BASH_REMATCH[1]}"
            HORA_ULTIMA="${BASH_REMATCH[2]}"
            
            echo "✓ Importação concluída"
            echo "Última hora no arquivo: $HORA_ULTIMA"
            
            # Atualizar log com última hora importada deste arquivo
            echo "$DATA_ULTIMA $HORA_ULTIMA" > "$LOG_IMPORTACAO"
            arquivos_com_dados_novos=$((arquivos_com_dados_novos + 1))
        else
            echo "⚠ Arquivo processado mas não foi possível extrair última hora"
        fi
    else
        echo "✗ Erro na importação (exit code: $EXIT_CODE)"
        
        # Parar em caso de erro
        deactivate
        exit $EXIT_CODE
    fi
    
    echo ""
    
    # Avançar para próximo dia
    DATA_ATUAL=$(date -I -d "$DATA_ATUAL + 1 day")
done

# Desativar ambiente virtual
deactivate

echo "=========================================="
echo "Resumo da Importação"
echo "=========================================="
echo "Arquivos verificados: $total_arquivos"
echo "Arquivos processados: $arquivos_processados"
echo "Arquivos com dados novos: $arquivos_com_dados_novos"
echo "Última importação registrada: $(cat $LOG_IMPORTACAO | tail -n 1)"
echo "Fim: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="