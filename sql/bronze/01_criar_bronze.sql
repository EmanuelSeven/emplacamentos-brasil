-- =============================================================================
-- Camada BRONZE: dados brutos da API do Banco Central (SGS)
-- =============================================================================
-- Regra do projeto: a bronze é intocável. Guarda exatamente o que a API
-- devolveu, mais o código da série e a data/hora da carga.
--
-- Formato da API: [{"data": "01/10/2026", "valor": "9498"}]
--
-- Decisões:
-- * DROP TABLE IF EXISTS: o script é recriável. Cada carga baixa a série
--   completa de novo, então recriar a tabela evita duplicar linhas.
-- * data como TEXT, no formato da API (dd/mm/aaaa): a conversão para
--   'AAAA-MM-01' é trabalho da silver. Converter aqui perderia o dado original.
-- * valor como TEXT: a API devolve o número entre aspas. Guardar como texto
--   preserva exatamente o que veio (ex.: "0.97" na Selic). A tipagem é na silver.
-- * Sem CHECK e sem NOT NULL em data/valor: a bronze não valida nada. Se a API
--   mandar algo estranho, queremos ver isso na bronze e tratar na silver,
--   em vez de a carga falhar e esconder o problema.
-- * codigo_serie INTEGER: identifica de qual série veio a linha (a API não
--   devolve o código dentro do JSON; ele vem da URL chamada).
-- * carregado_em TEXT: data e hora da carga, para saber de quando é o dado.
-- * Duas tabelas separadas (emplacamentos e Selic): têm unidades diferentes
--   (veículos x % ao mês) e serão tratadas de forma diferente na silver.
-- =============================================================================

DROP TABLE IF EXISTS bronze_emplacamentos;

CREATE TABLE bronze_emplacamentos (
    codigo_serie INTEGER,   -- 7384, 7385, 7386, 7387 ou 7389
    data         TEXT,      -- como veio da API: 'dd/mm/aaaa'
    valor        TEXT,      -- como veio da API: número em texto (veículos)
    carregado_em TEXT       -- data/hora da carga: 'AAAA-MM-DD HH:MM:SS'
);

DROP TABLE IF EXISTS bronze_selic;

CREATE TABLE bronze_selic (
    codigo_serie INTEGER,   -- 4390 (Selic acumulada no mês, % ao mês)
    data         TEXT,      -- como veio da API: 'dd/mm/aaaa'
    valor        TEXT,      -- como veio da API: número em texto (% ao mês)
    carregado_em TEXT       -- data/hora da carga: 'AAAA-MM-DD HH:MM:SS'
);
