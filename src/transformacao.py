"""Transformação: executa os scripts .sql da camada silver.

Como rodar (a partir da raiz do projeto, depois de src/ingestao.py):
    python src/transformacao.py

Executa os arquivos .sql de sql/silver em ordem alfabética (por isso os
nomes começam com 01_, 02_...). Toda a lógica fica nos .sql; este arquivo
só executa os scripts e conta as linhas antes e depois.
"""

import os
import sys

from database import PASTA_SQL, conectar

PASTA_SILVER = os.path.join(PASTA_SQL, "silver")

# Pares (bronze de origem, silver de destino) para conferir as contagens.
PARES_CONTAGEM = [
    ("bronze_emplacamentos", "silver_emplacamentos"),
    ("bronze_selic", "silver_selic"),
]


def listar_scripts(pasta):
    """Arquivos .sql da pasta, em ordem alfabética."""
    return sorted(
        os.path.join(pasta, nome) for nome in os.listdir(pasta) if nome.endswith(".sql")
    )


def executar_script(conexao, caminho):
    """Executa um arquivo .sql inteiro."""
    with open(caminho, encoding="utf-8") as arquivo:
        conexao.executescript(arquivo.read())


def tabela_existe(conexao, nome):
    linha = conexao.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (nome,)
    ).fetchone()
    return linha is not None


def contar(conexao, tabela):
    """Linhas da tabela, ou None se ela ainda não existe."""
    if not tabela_existe(conexao, tabela):
        return None
    return conexao.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]


def contagens(conexao):
    return {
        tabela: contar(conexao, tabela)
        for par in PARES_CONTAGEM
        for tabela in par
    }


def main():
    conexao = conectar()
    try:
        for bronze, _ in PARES_CONTAGEM:
            if not tabela_existe(conexao, bronze):
                print(f"ERRO: a tabela {bronze} não existe. Rode antes: python src/ingestao.py")
                sys.exit(1)

        antes = contagens(conexao)

        for caminho in listar_scripts(PASTA_SILVER):
            print(f"Executando {os.path.relpath(caminho, PASTA_SQL)}...")
            executar_script(conexao, caminho)

        depois = contagens(conexao)

        print("\nLinhas antes e depois da silver:")
        print("tabela               | antes | depois")
        for tabela in antes:
            valor_antes = "-" if antes[tabela] is None else antes[tabela]
            print(f"{tabela:<20} | {valor_antes:>5} | {depois[tabela]:>6}")
    finally:
        conexao.close()


if __name__ == "__main__":
    main()
