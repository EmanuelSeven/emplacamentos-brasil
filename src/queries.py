"""Consultas do painel: uma função por opção do menu.

Cada função recebe a conexão e devolve as linhas. As consultas leem SOMENTE
as VIEWs da gold e usam apenas SELECT, WHERE, ORDER BY e LIMIT: toda a lógica
dos indicadores (somas, médias, percentuais) está nos .sql de sql/gold/.
Valores digitados pelo usuário entram como parâmetro (?), nunca na string do SQL.
"""


def ultimos_12_meses_por_categoria(conexao):
    """Opção 2: quantidade de cada categoria nos 12 meses mais recentes."""
    return conexao.execute(
        """
        SELECT mes, categoria, quantidade
        FROM vw_tendencia
        WHERE mes IN (
            SELECT mes FROM vw_tendencia
            WHERE categoria = 'total'
            ORDER BY mes DESC
            LIMIT 12
        )
        ORDER BY mes DESC, categoria
        """
    ).fetchall()


def categorias_validas(conexao):
    """Opção 3 (apoio): categorias existentes no mês mais recente."""
    linhas = conexao.execute(
        """
        SELECT categoria
        FROM vw_tendencia
        WHERE mes = (SELECT mes FROM vw_tendencia ORDER BY mes DESC LIMIT 1)
        ORDER BY categoria
        """
    ).fetchall()
    return [linha["categoria"] for linha in linhas]


def filtrar_categoria(conexao, categoria):
    """Opção 3: os 24 meses mais recentes de uma categoria."""
    return conexao.execute(
        """
        SELECT mes, categoria, quantidade, acumulado_12m, variacao_12m_pct
        FROM vw_tendencia
        WHERE categoria = ?
        ORDER BY mes DESC
        LIMIT 24
        """,
        (categoria,),
    ).fetchall()


def tendencia_total(conexao):
    """Opção 4: acumulado de 12 meses do total, nos 12 meses mais recentes."""
    return conexao.execute(
        """
        SELECT mes, quantidade, acumulado_12m, variacao_12m_pct
        FROM vw_tendencia
        WHERE categoria = 'total'
        ORDER BY mes DESC
        LIMIT 12
        """
    ).fetchall()


def mix_anual(conexao):
    """Opção 5: participação de cada categoria no total de cada ano."""
    return conexao.execute(
        """
        SELECT ano, categoria, quantidade_ano, total_ano, participacao_pct, meses_no_ano
        FROM vw_mix
        ORDER BY ano, categoria
        """
    ).fetchall()


def sazonalidade_total(conexao):
    """Opção 6: índice médio de cada mês do ano para o total (100 = média do ano)."""
    return conexao.execute(
        """
        SELECT mes_do_ano, indice_medio, anos_usados
        FROM vw_sazonalidade
        WHERE categoria = 'total'
        ORDER BY mes_do_ano
        """
    ).fetchall()


def juros_emplacamentos(conexao):
    """Opção 7: correlação Selic x emplacamentos por defasagem (0 a 12 meses)."""
    return conexao.execute(
        """
        SELECT defasagem_meses, correlacao, meses_usados
        FROM vw_juros_emplacamentos
        ORDER BY defasagem_meses
        """
    ).fetchall()
