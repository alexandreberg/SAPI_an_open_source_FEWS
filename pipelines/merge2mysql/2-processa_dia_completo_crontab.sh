#!/bin/bash

# Script automático para processar arquivos MERGE em lote (uso em crontab)
# v2: Rastreia última HORA processada por dia, não apenas a data
# CORRIGIDO: Sempre reprocessa desde a última data (inclusive)

# Configurações
DIR_BASE="/dados/Pessoal/Mestrado/MERGE/GPM/HOURLY"
DIR_SCRIPT="/dados/Pessoal/Mestrado/MERGE"
LOG_PROCESSAMENTO="/dados/Pessoal/Mestrado/MERGE/ultimo_processamento.log"
LOG_TRANSFERENCIA="/dados/Pessoal/Mestrado/MERGE/ultima_transferencia.log"
SCRIPT_PROCESSAMENTO="2-processa_dia_completo.sh"
LOG_EXECUCAO="/dados/Pessoal/Mestrado/MERGE/log_crontab_$(date +%Y%m%d_%H%M%S).log"

# Redirecionar toda saída para o log de execução
exec > >(tee -a "$LOG_EXECUCAO") 2>&1

echo "=========================================="
echo "Processamento automático MERGE - CRONTAB"
echo "Início: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
echo ""

# Verificar se o script de processamento existe
if [ ! -f "$DIR_SCRIPT/$SCRIPT_PROCESSAMENTO" ]; then
    echo "ERRO: Script $SCRIPT_PROCESSAMENTO não encontrado!"
    exit 1
fi

# Verificar/criar log de controle de processamento
if [ ! -f "$LOG_PROCESSAMENTO" ]; then
    echo "AVISO: Arquivo de controle $LOG_PROCESSAMENTO não encontrado!"
    echo "Criando arquivo com data inicial: 2025-01-01"
    echo "2025-01-01" > "$LOG_PROCESSAMENTO"
fi

# Verificar se existe o log de transferência
if [ ! -f "$LOG_TRANSFERENCIA" ]; then
    echo "ERRO: Arquivo $LOG_TRANSFERENCIA não encontrado!"
    exit 1
fi

# Ler logs
ULTIMA_DATA_PROC=$(cat "$LOG_PROCESSAMENTO" | tail -n 1 | tr -d ' ')
ULTIMA_DATA_TRANSF=$(cat "$LOG_TRANSFERENCIA" | tail -n 1 | tr -d ' ')
DATA_ATUAL=$(date +%Y-%m-%d)

echo "Última data processada: $ULTIMA_DATA_PROC"
echo "Última data transferida: $ULTIMA_DATA_TRANSF"
echo "Data atual: $DATA_ATUAL"

# Validar formato das datas
if ! date -d "$ULTIMA_DATA_PROC" >/dev/null 2>&1; then
    echo "ERRO: Data inválida no arquivo de processamento: $ULTIMA_DATA_PROC"
    exit 1
fi

if ! date -d "$ULTIMA_DATA_TRANSF" >/dev/null 2>&1; then
    echo "ERRO: Data inválida no arquivo de transferência: $ULTIMA_DATA_TRANSF"
    exit 1
fi

echo ""

# Converter datas para timestamp
TS_ULTIMA_PROC=$(date -d "$ULTIMA_DATA_PROC" +%s)
TS_ULTIMA_TRANSF=$(date -d "$ULTIMA_DATA_TRANSF" +%s)
TS_ATUAL=$(date -d "$DATA_ATUAL" +%s)

# CRÍTICO: Sempre processar DESDE a última data (INCLUSIVE) até a última transferida
# Isso garante que dias incompletos sejam reprocessados
if [ $TS_ULTIMA_PROC -gt $TS_ULTIMA_TRANSF ]; then
    echo "Sistema atualizado. Nenhum dia para processar."
    echo "Fim: $(date '+%Y-%m-%d %H:%M:%S')"
    exit 0
