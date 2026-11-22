"""Testes da ingestão (sem internet) e da formatação do painel."""

import pytest

import ingestao
from main import formatar


class RespostaFalsa:
    """Imita o objeto de resposta do requests, sem rede."""

    def __init__(self, dados):
        self._dados = dados

    def raise_for_status(self):
        pass  # status 200

    def json(self):
        return self._dados


def test_baixar_serie_falha_com_lista_vazia(monkeypatch):
    # A API responde 200 mas com []: não há dado para gravar.
    # Esperado: ValueError (a carga deve parar, e não gravar uma série vazia).
    monkeypatch.setattr(ingestao.requests, "get", lambda url, timeout: RespostaFalsa([]))
    with pytest.raises(ValueError):
        ingestao.baixar_serie(7389)


def test_gravar_serie_grava_data_e_valor_como_texto(conexao):
    # Valores escolhidos de propósito: '0.10' viraria 0.1 se fosse convertido
    # para número, e a data em dd/mm/aaaa não pode ser reformatada.
    # Esperado: tudo gravado exatamente como recebido, com tipo TEXT.
    registros = [
        {"data": "01/10/2026", "valor": "0.10"},
        {"data": "01/11/2026", "valor": "1.07"},
    ]
    gravadas = ingestao.gravar_serie(
        conexao, "bronze_selic", 4390, registros, "2026-11-22 14:11:59"
    )
    assert gravadas == 2

    linhas = conexao.execute(
        "SELECT codigo_serie, data, valor, carregado_em, typeof(data) AS tipo_data, "
        "typeof(valor) AS tipo_valor FROM bronze_selic ORDER BY rowid"
    ).fetchall()
    assert [(l["data"], l["valor"]) for l in linhas] == [
        ("01/10/2026", "0.10"),
        ("01/11/2026", "1.07"),
    ]
    assert all(l["tipo_data"] == "text" and l["tipo_valor"] == "text" for l in linhas)
    assert all(l["codigo_serie"] == 4390 for l in linhas)
    assert all(l["carregado_em"] == "2026-11-22 14:11:59" for l in linhas)


def test_formatar_numeros_do_painel():
    # Inteiro: ponto de milhar.
    assert formatar(3039871, "acumulado_12m") == "3.039.871"
    # Decimal: 2 casas com vírgula (13,3388 arredonda para 13,34).
    assert formatar(13.3388, "variacao_12m_pct") == "13,34"
    # NULL: traço.
    assert formatar(None, "acumulado_12m") == "-"
    # Ano é rótulo, não quantidade: sem ponto de milhar.
    assert formatar(2024, "ano") == "2024"
