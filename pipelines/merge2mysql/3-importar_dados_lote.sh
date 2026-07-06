#!/bin/bash

# ============================================================
# Script para importação em lote de arquivos CSV MERGE
# NOVA ESTRUTURA SUPORTADA:
#
# CSV/
#   └── 2025/
#        ├── 01/
#        │    ├── estacao01_MERGE_20250101.csv
#        │    ├── ...
#        ├── 02/
#        └── ...
#
# Suporta: diário (arquivo único), mensal (ano/mês), anual.
# ============================================================

VENV_DIR="venv_merge"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/python"
CSV_DIR="CSV"

# Cores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ------------------------------------------------------------
# Validação do ano
# ------------------------------------------------------------
validar_ano() {
    local ano=$1
    if ! [[ "$ano" =~ ^[0-9]{4}$ ]]; then
        return 1
    fi
    return 0
}

# ------------------------------------------------------------
# Validação do mês
# ------------------------------------------------------------
validar_mes() {
    local mes=$1
    if ! [[ "$mes" =~ ^[0-9]{1,2}$ ]] || [ "$mes" -lt 1 ] || [ "$mes" -gt 12 ]; then
        return 1
    fi
    return 0
}

# ------------------------------------------------------------
# Checagens iniciais
# ------------------------------------------------------------
if [ ! -d "$SCRIPT_DIR/$VENV_DIR" ]; then
    echo -e "${RED}✗ Ambiente virtual não encontrado!${NC}"
    echo "Execute: ./setup_ambiente.sh"
    exit 1
fi

if [ ! -f "$SCRIPT_DIR/importar_csv_mysql.py" ]; then
    echo -e "${RED}✗ Script importar_csv_mysql.py não encontrado!${NC}"
    exit 1
fi

if [ ! -d "$CSV_DIR" ]; then
    echo -e "${RED}✗ Diretório CSV não encontrado: $CSV_DIR${NC}"
    exit 1
