-- =============================================================================
-- Camada SILVER: Selic mensal limpa e tipada
-- =============================================================================
-- Origem: bronze_selic (série 4390 do SGS: Selic acumulada no mês, % ao mês).
-- Uma linha = taxa Selic de um mês fechado, em % ao mês e anualizada.
--
-- Decisões:
-- * DROP TABLE IF EXISTS: o script é recriável; a silver é sempre refeita
--   inteira a partir da bronze.
-- * mes TEXT 'AAAA-MM-01' PRIMARY KEY: mesmo formato da silver_emplacamentos,
--   para o JOIN por mês na gold. Convertido de 'dd/mm/aaaa' com substr
--   (posições fixas; conferido que todas as datas seguem esse formato).
--   A chave primária garante um único valor por mês.
-- * selic_mes REAL: % ao mês, exatamente o número que a API manda, só
--   convertido de texto para número (a API usa ponto decimal, ex.: "1.07").
-- * selic_ano REAL: % ao ano por juros compostos,
--   ((1 + selic_mes/100)^12 - 1) * 100. Guardamos as duas unidades porque a
--   série vem ao mês, mas a Selic costuma ser lida ao ano. Anualizar por juros
--   compostos (e não multiplicar por 12) é o correto para taxa acumulada.
--   pow() existe no SQLite do .venv (3.53.4, conferido em 22/11/2026).
-- * Somente meses FECHADOS: o mês da carga está em andamento e a série é
--   acumulada no mês, então o valor dele é parcial (ex.: 11/2026 = 0.66
--   contra 1.07 em 10/2026). O corte usa o carregado_em da própria bronze, e
--   não a data de hoje do computador: assim o resultado depende só do dado
--   carregado, e rodar a silver de novo outro dia dá o mesmo resultado.
--   Mantém só mes < primeiro dia do mês da carga (o "<" também descartaria
--   qualquer mês posterior à carga, que não deveria existir).
-- * Histórico completo (desde 08/1986): o recorte de período (a Selic passa de
--   80% ao mês antes do Plano Real) é decidido na gold, no indicador de juros.
-- * Sem CHECK em selic_mes: não foi definido um intervalo válido para a taxa.
-- =============================================================================

DROP TABLE IF EXISTS silver_selic;

CREATE TABLE silver_selic (
    mes       TEXT PRIMARY KEY,   -- 'AAAA-MM-01'
    selic_mes REAL NOT NULL,      -- % ao mês (como vem da API)
    selic_ano REAL NOT NULL       -- % ao ano, anualizada por juros compostos
);

INSERT INTO silver_selic (mes, selic_mes, selic_ano)
SELECT
    mes,
    selic_mes,
    (pow(1 + selic_mes / 100.0, 12) - 1) * 100 AS selic_ano
FROM (
    SELECT
        -- 'dd/mm/aaaa' -> 'AAAA-MM-01'
        substr(data, 7, 4) || '-' || substr(data, 4, 2) || '-01' AS mes,
        CAST(valor AS REAL) AS selic_mes,
        -- '2026-11-22 14:11:59' -> '2026-11-01' (mês da carga)
        substr(carregado_em, 1, 7) || '-01' AS mes_da_carga
    FROM bronze_selic
)
WHERE mes < mes_da_carga;
