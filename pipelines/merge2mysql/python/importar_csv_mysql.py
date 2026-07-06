#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2024–2026 Alexandre Nuernberg <alexandreberg@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
"""
Importador MERGE para MySQL (dados já em UTC)

- Ignora as 3 primeiras linhas do CSV MERGE
- Dados MERGE já vêm em UTC (sem conversão de timezone)
- Atualiza SOMENTE o campo value3 (precipitação) de registros existentes
- Se reading_time não existir no banco, insere novo registro
- NÃO mexe em value1, value2, value4, value5
"""

import sys
import pandas as pd
import mysql.connector
from mysql.connector import Error
from datetime import datetime

# Configurações externas
from config_mysql import DB_CONFIG, TABLE_NAME, COLUMN_PRECIP


# ============================
#   FUNÇÃO: Conectar MySQL
# ============================
def conectar_mysql():
    try:
        conexao = mysql.connector.connect(**DB_CONFIG)
        if conexao.is_connected():
            print(f"✓ Conectado ao MySQL: {DB_CONFIG['database']}")
            return conexao
    except Error as e:
        print(f"✗ Erro ao conectar: {e}")
        sys.exit(1)


# ============================
#     FUNÇÃO PRINCIPAL
# ============================
def importar_merge(csv_file):

    print("=" * 60)
    print("Importador MERGE → MySQL (dados já em UTC)")
    print("=" * 60)
    print(f"Arquivo: {csv_file}")
    print(f"Tabela: {TABLE_NAME}\n")

    # Ler CSV ignorando as 3 primeiras linhas
    try:
        df = pd.read_csv(csv_file, skiprows=2)
        print(f"✓ CSV lido com {len(df)} registros")
    except Exception as e:
        print(f"✗ Erro ao ler CSV: {e}")
        sys.exit(1)

    # Verificar colunas
    colunas_necessarias = ["date", "time", "precipitacao_mm"]
    for c in colunas_necessarias:
        if c not in df.columns:
            print(f"✗ Erro: coluna '{c}' ausente no CSV!")
            print(f"Colunas encontradas: {list(df.columns)}")
            sys.exit(1)

    # Conexão MySQL
    conexao = conectar_mysql()
    cursor = conexao.cursor()

    # QUERYs de update e insert
    query_update = f"""
        UPDATE {TABLE_NAME}
        SET {COLUMN_PRECIP} = %s
        WHERE reading_time = %s
    """

    query_insert = f"""
        INSERT INTO {TABLE_NAME} (reading_time, {COLUMN_PRECIP})
        VALUES (%s, %s)
    """

    atualizados = 0
    inseridos = 0
    erros = 0

    print("Processando registros...")

    # Loop pelas linhas
    for idx, linha in df.iterrows():
        try:
            # Dados MERGE já vêm em UTC - apenas parse direto
            dt_utc = datetime.strptime(
                str(linha["date"]) + " " + str(linha["time"]), 
                "%Y-%m-%d %H:%M:%S"
            )
            precip = float(linha["precipitacao_mm"])

            # Primeiro tenta UPDATE
            cursor.execute(query_update, (precip, dt_utc))
            if cursor.rowcount > 0:
                atualizados += 1
                continue

            # Se não existia -> INSERT
            cursor.execute(query_insert, (dt_utc, precip))
            inseridos += 1

        except Exception as e:
            erros += 1
            print(f"✗ Erro na linha {idx + 1}: {e}")

    conexao.commit()
    cursor.close()
    conexao.close()

    print("\n===== RESULTADO =====")
    print(f"✓ Atualizados : {atualizados}")
    print(f"✓ Inseridos   : {inseridos}")
    if erros > 0:
        print(f"✗ Erros       : {erros}")
    print("=====================\n")

    # Retorna código de erro se houver falhas
    if erros > 0:
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python3 importar_csv_mysql.py arquivo.csv")
        sys.exit(1)

    importar_merge(sys.argv[1])
