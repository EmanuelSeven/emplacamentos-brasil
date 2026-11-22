"""Testes da camada gold (VIEWs), com bronze inventada em memória.

Cada teste monta a bronze, roda os .sql reais da silver e da gold, e
compara a VIEW com valores calculados à mão.
"""

import pytest

from conftest import inserir_emplacamentos, inserir_selic, rodar_camadas


def data_api(ano, mes):
    """Data no formato da API: '01/mm/aaaa'."""
    return f"01/{mes:02d}/{ano}"


def test_tendencia_acumulado_null_antes_de_12_meses_e_soma_no_12o(conexao):
    # Total (7389) de 01/2023 a 01/2024 (13 meses), quantidades 10, 20, ..., 130.
    meses = [(2023, m) for m in range(1, 13)] + [(2024, 1)]
    inserir_emplacamentos(
        conexao,
        [(7389, data_api(a, m), str(10 * (i + 1))) for i, (a, m) in enumerate(meses)],
    )
    rodar_camadas(conexao, "silver", "gold")

    linhas = conexao.execute(
        "SELECT mes, acumulado_12m FROM vw_tendencia WHERE categoria = 'total' ORDER BY mes"
    ).fetchall()
    acumulado = {l["mes"]: l["acumulado_12m"] for l in linhas}

    # Meses 1 a 11 (2023-01 a 2023-11): ainda não há 12 meses -> NULL.
    for m in range(1, 12):
        assert acumulado[f"2023-{m:02d}-01"] is None
    # 12º mês (2023-12): 10 + 20 + ... + 120 = 10 x (1 + ... + 12) = 10 x 78 = 780.
    assert acumulado["2023-12-01"] == 780
    # 13º mês (2024-01): janela anda 1 mês: 780 - 10 + 130 = 900.
    assert acumulado["2024-01-01"] == 900


def test_mix_soma_100_e_total_nao_entra_como_categoria(conexao):
    # Ano 2023, 2 meses. Cada mês: as 4 categorias somam exatamente o total.
    #   jan: automoveis 70, comerciais_leves 20, caminhoes 7, onibus 3, total 100
    #   fev: automoveis 140, comerciais_leves 40, caminhoes 14, onibus 6, total 200
    # No ano: total = 300; automoveis 210 (70%), comerciais_leves 60 (20%),
    #         caminhoes 21 (7%), onibus 9 (3%). Soma = 100%.
    dados = {7384: (70, 140), 7385: (20, 40), 7386: (7, 14), 7387: (3, 6), 7389: (100, 200)}
    linhas = []
    for codigo, (jan, fev) in dados.items():
        linhas.append((codigo, "01/01/2023", str(jan)))
        linhas.append((codigo, "01/02/2023", str(fev)))
    inserir_emplacamentos(conexao, linhas)
    rodar_camadas(conexao, "silver", "gold")

    mix = {
        l["categoria"]: l
        for l in conexao.execute("SELECT * FROM vw_mix WHERE ano = 2023")
    }
    # O total é o denominador, não uma fatia: só as 4 categorias aparecem.
    assert set(mix) == {"automoveis", "comerciais_leves", "caminhoes", "onibus"}
    assert mix["automoveis"]["participacao_pct"] == pytest.approx(70.0)
    assert mix["comerciais_leves"]["participacao_pct"] == pytest.approx(20.0)
    assert mix["caminhoes"]["participacao_pct"] == pytest.approx(7.0)
    assert mix["onibus"]["participacao_pct"] == pytest.approx(3.0)
    assert sum(l["participacao_pct"] for l in mix.values()) == pytest.approx(100.0)
    assert mix["automoveis"]["total_ano"] == 300
    assert mix["automoveis"]["meses_no_ano"] == 2


def test_sazonalidade_ignora_ano_incompleto(conexao):
    # 2022 completo (12 meses) no total: jan 50, fev 150, mar a dez 100.
    #   Média mensal de 2022 = (50 + 150 + 10 x 100) / 12 = 1200 / 12 = 100.
    #   Índices: jan 50/100 x 100 = 50; fev 150; demais 100.
    # 2023 incompleto (só jan e fev), com valores bem diferentes (1000 e 10):
    #   se entrasse, mudaria os índices de jan e fev e anos_usados seria 2.
    linhas = [(7389, data_api(2022, 1), "50"), (7389, data_api(2022, 2), "150")]
    linhas += [(7389, data_api(2022, m), "100") for m in range(3, 13)]
    linhas += [(7389, data_api(2023, 1), "1000"), (7389, data_api(2023, 2), "10")]
    inserir_emplacamentos(conexao, linhas)
    rodar_camadas(conexao, "silver", "gold")

    saz = {
        l["mes_do_ano"]: l
        for l in conexao.execute("SELECT * FROM vw_sazonalidade WHERE categoria = 'total'")
    }
    assert len(saz) == 12
    assert all(l["anos_usados"] == 1 for l in saz.values())  # só 2022
    assert saz[1]["indice_medio"] == pytest.approx(50.0)
    assert saz[2]["indice_medio"] == pytest.approx(150.0)
    assert saz[3]["indice_medio"] == pytest.approx(100.0)


def test_juros_correlacao_inversa_e_meses_usados_por_defasagem(conexao):
    # 14 meses, de 2000-01 a 2001-02, nas duas séries.
    #   Selic alterna 1.0 e 2.0 % ao mês (meses ímpares da lista: 1.0; pares: 2.0).
    #   Emplacamentos (total) alternam 200 e 100: Selic baixa -> 200; Selic alta -> 100.
    # Com só dois valores de Selic, a relação é exatamente uma reta decrescente,
    # então na defasagem 0 a correlação de Pearson é -1.
    #
    # Pares por defasagem N: Selic do mês X contra emplacamentos de X + N.
    #   Com 14 meses, há 14 - N pares: N=0 -> 14, N=1 -> 13, ..., N=12 -> 2.
    #
    # Caso de borda: 1999-12 existe nas duas séries, com Selic 80% ao mês.
    # Está antes do recorte (2000-01), então não pode entrar; se entrasse,
    # meses_usados seria 15 na defasagem 0.
    meses = [(2000, m) for m in range(1, 13)] + [(2001, 1), (2001, 2)]
    selic = [(data_api(a, m), "1.0" if i % 2 == 0 else "2.0") for i, (a, m) in enumerate(meses)]
    emplac = [(7389, data_api(a, m), "200" if i % 2 == 0 else "100") for i, (a, m) in enumerate(meses)]
    selic.append(("01/12/1999", "80.0"))
    emplac.append((7389, "01/12/1999", "50"))
    inserir_selic(conexao, selic)
    inserir_emplacamentos(conexao, emplac)
    rodar_camadas(conexao, "silver", "gold")

    linhas = conexao.execute(
        "SELECT defasagem_meses, correlacao, meses_usados FROM vw_juros_emplacamentos "
        "ORDER BY defasagem_meses"
    ).fetchall()

    assert [l["defasagem_meses"] for l in linhas] == list(range(13))
    assert linhas[0]["correlacao"] == pytest.approx(-1.0, abs=1e-9)
    assert [l["meses_usados"] for l in linhas] == [14 - n for n in range(13)]