fi

# CORRIGIDO: Processar desde a última data processada (INCLUSIVE)
DATA_INICIAL="$ULTIMA_DATA_PROC"
DATA_FINAL="$ULTIMA_DATA_TRANSF"

echo "Modo: Processamento incremental (com reprocessamento)"
echo "Período: $DATA_INICIAL até $DATA_FINAL (ambos inclusive)"
echo ""

# Contadores
DIAS_PROCESSADOS=0
DIAS_COMPLETOS=0
DIAS_INCOMPLETOS=0
DIAS_VAZIOS=0
DIAS_PULADOS=0
ULTIMA_DATA_SUCESSO=""

# Processar cada dia no período
DATA_PROCESSAR="$DATA_INICIAL"

while [ $(date -d "$DATA_PROCESSAR" +%s) -le $(date -d "$DATA_FINAL" +%s) ]; do
    ANO=$(date -d "$DATA_PROCESSAR" +%Y)
    MES=$(date -d "$DATA_PROCESSAR" +%m)
    DIA=$(date -d "$DATA_PROCESSAR" +%d)
    
    echo "=========================================="
    echo "Processando: $DATA_PROCESSAR ($ANO/$MES/$DIA)"
    echo "=========================================="
    
    # Verificar se o diretório do dia existe
    DIR_DIA="$DIR_BASE/$ANO/$MES/$DIA"
    
    if [ ! -d "$DIR_DIA" ]; then
        echo "AVISO: Diretório $DIR_DIA não encontrado. Pulando..."
        DIAS_VAZIOS=$((DIAS_VAZIOS + 1))
        echo ""
        DATA_PROCESSAR=$(date -d "$DATA_PROCESSAR + 1 day" +%Y-%m-%d)
        continue
    fi
    
    # Contar arquivos GRIB2 no diretório
    NUM_GRIB2=$(ls -1 "$DIR_DIA"/*.grib2 2>/dev/null | wc -l)
    echo "Arquivos GRIB2 encontrados: $NUM_GRIB2"
    
    if [ $NUM_GRIB2 -eq 0 ]; then
        echo "AVISO: Nenhum arquivo GRIB2 encontrado. Pulando..."
        DIAS_VAZIOS=$((DIAS_VAZIOS + 1))
        echo ""
        DATA_PROCESSAR=$(date -d "$DATA_PROCESSAR + 1 day" +%Y-%m-%d)
        continue
    fi
    
    # Determinar se é dia atual
    DIA_ATUAL=$([ "$DATA_PROCESSAR" == "$DATA_ATUAL" ] && echo "sim" || echo "nao")
    
    # Verificar completude
    if [ $NUM_GRIB2 -lt 24 ]; then
        if [ "$DIA_ATUAL" == "sim" ]; then
            echo "⚠ Dia atual incompleto: $NUM_GRIB2 de 24 arquivos (normal)"
        else
            echo "⚠ Dia passado incompleto: $NUM_GRIB2 de 24 arquivos"
            echo "  (Possível falha na origem ou FTP temporariamente indisponível)"
        fi
        DIAS_INCOMPLETOS=$((DIAS_INCOMPLETOS + 1))
    else
        echo "✓ Dia completo com 24 arquivos"
        DIAS_COMPLETOS=$((DIAS_COMPLETOS + 1))
    fi
    
    # Verificar se CSV já existe e quantas linhas tem
    CSV_FILE="$DIR_SCRIPT/CSV/$ANO/$MES/estacao01_MERGE_${ANO}${MES}${DIA}.csv"
    PRECISA_PROCESSAR="sim"
    
    if [ -f "$CSV_FILE" ]; then
        LINHAS_EXISTENTES=$(( $(wc -l < "$CSV_FILE") - 3 ))
        echo "CSV existente com $LINHAS_EXISTENTES registros"
        
        # Verificar se precisa reprocessar
        if [ $LINHAS_EXISTENTES -eq $NUM_GRIB2 ]; then
            # CSV tem mesma quantidade de dados que GRIB2
            if [ "$DIA_ATUAL" == "nao" ] && [ $NUM_GRIB2 -eq 24 ]; then
                # Dia passado completo e CSV completo - pode pular
                echo "✓ Dia já processado completamente (24/24). Pulando..."
                PRECISA_PROCESSAR="nao"
                DIAS_PULADOS=$((DIAS_PULADOS + 1))
            else
                # Dia atual ou incompleto - sempre reprocessar
                echo "⟳ Reprocessando (dia atual ou incompleto)..."
            fi
        else
            # CSV desatualizado
            echo "⟳ Reprocessando ($LINHAS_EXISTENTES → $NUM_GRIB2 registros)..."
        fi
    else
        echo "Arquivo CSV não existe. Processando pela primeira vez..."
    fi
    
    # Processar se necessário
    if [ "$PRECISA_PROCESSAR" == "sim" ]; then
        echo "Executando processamento..."
        TEMP_LOG=$(mktemp)
        
        cd "$DIR_SCRIPT" || exit 1
        $DIR_SCRIPT/$SCRIPT_PROCESSAMENTO "$DIR_BASE" "$ANO" "$MES" "$DIA" > "$TEMP_LOG" 2>&1
        EXIT_CODE=$?
        
        # Mostrar saída do processamento
        cat "$TEMP_LOG"
        
        # Verificar se o processamento foi bem-sucedido
        PROCESSADOS=$(grep "Processados com sucesso:" "$TEMP_LOG" | awk '{print $4}')
        
        if [ $EXIT_CODE -eq 0 ] && [ ! -z "$PROCESSADOS" ] && [ $PROCESSADOS -gt 0 ]; then
            echo ""
            echo "✓ Processamento concluído! ($PROCESSADOS/$NUM_GRIB2 arquivos)"
            
            ULTIMA_DATA_SUCESSO="$DATA_PROCESSAR"
            DIAS_PROCESSADOS=$((DIAS_PROCESSADOS + 1))
        else
            echo ""
            echo "✗ ERRO no processamento!"
            echo "Exit code: $EXIT_CODE"
            echo "Arquivos processados: ${PROCESSADOS:-0}"
            
            # Se for dia passado com erro crítico, parar
            if [ "$DIA_ATUAL" == "nao" ] && [ $EXIT_CODE -ne 0 ]; then
                echo "Erro crítico em dia passado. Parando execução."
                rm -f "$TEMP_LOG"
                break
            fi
        fi
        
        rm -f "$TEMP_LOG"
    else
        # Dia pulado também conta como sucesso
        ULTIMA_DATA_SUCESSO="$DATA_PROCESSAR"
        DIAS_PROCESSADOS=$((DIAS_PROCESSADOS + 1))
    fi
    
    echo ""
    
    # Avançar para o próximo dia
    DATA_PROCESSAR=$(date -d "$DATA_PROCESSAR + 1 day" +%Y-%m-%d)
done

# Atualizar log de processamento com a última data processada com sucesso
if [ ! -z "$ULTIMA_DATA_SUCESSO" ]; then
    echo "$ULTIMA_DATA_SUCESSO" > "$LOG_PROCESSAMENTO"
    echo "✓ Log atualizado para: $ULTIMA_DATA_SUCESSO"
fi

echo ""
echo "=========================================="
echo "Resumo Final"
echo "=========================================="
echo "Dias processados: $DIAS_PROCESSADOS"
echo "  - Dias completos (24 arq): $DIAS_COMPLETOS"
echo "  - Dias incompletos (<24): $DIAS_INCOMPLETOS"
echo "  - Dias pulados (já ok): $DIAS_PULADOS"
echo "  - Dias vazios/ausentes: $DIAS_VAZIOS"
echo "Última data no log: $(cat $LOG_PROCESSAMENTO | tail -n 1)"
echo "Fim: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="