fi

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   Importação em Lote - MERGE → MySQL${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# ------------------------------------------------------------
# Ativar ambiente virtual
# ------------------------------------------------------------
source "$SCRIPT_DIR/$VENV_DIR/bin/activate"

if [ $? -ne 0 ]; then
    echo -e "${RED}✗ Erro ao ativar ambiente virtual${NC}"
    exit 1
fi

# ------------------------------------------------------------
# Menu principal
# ------------------------------------------------------------
echo -e "${YELLOW}Escolha o tipo de importação:${NC}"
echo "1) Arquivo único (diário)"
echo "2) Mês completo"
echo "3) Ano completo"
echo ""
read -p "Opção [1-3]: " opcao

case $opcao in

    # --------------------------------------------------------
    # 1) Importação diária (arquivo único)
    # --------------------------------------------------------
    1)
        echo ""
        echo "Digite o caminho relativo ao diretório CSV/"
        echo "Exemplo: 2025/01/estacao01_MERGE_20250107.csv"
        echo ""
        read -p "Arquivo: " arquivo_rel

        arquivo="$CSV_DIR/$arquivo_rel"

        if [ ! -f "$arquivo" ]; then
            echo -e "${RED}✗ Arquivo não encontrado: $arquivo${NC}"
            deactivate
            exit 1
        fi

        arquivos=("$arquivo")
        ;;

    # --------------------------------------------------------
    # 2) Importação mensal
    # --------------------------------------------------------
    2)
        echo ""
        read -p "Ano (ex: 2025): " ano
        read -p "Mês (1-12): " mes

        if ! validar_ano "$ano"; then
            echo -e "${RED}✗ Ano inválido!${NC}"
            deactivate
            exit 1
        fi

        if ! validar_mes "$mes"; then
            echo -e "${RED}✗ Mês inválido!${NC}"
            deactivate
            exit 1
        fi

        mes_pad=$(printf "%02d" $mes)

        dir_mes="$CSV_DIR/$ano/$mes_pad"

        if [ ! -d "$dir_mes" ]; then
            echo -e "${RED}✗ Diretório não encontrado: $dir_mes${NC}"
            deactivate
            exit 1
        fi

        mapfile -t arquivos < <(find "$dir_mes" -type f -name "*.csv" | sort)

        if [ ${#arquivos[@]} -eq 0 ]; then
            echo -e "${RED}✗ Nenhum CSV encontrado em $dir_mes${NC}"
            deactivate
            exit 1
        fi

        echo -e "${GREEN}✓ ${#arquivos[@]} arquivos encontrados em ${ano}/${mes_pad}${NC}"
        ;;

    # --------------------------------------------------------
    # 3) Importação anual
    # --------------------------------------------------------
    3)
        echo ""
        read -p "Ano (ex: 2025): " ano

        if ! validar_ano "$ano"; then
            echo -e "${RED}✗ Ano inválido!${NC}"
            deactivate
            exit 1
        fi

        dir_ano="$CSV_DIR/$ano"

        if [ ! -d "$dir_ano" ]; then
            echo -e "${RED}✗ Diretório não encontrado: $dir_ano${NC}"
            deactivate
            exit 1
        fi

        mapfile -t arquivos < <(find "$dir_ano" -type f -name "*.csv" | sort)

        if [ ${#arquivos[@]} -eq 0 ]; then
            echo -e "${RED}✗ Nenhum CSV encontrado no ano ${ano}${NC}"
            deactivate
            exit 1
        fi

        echo -e "${GREEN}✓ ${#arquivos[@]} arquivos encontrados para o ano ${ano}${NC}"
        ;;

    *)
        echo -e "${RED}✗ Opção inválida${NC}"
        deactivate
        exit 1
        ;;
esac

# ------------------------------------------------------------
# Confirmação da lista de arquivos
# ------------------------------------------------------------
echo ""
echo -e "${YELLOW}Arquivos que serão processados:${NC}"
for f in "${arquivos[@]}"; do
    echo " - $(basename "$f")"
done

echo ""
read -p "Confirmar importação? [s/N]: " confirma

if [[ ! "$confirma" =~ ^[SsYy]$ ]]; then
    deactivate
    echo -e "${YELLOW}✗ Operação cancelada${NC}"
    exit 0
fi

# ------------------------------------------------------------
# Processamento
# ------------------------------------------------------------
total_arquivos=${#arquivos[@]}
sucesso=0
erros=0
inicio=$(date +%s)

echo ""
echo -e "${BLUE}Iniciando processamento...${NC}"
echo ""

for ((i=0; i<${#arquivos[@]}; i++)); do
    arquivo="${arquivos[$i]}"
    numero=$((i+1))

    echo -e "${BLUE}[$numero/$total_arquivos]${NC} Processando: $(basename "$arquivo")"

    python3 "$SCRIPT_DIR/importar_csv_mysql.py" "$arquivo"
    if [ $? -eq 0 ]; then
        ((sucesso++))
        echo -e "${GREEN}✓ Sucesso${NC}"
    else
        ((erros++))
        echo -e "${RED}✗ Erro${NC}"
    fi
    echo ""
done

deactivate

# ------------------------------------------------------------
# Resumo final
# ------------------------------------------------------------
fim=$(date +%s)
duracao=$((fim - inicio))
min=$((duracao / 60))
seg=$((duracao % 60))

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}           RESUMO DA IMPORTAÇÃO${NC}"
echo -e "${BLUE}========================================${NC}"
echo "Total de arquivos : $total_arquivos"
echo -e "${GREEN}Sucessos          : $sucesso${NC}"
echo -e "${RED}Erros             : $erros${NC}"
echo "Tempo total       : ${min}m ${seg}s"
echo -e "${BLUE}========================================${NC}"

if [ $erros -gt 0 ]; then
    exit 1
else
    exit 0
fi
