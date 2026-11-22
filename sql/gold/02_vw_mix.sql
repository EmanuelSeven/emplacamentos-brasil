-- =============================================================================
-- GOLD 2: Mix — participação de cada categoria no total, por ano
-- =============================================================================
-- Pergunta: quanto cada categoria representa dos emplacamentos de cada ano?
-- Uma linha = um ano de uma categoria (só as 4: automoveis, comerciais_leves,
-- caminhoes, onibus). Lê só de silver_emplacamentos.
--
-- Decisões:
-- * DROP VIEW IF EXISTS: script recriável.
-- * Por ANO (decisão do autor): o mix mensal oscila muito; o anual mostra a
--   mudança de perfil do mercado ao longo do tempo.
-- * Só as 4 categorias: o 'total' é o denominador, não uma fatia do mix.
-- * Denominador = linha 'total' (7389) do ano, por JOIN com a própria silver
--   (decisão do autor). As 4 somam exatamente o total nos 441 meses
--   (conferido em 22/11/2026), então as participações de cada ano somam 100%.
--   JOIN por ano: os dois lados têm os mesmos anos (1990 a 2026), então
--   nenhuma linha some no JOIN.
-- * meses_no_ano: quantos meses entraram na soma. 1990 começa em fevereiro
--   (11 meses) e o último ano está incompleto. A participação desses anos é
--   válida, mas a quantidade no ano não é comparável com anos completos.
-- * Ano extraído do mes 'AAAA-MM-01' com substr, como inteiro.
-- * Participação em % (× 100.0, sem divisão inteira) e sem arredondamento.
-- =============================================================================

DROP VIEW IF EXISTS vw_mix;

CREATE VIEW vw_mix AS
WITH por_categoria AS (
    SELECT
        CAST(substr(mes, 1, 4) AS INTEGER) AS ano,
        categoria,
        SUM(quantidade) AS quantidade_ano,
        COUNT(*)        AS meses_no_ano
    FROM silver_emplacamentos
    WHERE categoria <> 'total'
    GROUP BY ano, categoria
),
total_ano AS (
    SELECT
        CAST(substr(mes, 1, 4) AS INTEGER) AS ano,
        SUM(quantidade) AS total_ano
    FROM silver_emplacamentos
    WHERE categoria = 'total'
    GROUP BY ano
)
SELECT
    c.ano,
    c.categoria,
    c.quantidade_ano,
    t.total_ano,
    c.quantidade_ano * 100.0 / t.total_ano AS participacao_pct,
    c.meses_no_ano
FROM por_categoria AS c
JOIN total_ano AS t ON t.ano = c.ano
ORDER BY c.ano, c.categoria;
