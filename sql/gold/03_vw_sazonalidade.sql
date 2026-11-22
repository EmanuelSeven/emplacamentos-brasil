-- =============================================================================
-- GOLD 3: Sazonalidade — quais meses ficam acima/abaixo da média do ano
-- =============================================================================
-- Pergunta: em média, cada mês do ano vende mais ou menos que um mês típico?
-- Uma linha = uma categoria (as 5) em um mês do ano (1 a 12).
-- Lê só de silver_emplacamentos.
--
-- Decisões:
-- * DROP VIEW IF EXISTS: script recriável.
-- * Índice do mês = quantidade do mês ÷ média mensal do PRÓPRIO ano × 100
--   (decisão do autor). Comparar com a média do próprio ano tira o efeito do
--   tamanho do mercado em cada ano (1992 e 2013 têm escalas bem diferentes).
--   100 = mês na média do ano; acima de 100 = acima da média; abaixo = abaixo.
-- * indice_medio = média desse índice entre os anos usados (AVG).
-- * Só ANOS COMPLETOS, com 12 meses (decisão do autor): em ano incompleto a
--   média do ano fica distorcida (1990 não tem janeiro; o último ano não tem
--   os meses finais). Hoje isso deixa 1991 a 2025.
-- * anos_usados: quantos anos entraram na média de cada mês, para conferência.
-- * As 5 categorias, cada uma com seu próprio índice; nada é somado entre
--   categorias.
-- * Média do ano e meses do ano por função de janela (PARTITION BY categoria,
--   ano), para comparar cada mês com o seu ano sem um JOIN extra.
-- * Índice em REAL (× 100.0) e sem arredondamento.
-- =============================================================================

DROP VIEW IF EXISTS vw_sazonalidade;

CREATE VIEW vw_sazonalidade AS
WITH meses AS (
    SELECT
        categoria,
        CAST(substr(mes, 1, 4) AS INTEGER) AS ano,
        CAST(substr(mes, 6, 2) AS INTEGER) AS mes_do_ano,
        quantidade,
        AVG(quantidade) OVER ano_da_categoria AS media_mensal_do_ano,
        COUNT(*)        OVER ano_da_categoria AS meses_no_ano
    FROM silver_emplacamentos
    WINDOW ano_da_categoria AS (PARTITION BY categoria, substr(mes, 1, 4))
)
SELECT
    categoria,
    mes_do_ano,
    AVG(quantidade * 100.0 / media_mensal_do_ano) AS indice_medio,
    COUNT(*) AS anos_usados
FROM meses
WHERE meses_no_ano = 12
GROUP BY categoria, mes_do_ano
ORDER BY categoria, mes_do_ano;
