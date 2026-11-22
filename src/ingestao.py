"""Ingestão: API do Banco Central (SGS) -> camada bronze.

Como rodar (a partir da raiz do projeto):
    python src/ingestao.py

Baixa a série completa de cada código e grava na bronze sem alterar
data nem valor, mais o código da série e a data/hora da carga.
Se qualquer série falhar, a carga para e o erro é mostrado.
"""

import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

from database import PASTA_SQL, conectar

URL_SGS = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados?formato=json"
TIMEOUT_SEGUNDOS = 30

# Fuso de Brasília. No Windows, o zoneinfo precisa do pacote tzdata (requirements.txt).
FUSO_BRASILIA = ZoneInfo("America/Sao_Paulo")

# Códigos aprovados no CLAUDE.md. Tabela da bronze -> lista de códigos.
SERIES = {
    "bronze_emplacamentos": [7384, 7385, 7386, 7387, 7389],
    "bronze_selic": [4390],
}

SCRIPT_BRONZE = os.path.join(PASTA_SQL, "bronze", "01_criar_bronze.sql")


def gerar_carregado_em():
    """Data/hora da carga, SEMPRE no horário de Brasília: 'AAAA-MM-DD HH:MM:SS'.

    Motivo: datetime.now() sem fuso usa o relógio do servidor. No Streamlit
    Cloud ele roda em UTC, 3 h à frente de Brasília: a "última atualização"
    aparecia adiantada e, no último dia do mês depois das 21h, o carregado_em
    já cairia no mês seguinte, e a silver_selic manteria o mês em andamento
    (que é incompleto). Com o fuso explícito, o resultado não depende da máquina.
    """
    return datetime.now(FUSO_BRASILIA).strftime("%Y-%m-%d %H:%M:%S")


def baixar_serie(codigo):
    """Busca a série completa na API e devolve a lista de registros como veio."""
    url = URL_SGS.format(codigo=codigo)
    resposta = requests.get(url, timeout=TIMEOUT_SEGUNDOS)
    resposta.raise_for_status()  # status diferente de 2xx -> erro

    registros = resposta.json()
    if not isinstance(registros, list) or len(registros) == 0:
        raise ValueError(f"Série {codigo}: resposta inesperada da API: {str(registros)[:200]}")
    for registro in registros:
        if "data" not in registro or "valor" not in registro:
            raise ValueError(f"Série {codigo}: registro sem 'data' ou 'valor': {registro}")
    return registros


def criar_bronze(conexao):
    """Executa o script que (re)cria as tabelas da bronze."""
    with open(SCRIPT_BRONZE, encoding="utf-8") as arquivo:
        conexao.executescript(arquivo.read())


def gravar_serie(conexao, tabela, codigo, registros, carregado_em):
    """Insere os registros na bronze exatamente como vieram da API."""
    linhas = [(codigo, r["data"], r["valor"], carregado_em) for r in registros]
    conexao.executemany(
        f"INSERT INTO {tabela} (codigo_serie, data, valor, carregado_em) VALUES (?, ?, ?, ?)",
        linhas,
    )
    return len(linhas)


def resumo_bronze(conexao):
    """Linhas, primeira e última data (na ordem em que a API devolveu) por série."""
    resumo = []
    for tabela, codigos in SERIES.items():
        for codigo in codigos:
            linha = conexao.execute(
                f"""
                SELECT COUNT(*) AS linhas,
                       (SELECT data FROM {tabela} WHERE codigo_serie = ? ORDER BY rowid ASC  LIMIT 1) AS primeira,
                       (SELECT data FROM {tabela} WHERE codigo_serie = ? ORDER BY rowid DESC LIMIT 1) AS ultima
                FROM {tabela}
                WHERE codigo_serie = ?
                """,
                (codigo, codigo, codigo),
            ).fetchone()
            resumo.append((tabela, codigo, linha["linhas"], linha["primeira"], linha["ultima"]))
    return resumo


def main():
    # 1) Baixa tudo antes de tocar no banco: se uma série falhar,
    #    a bronze anterior continua intacta (nada é gravado pela metade).
    baixadas = {}
    for tabela, codigos in SERIES.items():
        for codigo in codigos:
            print(f"Baixando série {codigo}...")
            try:
                baixadas[(tabela, codigo)] = baixar_serie(codigo)
            except Exception as erro:
                print(f"\nERRO na série {codigo}: {type(erro).__name__}: {erro}")
                print("Carga interrompida. Nenhuma alteração foi feita no banco.")
                sys.exit(1)
            print(f"  {len(baixadas[(tabela, codigo)])} registros recebidos")

    # 2) Recria a bronze e grava tudo numa única transação.
    carregado_em = gerar_carregado_em()
    conexao = conectar()
    try:
        criar_bronze(conexao)
        with conexao:
            for (tabela, codigo), registros in baixadas.items():
                gravar_serie(conexao, tabela, codigo, registros, carregado_em)

        # 3) Confere o que ficou gravado, comparando com o que a API devolveu.
        print(f"\nCarga concluída em {carregado_em}\n")
        print("tabela               | série | linhas | primeira data | última data")
        for tabela, codigo, linhas, primeira, ultima in resumo_bronze(conexao):
            print(f"{tabela:<20} | {codigo:>5} | {linhas:>6} | {primeira:<13} | {ultima}")
            recebidas = len(baixadas[(tabela, codigo)])
            if linhas != recebidas:
                print(f"  ATENÇÃO: API devolveu {recebidas} linhas e a bronze tem {linhas}.")
    finally:
        conexao.close()


if __name__ == "__main__":
    main()
