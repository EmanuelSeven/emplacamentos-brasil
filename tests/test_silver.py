"""Testes da camada silver, com bronze inventada em memória."""

import pytest

from conftest import inserir_emplacamentos, inserir_selic, rodar_camadas


def test_data_vira_mes_e_valor_vira_inteiro(conexao):
    # Bronze: '01/03/2024' e '1500' (texto, como a API manda).
    # Esperado à mão: dd/mm/aaaa -> 'AAAA-MM-01' = '2024-03-01';
    # '1500' -> 1500 guardado como INTEGER (não texto nem REAL).
    inserir_emplacamentos(conexao, [(7384, "01/03/2024", "1500")])
    rodar_camadas(conexao, "silver")

    linha = conexao.execute(
        "SELECT mes, categoria, quantidade, typeof(quantidade) AS tipo FROM silver_emplacamentos"
    ).fetchone()
    assert linha["mes"] == "2024-03-01"
    assert linha["categoria"] == "automoveis"  # 7384 = automóveis
    assert linha["quantidade"] == 1500
    assert linha["tipo"] == "integer"


def test_selic_exclui_mes_da_carga_e_mantem_anteriores(conexao):
    # Carga feita em 15/12/2024: dezembro/2024 está em andamento (valor parcial).
    # Esperado à mão: ficam outubro e novembro; sai dezembro.
    inserir_selic(
        conexao,
        [("01/10/2024", "0.93"), ("01/11/2024", "0.79"), ("01/12/2024", "0.40")],
        carregado_em="2024-12-15 09:30:00",
    )
    rodar_camadas(conexao, "silver")

    meses = [l["mes"] for l in conexao.execute("SELECT mes FROM silver_selic ORDER BY mes")]
    assert meses == ["2024-10-01", "2024-11-01"]


def test_selic_ano_por_juros_compostos(conexao):
    # selic_mes = 1.0% ao mês.
    # À mão: (1 + 0,01)^12 = 1,126825...  ->  (1,126825 - 1) x 100 = 12,6825% ao ano.
    # (Se fosse juros simples daria 12,00%; o teste diferencia os dois.)
    inserir_selic(conexao, [("01/01/2024", "1.0")])
    rodar_camadas(conexao, "silver")

    linha = conexao.execute("SELECT selic_mes, selic_ano FROM silver_selic").fetchone()
    assert linha["selic_mes"] == 1.0
    assert linha["selic_ano"] == pytest.approx(12.6825, abs=1e-4)


def test_mesmo_numero_de_linhas_na_bronze_e_na_silver(conexao):
    # 5 séries x 3 meses = 15 linhas na bronze.
    # A silver_emplacamentos não filtra nada, então também deve ter 15.
    linhas = []
    for codigo, base in [(7384, 70), (7385, 20), (7386, 7), (7387, 3), (7389, 100)]:
        for mes in ["01/01/2024", "01/02/2024", "01/03/2024"]:
            linhas.append((codigo, mes, str(base)))
    inserir_emplacamentos(conexao, linhas)
    rodar_camadas(conexao, "silver")

    bronze = conexao.execute("SELECT COUNT(*) FROM bronze_emplacamentos").fetchone()[0]
    silver = conexao.execute("SELECT COUNT(*) FROM silver_emplacamentos").fetchone()[0]
    assert bronze == 15
    assert silver == 15
