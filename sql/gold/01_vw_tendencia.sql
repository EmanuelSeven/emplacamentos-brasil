-- =============================================================================
-- GOLD 1: Tendência — emplacamentos mensais e acumulado de 12 meses
-- =============================================================================
-- Pergunta: como os emplacamentos evoluem, mês a mês e no acumulado de 12 meses?
-- Uma linha = um mês de uma categoria (as 5, incluindo 'total').
-- Lê só de silver_emplacamentos.
--
-- Decisões:
-- * DROP VIEW IF EXISTS: script recriável. VIEW (e não tabela) porque o
--   indicador é sempre recalculado a partir da silver, sem cópia de dados.
-- * As 5 categorias, incluindo 'total': cada uma é uma série própria; aqui
--   nada é somado entre categorias, então o total não conta em dobro.
-- * acumulado_12m = soma do mês com os 11 anteriores (janela móvel
--   ROWS BETWEEN 11 PRECEDING AND CURRENT ROW). Tira a sazonalidade do mês e
--   mostra a tendência. Janela por LINHAS funciona porque a série não tem
--   buracos: conferido em 22/11/2026, 441 meses seguidos de 1990-02 a 2026-10
--   em cada categoria (a PRIMARY KEY da silver impede mês repetido).
-- * acumulado_12m é NULL enquanto não houver 12 meses (decisão do autor): os
--   11 primeiros meses (1990-02 a 1990-12) teriam uma soma parcial, que
--   pareceria uma queda falsa. COUNT(*) na mesma janela confere os 12 meses.
-- * variacao_12m_pct = acumulado do mês contra o acumulado de 12 meses antes
--   (LAG de 12 linhas), em %. NULL quando não há acumulado 12 meses antes
--   (até 1991-12). Comparar com o mesmo mês do ano anterior evita efeito
--   sazonal. Multiplicado por 1.0 para não virar divisão inteira.
-- * Sem arredondamento: a formatação fica na exibição.
-- =============================================================================

DROP VIEW IF EXISTS vw_tendencia;

CREATE VIEW vw_tendencia AS
WITH acumulado AS (
    SELECT
        mes,
        categoria,
        quantidade,
        CASE
            WHEN COUNT(*) OVER janela_12m = 12 THEN SUM(quantidade) OVER janela_12m
        END AS acumulado_12m
    FROM silver_emplacamentos
    WINDOW janela_12m AS (
        PARTITION BY categoria
        ORDER BY mes
        ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
    )
)
SELECT
    mes,
    categoria,
    quantidade,
    acumulado_12m,
    (acumulado_12m * 1.0
        / LAG(acumulado_12m, 12) OVER (PARTITION BY categoria ORDER BY mes)
        - 1) * 100 AS variacao_12m_pct
FROM acumulado
ORDER BY categoria, mes;
