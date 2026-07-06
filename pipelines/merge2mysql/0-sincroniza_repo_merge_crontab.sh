#!/bin/bash
# Sincroniza o repositório MERGE dia a dia pela crontab, recuperando dias perdidos.
# v2: Sincroniza SEMPRE todos os dias até hoje (inclusive)

LOGFILE="/dados/Pessoal/Mestrado/MERGE/ultima_transferencia.log"

# Se o arquivo não existir, assume ontem como última data completa
if [[ ! -f "$LOGFILE" ]]; then
    echo "Arquivo $LOGFILE não encontrado. Criando com data de ontem."
    date -d "yesterday" +%Y-%m-%d > "$LOGFILE"
fi

DATA_ULTIMA=$(cat "$LOGFILE")
DATA_ATUAL=$(date +%Y-%m-%d)

echo "Última data sincronizada: $DATA_ULTIMA"
echo "Data atual: $DATA_ATUAL"

# Converter para timestamp para comparação correta
TS_ULTIMA=$(date -d "$DATA_ULTIMA" +%s)
TS_ATUAL=$(date -d "$DATA_ATUAL" +%s)

# Sincronizar DESDE a última data (inclusive) ATÉ hoje (inclusive)
DATA_LOOP="$DATA_ULTIMA"
TS_LOOP=$TS_ULTIMA

while [ $TS_LOOP -le $TS_ATUAL ]; do

    ANO=$(date -d "$DATA_LOOP" +%Y)
    MES=$(date -d "$DATA_LOOP" +%m)
    DIA=$(date -d "$DATA_LOOP" +%d)

    echo ""
    echo "=========================================="
    echo "Sincronizando dia: $DATA_LOOP"
    echo "=========================================="

    CAMINHO_ORIGEM="/modelos/tempo/MERGE/GPM/HOURLY/$ANO/$MES/$DIA"
    CAMINHO_DESTINO="/dados/Pessoal/Mestrado/MERGE/GPM/HOURLY/$ANO/$MES/$DIA"

    echo "Origem: $CAMINHO_ORIGEM"
    echo "Destino: $CAMINHO_DESTINO"

    # Faz download incremental (apenas arquivos novos/atualizados)
    lftp -c "
        set ssl:verify-certificate no;
        open https://ftp.cptec.inpe.br;
        mirror --verbose --continue --only-newer \"$CAMINHO_ORIGEM\" \"$CAMINHO_DESTINO\"
    "

    # Verificação: quantos arquivos existem?
    NUM_ARQUIVOS=$(ls "$CAMINHO_DESTINO"/*.grib2 2>/dev/null | wc -l)
    
    echo "Arquivos .grib2 baixados: $NUM_ARQUIVOS de 24"

    if [[ $NUM_ARQUIVOS -ge 24 ]]; then
        echo "✓ Dia completo (24/24 arquivos)"
    elif [[ $NUM_ARQUIVOS -gt 0 ]]; then
        echo "⚠ Dia incompleto ($NUM_ARQUIVOS/24 arquivos)"
    else
        echo "✗ Sem arquivos (diretório vazio ou inexistente)"
    fi

    # Avançar para o próximo dia
    DATA_LOOP=$(date -I -d "$DATA_LOOP + 1 day")
    TS_LOOP=$(date -d "$DATA_LOOP" +%s)
done

# Atualizar log com a data atual (sempre)
echo "$DATA_ATUAL" > "$LOGFILE"

echo ""
echo "=========================================="
echo "Sincronização concluída!"
echo "Última data no log: $DATA_ATUAL"
echo "=========================================="