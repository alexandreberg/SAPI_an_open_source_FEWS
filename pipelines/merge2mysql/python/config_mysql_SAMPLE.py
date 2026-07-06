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
Configurações de conexão MySQL
Banco: xxxxxxxxxxxxxxx
Tabela: merge
"""

# ============================
# CONFIGURAÇÕES DO BANCO
# ============================

DB_CONFIG = {
    'host': 'xxxxxxxxxxxxxxx',        # ou IP do servidor
    'port': 3306,                # porta padrão MySQL/MariaDB
    'user': 'xxxxxxxxxxxxxxx',       # ALTERAR
    'password': 'xxxxxxxxxxxxxxx',     # ALTERAR
    'database': 'xxxxxxxxxxxxxxx',
    'charset': 'utf8mb4',
    'collation': 'utf8mb4_unicode_ci'
}

# ============================
# MAPEAMENTO DE COLUNAS
# ============================

TABLE_NAME = 'merge'

# Coluna que receberá a precipitação (mm)
COLUMN_PRECIP = 'prec_mm'

# Mapeamento completo (caso precise usar outras colunas no futuro)
# COLUMNS = {
#     'value1': 'cota',      # ou outro sensor
#     'value2': 'outros_dados',           # ou outro sensor
#     'value3': 'precipitacao_mm',   # MERGE
#     'value4': 'outros_dados',           # ou outro sensor
#     'value5': 'outros_dados'       # campo maior (VARCHAR 50)
# }


# ============================
# VALIDAÇÃO
# ============================

def validar_config():
    """Verifica se as configurações estão corretas"""
    if DB_CONFIG['user'] == 'seu_usuario':
        print("⚠️  ATENÇÃO: Configure o usuário MySQL em config_mysql.py")
        return False
    
    if DB_CONFIG['password'] == 'sua_senha':
        print("⚠️  ATENÇÃO: Configure a senha MySQL em config_mysql.py")
        return False
    
    return True


if __name__ == "__main__":
    # Teste de conexão
    import mysql.connector
    from mysql.connector import Error
    
    if not validar_config():
        print("\n❌ Configure as credenciais antes de usar!")
        exit(1)
    
    print("🔍 Testando conexão...")
    
    try:
        conexao = mysql.connector.connect(**DB_CONFIG)
        
        if conexao.is_connected():
            cursor = conexao.cursor()
            
            # Info do servidor
            cursor.execute("SELECT VERSION()")
            versao = cursor.fetchone()
            
            # Info da tabela
            cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
            total = cursor.fetchone()[0]
            
            print(f"✅ Conectado com sucesso!")
            print(f"   Servidor: {versao[0]}")
            print(f"   Banco: {DB_CONFIG['database']}")
            print(f"   Tabela: {TABLE_NAME}")
            print(f"   Registros: {total:,}")
            
            cursor.close()
            conexao.close()
            
    except Error as e:
        print(f"❌ Erro na conexão: {e}")
        exit(1)
