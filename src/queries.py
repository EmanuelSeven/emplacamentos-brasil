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


# --- Consultas usadas só pelo dashboard (src/dashboard.py) ---------------------
# Mesmo padrão: só SELECT, WHERE, ORDER BY e LIMIT sobre as VIEWs da gold.
# Mix, sazonalidade e juros reaproveitam as funções acima.


def ultimo_mes_total(conexao):
    """Dashboard (topo): a linha do mês mais recente da categoria total."""
    return conexao.execute(
        """
        SELECT mes, quantidade, acumulado_12m, variacao_12m_pct
        FROM vw_tendencia
        WHERE categoria = 'total'
        ORDER BY mes DESC
        LIMIT 1
        """
    ).fetchone()


def serie_acumulado_12m(conexao, categoria):
    """Dashboard (gráfico 1): acumulado de 12 meses de uma categoria, mês a mês.

    Os primeiros 11 meses da série (acumulado NULL) ficam de fora com WHERE.
    """
    return conexao.execute(
        """
        SELECT mes, categoria, acumulado_12m, variacao_12m_pct
        FROM vw_tendencia
        WHERE categoria = ?
          AND acumulado_12m IS NOT NULL
        ORDER BY mes
        """,
        (categoria,),
    ).fetchall()


def ultima_carga(conexao):
    """Dashboard (linha abaixo do título): data/hora da última carga da API.

    EXCEÇÃO à regra "só VIEWs da gold", pedida pelo autor: carregado_em só
    existe na bronze, e é um metadado da carga, não um indicador. Só leitura,
    sem cálculo; devolve o texto como foi gravado ('AAAA-MM-DD HH:MM:SS').
    """
    linha = conexao.execute(
        """
        SELECT carregado_em
        FROM bronze_emplacamentos
        ORDER BY carregado_em DESC
        LIMIT 1
        """
    ).fetchone()
    return None if linha is None else linha["carregado_em"]


def colunas_da_view(conexao, view):
    """Dashboard (aba Arquitetura): colunas de uma VIEW, via PRAGMA table_info.

    pragma_table_info(?) é a forma de PRAGMA table_info que aceita o nome
    como parâmetro, em vez de colar o nome na string do SQL.
    """
    return conexao.execute(
        """
        SELECT cid, name, type
        FROM pragma_table_info(?)
        ORDER BY cid
        """,
        (view,),
    ).fetchall()
