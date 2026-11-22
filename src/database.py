"""Conexão com o banco SQLite do projeto.

Os caminhos são calculados a partir deste arquivo, para o projeto funcionar
de qualquer pasta de onde o comando for executado.
"""

import os
import sqlite3

# Raiz do projeto: a pasta acima de src/
PASTA_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASTA_DATA = os.path.join(PASTA_BASE, "data")
PASTA_SQL = os.path.join(PASTA_BASE, "sql")
CAMINHO_BANCO = os.path.join(PASTA_DATA, "emplacamentos.db")


def conectar(caminho=CAMINHO_BANCO):
    """Abre uma conexão com o banco e devolve a conexão configurada."""
    # data/ não vai para o git; sem isto, um clone novo falharia ao abrir o banco.
    # (":memory:" não precisa de pasta.)
    if caminho != ":memory:":
        os.makedirs(os.path.dirname(caminho), exist_ok=True)

    conexao = sqlite3.connect(caminho)
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA foreign_keys = ON")
    return conexao
