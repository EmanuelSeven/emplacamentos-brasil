-- =============================================================================
-- Camada SILVER: emplacamentos limpos e tipados
-- =============================================================================
-- Origem: bronze_emplacamentos (dados brutos da API do Banco Central / Fenabrave).
-- Uma linha = quantidade de veículos novos emplacados em um mês, em uma categoria.
--
-- Decisões:
-- * DROP TABLE IF EXISTS: o script é recriável; a silver é sempre refeita
--   inteira a partir da bronze, que também é recarregada inteira.
-- * mes TEXT 'AAAA-MM-01': padrão do projeto para meses. Ordena corretamente
--   como texto e é a mesma chave que a silver_selic usa, para o JOIN por mês
--   na gold. Convertido de 'dd/mm/aaaa' com substr (posições fixas: conferido
--   em 22/11/2026 que todas as datas da bronze seguem dd/mm/aaaa e caem no dia 01).
-- * codigo_serie mantido: liga a linha de volta à série de origem na bronze/API.
-- * categoria em texto, sem acento e sem espaço (automoveis, comerciais_leves,
--   caminhoes, onibus, total): legível no painel e fácil de filtrar em SQL.
--   O CASE não tem ELSE: um código desconhecido vira NULL e o NOT NULL faz a
--   carga falhar, em vez de entrar uma categoria errada calada.
-- * O total (7389) fica como categoria 'total', separado. Ele NUNCA deve ser
--   somado com as outras quatro (contaria tudo em dobro). Conferido em
--   22/11/2026: 7384+7385+7386+7387 = 7389 nos 441 meses.
-- * quantidade INTEGER: são veículos, número inteiro. Na bronze todos os
--   valores têm só dígitos (conferido), então o CAST não perde nada.
--   CHECK (quantidade >= 0): emplacamento negativo não existe; se aparecer,
--   a carga falha e o problema fica visível.
-- * PRIMARY KEY (mes, codigo_serie): um valor por série por mês. Se a API
--   mandar mês repetido, a carga falha em vez de duplicar números.
-- * Sem filtro de linhas: a silver deve ter as mesmas 5 x 441 = 2.205 linhas
--   da bronze. Histórico completo; recortes de período ficam para a gold.
-- =============================================================================

DROP TABLE IF EXISTS silver_emplacamentos;

CREATE TABLE silver_emplacamentos (
    mes          TEXT    NOT NULL,   -- 'AAAA-MM-01'
    codigo_serie INTEGER NOT NULL,   -- 7384, 7385, 7386, 7387 ou 7389
    categoria    TEXT    NOT NULL,   -- automoveis, comerciais_leves, caminhoes, onibus, total
    quantidade   INTEGER NOT NULL CHECK (quantidade >= 0),  -- veículos emplacados no mês
    PRIMARY KEY (mes, codigo_serie)
);

INSERT INTO silver_emplacamentos (mes, codigo_serie, categoria, quantidade)
SELECT
    -- 'dd/mm/aaaa' -> 'AAAA-MM-01'
    substr(data, 7, 4) || '-' || substr(data, 4, 2) || '-01' AS mes,
    codigo_serie,
    CASE codigo_serie
        WHEN 7384 THEN 'automoveis'
        WHEN 7385 THEN 'comerciais_leves'
        WHEN 7386 THEN 'caminhoes'
        WHEN 7387 THEN 'onibus'
        WHEN 7389 THEN 'total'
    END AS categoria,
    CAST(valor AS INTEGER) AS quantidade
FROM bronze_emplacamentos;
