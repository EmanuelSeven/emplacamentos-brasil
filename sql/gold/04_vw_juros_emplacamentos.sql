-- =============================================================================
-- GOLD 4: Juros × emplacamentos — correlação com defasagem
-- =============================================================================
-- Pergunta: a Selic de um mês se relaciona com os emplacamentos dos meses
-- seguintes? Em quantos meses a relação aparece mais forte?
-- Uma linha = uma defasagem (0 a 12 meses), com a correlação e os meses usados.
-- Lê só de silver_selic e silver_emplacamentos.
--
-- Decisões:
-- * DROP VIEW IF EXISTS: script recriável.
-- * Defasagem de 0 a 12 meses (decisão do autor): Selic do mês X contra
--   emplacamentos do mês X + N. Juros afetam o crédito e a compra com atraso.
--   As 13 defasagens são geradas com um CTE recursivo, sem tabela auxiliar.
-- * Selic em selic_ano (% ao ano), decisão do autor: é a unidade em que a
--   taxa é lida. Emplacamentos da categoria 'total' (7389), decisão do autor.
-- * JOIN por mês no formato 'AAAA-MM-01' (padronizado na silver). O mês
--   X + N é calculado com date(mes, '+N months'); como o dia é sempre 01,
--   não há problema de fim de mês.
-- * Recorte: Selic a partir de 2000-01 (decisão do autor). Depois do câmbio
--   flutuante e do regime de metas de inflação (1999); antes, a Selic passa
--   de 80% ao mês e distorce a relação. O recorte vale para o mês X da Selic;
--   os emplacamentos usados começam em 2000-01 + N.
-- * INNER JOIN: um par só entra se existirem os dois lados. Nas defasagens
--   maiores, os últimos N meses de Selic ainda não têm emplacamento X + N,
--   por isso meses_usados cai de um em um (ex.: N = 12 perde 12 meses).
-- * Correlação de Pearson sobre os NÍVEIS (valores do mês, não variações),
--   decisão do autor, calculada em SQL pela forma centrada:
--     r = SUM((x - média x)(y - média y))
--         / sqrt(SUM((x - média x)^2) * SUM((y - média y)^2))
--   A forma centrada foi escolhida em vez de n*SUM(xy) - SUM(x)*SUM(y):
--   emplacamentos passam de 300 mil por mês, os quadrados somados chegam
--   perto do limite de precisão do REAL e a subtração perderia casas.
--   As médias de cada defasagem vêm de AVG() OVER (PARTITION BY defasagem).
-- * Limitação (vai para o README): correlação não é causalidade, e as duas
--   séries têm tendência e sazonalidade, o que pode inflar ou esconder a
--   relação.
-- =============================================================================

DROP VIEW IF EXISTS vw_juros_emplacamentos;

CREATE VIEW vw_juros_emplacamentos AS
WITH RECURSIVE defasagens(n) AS (
    SELECT 0
    UNION ALL
    SELECT n + 1 FROM defasagens WHERE n < 12
),
pares AS (
    SELECT
        d.n          AS defasagem_meses,
        s.selic_ano  AS x,
        e.quantidade AS y
    FROM defasagens AS d
    JOIN silver_selic AS s
        ON s.mes >= '2000-01-01'
    JOIN silver_emplacamentos AS e
        ON e.categoria = 'total'
       AND e.mes = date(s.mes, '+' || d.n || ' months')
),
centrados AS (
    SELECT
        defasagem_meses,
        x - AVG(x) OVER (PARTITION BY defasagem_meses) AS dx,
        y - AVG(y) OVER (PARTITION BY defasagem_meses) AS dy
    FROM pares
)
SELECT
    defasagem_meses,
    SUM(dx * dy) / sqrt(SUM(dx * dx) * SUM(dy * dy)) AS correlacao,
    COUNT(*) AS meses_usados
FROM centrados
GROUP BY defasagem_meses
ORDER BY defasagem_meses;
