#!/bin/bash

# Script para processar todos os arquivos GRIB2 do MERGE de um dia
# e gerar CSV consolidado com dados horários

# Configurações (Altere aqui) ==>
# Localização da Coordenada da área de estudo:
LAT="-27.431518"
LON="-48.421779"
ESTACAO="estacao01_MERGE"
# Diretorio de armazenamento dos arquivos processados CSV:
DIR_OUTPUT="/home/ilha3d/MERGE/CSV"
# <== Fim das configurações

# Verifica argumentos
if [ $# -lt 4 ]; then
    echo "Uso: $0 <diretório_com_grib2> <ano> <mes> <dia>"
    echo "Exemplo: $0 /home/ilha3d/MERGE/GPM/HOURLY 2025 11 13"
    exit 1
fi

DIR_INPUT="$1/$2/$3/$4"
ANO="$2"
MES="$3"
DIA="$4"

# Criar subpasta mensal dentro de DIR_OUTPUT
DIR_OUTPUT_MES="${DIR_OUTPUT}/${ANO}/${MES}"

# Criar diretório se não existir
mkdir -p "$DIR_OUTPUT_MES"

# Nome do arquivo de saída no formato numérico: estacao01_MERGE_YYYYMMDD.csv
OUTPUT_FILE="${DIR_OUTPUT_MES}/${ESTACAO}_${ANO}${MES}${DIA}.csv"

# Verifica se o diretório de entrada existe
if [ ! -d "$DIR_INPUT" ]; then
    echo "Erro: Diretório $DIR_INPUT não encontrado!"
    exit 1
fi

if [ ! -d "$DIR_OUTPUT" ]; then
    echo "Erro: Diretório $DIR_OUTPUT não encontrado!"
    exit 1
fi

echo "===================================="
echo "Processamento em lote - Estação-01"
echo "===================================="
echo "Diretório: $DIR_INPUT"
echo "Coordenadas: Lat=$LAT, Lon=$LON"
echo "Arquivo saída: $OUTPUT_FILE"
echo ""

# FASE 1: Converter todos os GRIB2 para NetCDF primeiro
echo "Fase 1: Convertendo GRIB2 para NetCDF..."
CONVERTIDOS=0
for GRIB_FILE in "$DIR_INPUT"/*.grib2; do
    if [ ! -f "$GRIB_FILE" ]; then
        continue
    fi
    
    NC_FILE="${GRIB_FILE%.grib2}.nc"
    
    if [ ! -f "$NC_FILE" ]; then
        echo -n "  Convertendo $(basename $GRIB_FILE)... "
        cdo -f nc copy "$GRIB_FILE" "$NC_FILE" 2>/dev/null
        if [ $? -eq 0 ]; then
            echo "OK"
            CONVERTIDOS=$((CONVERTIDOS + 1))
        else
            echo "ERRO"
        fi
    fi
done

if [ $CONVERTIDOS -gt 0 ]; then
    echo "  $CONVERTIDOS arquivo(s) convertido(s)"
fi
echo ""

# FASE 2: Extrair dados de precipitação
echo "Fase 2: Extraindo dados de precipitação..."

# Criar cabeçalho do CSV
echo "Dados de precipitacao horaria do MERGE para o ponto da $ESTACAO"  > "$OUTPUT_FILE"
echo "Latitude = $LAT e Longitude = $LON"  >> "$OUTPUT_FILE"
echo "date,time,precipitacao_mm" >> "$OUTPUT_FILE"

# Contador
TOTAL=0
PROCESSADOS=0

# Processar cada arquivo NetCDF
for NC_FILE in "$DIR_INPUT"/*.nc; do
    if [ ! -f "$NC_FILE" ]; then
        continue
    fi
    
    TOTAL=$((TOTAL + 1))
    BASENAME=$(basename "$NC_FILE")
    
    echo -n "  [$TOTAL] Processando $BASENAME... "
    
    # Arquivo temporário
    TEMP_FILE=$(mktemp)

    # Detectar nome da variável de precipitação (prec em CDO 2.4.x, rdp em CDO 2.5.x)
    VAR_NAME=$(cdo showname "$NC_FILE" 2>/dev/null | tr ' ' '\n' | grep -E '^(prec|rdp)$' | head -1)
    if [ -z "$VAR_NAME" ]; then
        echo "ERRO (variável não encontrada)"
        rm -f "$TEMP_FILE"
        continue
    fi

    # Extrair dados do ponto
    cdo -selname,$VAR_NAME -remapnn,"lon=${LON}_lat=${LAT}" "$NC_FILE" "$TEMP_FILE" 2>/dev/null
    
    if [ $? -eq 0 ]; then
        # Exportar para CSV (sem cabeçalho)
        # Formato: date,time,value
        cdo -outputtab,date,time,value "$TEMP_FILE" 2>/dev/null | \
          grep -v '#' | \
          tr -s ' ' | \
          awk '{gsub(/^ +| +$/,"")} {printf "%s,%s,%s\n", $1, $2, $3}' >> "$OUTPUT_FILE"
        
        PROCESSADOS=$((PROCESSADOS + 1))
        echo "OK"
    else
        echo "ERRO"
    fi
    
    # Limpar temporário
    rm -f "$TEMP_FILE"
done

echo ""
echo "===================================="
echo "Resumo do Processamento"
echo "===================================="
echo "Total de arquivos: $TOTAL"
echo "Processados com sucesso: $PROCESSADOS"
echo "Arquivo gerado: $OUTPUT_FILE"

if [ -f "$OUTPUT_FILE" ]; then
    NUM_LINHAS=$(( $(wc -l < "$OUTPUT_FILE") - 3 ))
    echo "Registros extraídos: $NUM_LINHAS"
    echo ""
    echo "Primeiras 5 linhas:"
    head -n 6 "$OUTPUT_FILE"
    echo ""
    echo "Últimas 3 linhas:"
    tail -n 3 "$OUTPUT_FILE"
fi
