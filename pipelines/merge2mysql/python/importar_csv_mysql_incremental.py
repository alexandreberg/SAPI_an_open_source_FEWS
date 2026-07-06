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
Importador MERGE para MySQL (versão incremental para crontab)

- Importa apenas registros APÓS determinada hora
- Dados MERGE já vêm em UTC (sem conversão de timezone)
- Cria registros horários do MERGE (com value1=NULL para identificar)
- USA INSERT IGNORE para evitar duplicatas
"""

import sys
import pandas as pd
import mysql.connector
from mysql.connector import Error
from datetime import datetime

# Configurações externas
from config_mysql import DB_CONFIG, TABLE_NAME, COLUMN_PRECIP


def conectar_mysql():
    """Conecta ao banco MySQL"""
    try:
        conexao = mysql.connector.connect(**DB_CONFIG)
        if conexao.is_connected():
            print(f"✓ Conectado ao MySQL: {DB_CONFIG['database']}")
            return conexao
    except Error as e:
        print(f"✗ Erro ao conectar: {e}")
        sys.exit(1)


def importar_merge_incremental(csv_file, hora_inicial="00:00"):
    """
    Importa dados do CSV apenas APÓS determinada hora
    Usa INSERT IGNORE para evitar duplicatas (índice único em timestamp)
    
    Args:
        csv_file: Caminho do arquivo CSV
        hora_inicial: Hora inicial no formato HH:MM (importa registros APÓS esta hora)
    """
    
    print("=" * 60)
    print("Importador MERGE → MySQL (INSERT IGNORE)")
    print("=" * 60)
    print(f"Arquivo: {csv_file}")
    print(f"Hora inicial: {hora_inicial}")
    print(f"Tabela: {TABLE_NAME}")
    print()

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

    # Filtrar registros APÓS a hora inicial
    hora_inicial_full = hora_inicial + ":00"
    
    df_filtrado = df[df['time'] >= hora_inicial_full].copy()
    
    if len(df_filtrado) == 0:
        print(f"✓ Nenhum registro novo após {hora_inicial}")
        print(f"  (Arquivo já estava atualizado)")
        return
    
    print(f"✓ {len(df_filtrado)} registros novos para processar")
    print()

    # Conexão MySQL
    conexao = conectar_mysql()
    cursor = conexao.cursor()

    # INSERT IGNORE: insere se não existir, ignora se existir (por causa do índice único)
    query_insert = f"""
        INSERT IGNORE INTO {TABLE_NAME} (timestamp, {COLUMN_PRECIP})
        VALUES (%s, %s)
    """

    inseridos = 0
    ignorados = 0
    erros = 0

    print("Processando registros (INSERT IGNORE)...")

    # Loop pelas linhas filtradas
    for idx, linha in df_filtrado.iterrows():
        try:
            # Dados MERGE já vêm em UTC - apenas parse direto
            dt_utc = datetime.strptime(
                str(linha["date"]) + " " + str(linha["time"]), 
                "%Y-%m-%d %H:%M:%S"
            )
            precip = float(linha["precipitacao_mm"])

            # Executar INSERT IGNORE
            cursor.execute(query_insert, (dt_utc, precip))
            
            # rowcount = 1 se inseriu, 0 se ignorou (já existia)
            if cursor.rowcount == 1:
                inseridos += 1
            else:
                ignorados += 1

        except Exception as e:
            erros += 1
            print(f"✗ Erro na linha {idx + 1}: {e}")

    conexao.commit()
    cursor.close()
    conexao.close()

    print()
    print("===== RESULTADO =====")
    print(f"✓ Inseridos   : {inseridos}")
    if ignorados > 0:
        print(f"⊘ Ignorados   : {ignorados} (já existiam)")
    if erros > 0:
        print(f"✗ Erros       : {erros}")
    print("=====================")
    print()

    # Retorna código de erro se houver falhas
    if erros > 0:
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python3 importar_csv_mysql_incremental.py arquivo.csv [hora_inicial]")
        print("Exemplo: python3 importar_csv_mysql_incremental.py dados.csv 06:00")
        sys.exit(1)
    
    csv_file = sys.argv[1]
    hora_inicial = sys.argv[2] if len(sys.argv) > 2 else "00:00"
    
    # Validar formato da hora
    if not hora_inicial.count(':') == 1:
        print(f"✗ Formato de hora inválido: {hora_inicial}")
        print("Use formato HH:MM (exemplo: 06:00)")
        sys.exit(1)
    
    importar_merge_incremental(csv_file, hora_inicial)
