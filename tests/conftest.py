"""Ferramentas comuns dos testes.

Todos os testes usam um banco em memória (conectar(":memory:")) com dados
INVENTADOS. Nenhum teste abre data/emplacamentos.db nem chama a API.
Os testes executam os .sql reais do projeto (sql/bronze, sql/silver, sql/gold).
"""

import os

import pytest
import requests

from database import PASTA_SQL, conectar
from ingestao import criar_bronze
from transformacao import executar_script, listar_scripts

# carregado_em padrão dos dados inventados: bem depois de todos os meses
# usados nos testes, para o filtro de "mês da carga" da silver_selic não
# interferir (exceto no teste que verifica justamente esse filtro).
CARGA_PADRAO = "2030-06-15 10:00:00"


@pytest.fixture(autouse=True)
def sem_internet(monkeypatch):
    """Garante que nenhum teste acessa a internet: requests.get (API do Banco
    Central) e requests.post (contador no Supabase) falham se forem usados."""
    def bloqueado(*args, **kwargs):
        raise RuntimeError("Teste tentou acessar a internet")
    monkeypatch.setattr(requests, "get", bloqueado)
    monkeypatch.setattr(requests, "post", bloqueado)


@pytest.fixture
def conexao():
    """Banco em memória com as tabelas da bronze criadas (vazias)."""
    con = conectar(":memory:")
    criar_bronze(con)  # executa sql/bronze/01_criar_bronze.sql
    yield con
    con.close()


def inserir_emplacamentos(con, linhas, carregado_em=CARGA_PADRAO):
    """linhas: lista de (codigo_serie, 'dd/mm/aaaa', 'valor em texto')."""
    con.executemany(
        "INSERT INTO bronze_emplacamentos (codigo_serie, data, valor, carregado_em) "
        "VALUES (?, ?, ?, ?)",
        [(c, d, v, carregado_em) for c, d, v in linhas],
    )


def inserir_selic(con, linhas, carregado_em=CARGA_PADRAO):
    """linhas: lista de ('dd/mm/aaaa', 'valor em texto')."""
    con.executemany(
        "INSERT INTO bronze_selic (codigo_serie, data, valor, carregado_em) "
        "VALUES (4390, ?, ?, ?)",
        [(d, v, carregado_em) for d, v in linhas],
    )


def rodar_camadas(con, *camadas):
    """Executa os .sql reais de cada camada pedida ('silver', 'gold'), em ordem."""
    for camada in camadas:
        for caminho in listar_scripts(os.path.join(PASTA_SQL, camada)):
            executar_script(con, caminho)
