# CLAUDE.md — emplacamentos-brasil

Projeto do **Desafio Final da Trilha Engenharia de Dados JR**.
Pipeline local, do dado bruto aos indicadores, sobre os **emplacamentos de veículos novos no Brasil**.

## Contexto de negócio

O autor trabalha numa indústria de vidros automotivos (laminados e temperados).
Os emplacamentos funcionam como termômetro da demanda das montadoras e apoiam o planejamento de
vendas, produção e compras. **Nenhum dado interno da empresa entra neste repositório**: ele é público.

## Escopo (fechado, não ampliar sem pedir)

- **Fonte:** API pública do Banco Central (SGS). Licença ODbL, citar a fonte no README.
  - URL: `https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados?formato=json`
  - Emplacamentos (fonte original Fenabrave): 7384 (automóveis), 7389 (total).
    Os códigos de comerciais leves, caminhões e ônibus **devem ser confirmados no portal antes de usar**.
  - Selic mensal: confirmar o código no portal antes de usar (candidato: 4390, Selic acumulada no mês).
- **Fora do escopo:** câmbio, PVB, Comex Stat, RENAVAM, DRE. Ficam para os próximos projetos (Pleno/Sênior).

## Perguntas de negócio (cada uma vira um indicador na gold)

1. **Tendência:** emplacamentos mensais por categoria e acumulado de 12 meses.
2. **Mix:** participação de cada categoria no total, ao longo do tempo.
3. **Sazonalidade:** meses acima/abaixo da média do respectivo ano.
4. **Juros × emplacamentos:** relação entre a Selic e os emplacamentos, com defasagem em meses.

## Stack

- Python + **SQLite** (banco em `data/emplacamentos.db`, fora do git)
- `pytest` para os testes
- Painel no terminal (menu numerado em `src/main.py`), no mesmo formato do exemplo da aula

## Estrutura

```
data/                  banco SQLite (não versionado)
sql/bronze/            criação das tabelas brutas
sql/silver/            limpeza e tipagem
sql/gold/              1 arquivo .sql por indicador (cada um cria uma VIEW)
src/database.py        conexão com o banco
src/ingestao.py        API do Banco Central -> bronze
src/transformacao.py   executa os .sql da silver e da gold
src/main.py            menu do painel
tests/                 testes com dados inventados
```

## Regras (obrigatórias)

1. **Bronze é intocável.** Grava exatamente o que a API devolveu, mais a coluna de data/hora de carga
   e o código da série. Nenhuma limpeza, renomeação ou conversão na bronze.
2. **Toda transformação fica em arquivo `.sql`**, nunca escondida dentro do Python.
3. **Gold = um `.sql` por indicador**, cada um criando uma VIEW. O painel lê **só** as VIEWs da gold,
   sem nenhum cálculo no Python ou na tela.
4. **Contar linhas antes e depois** de todo filtro, deduplicação e JOIN, e mostrar os números para o autor.
   Se a contagem mudar de forma inesperada, parar e avisar em vez de corrigir sozinho.
5. **JOIN por mês:** padronizar as datas das duas séries no mesmo formato (primeiro dia do mês) na silver,
   antes do JOIN. Informar os meses que existem de um lado e faltam do outro.
6. **Toda decisão sobre o dado tem um motivo escrito**, em comentário no `.sql` e no README.
7. **Testes** com `pytest`, usando dados inventados em memória (`sqlite3.connect(":memory:")`),
   **sem abrir** `data/emplacamentos.db` e sem chamar a API.
8. **Um commit por etapa**, com mensagem em português dizendo o que mudou. Não juntar etapas num commit.
   Não fazer commit nem push sem o autor pedir.
9. **Não assumir nada que não foi pedido.** Na dúvida, perguntar. Se precisar assumir algo,
   dizer explicitamente o que foi assumido, para o autor registrar na seção da IA do README.
10. Não usar servidores MCP neste projeto (nada de BigQuery ou nuvem).

## Padrões do exemplo da aula (seguir)

- **`src/database.py`**: só `os` e `sqlite3`; caminhos calculados a partir do próprio arquivo
  (`PASTA_BASE` = raiz do projeto); `conectar()` com `row_factory = sqlite3.Row` e
  `PRAGMA foreign_keys = ON` em **toda** conexão.
  **Diferença do nosso projeto:** `data/` não vai para o git, então `conectar()` deve criar a pasta
  `data/` se ela não existir (`os.makedirs(..., exist_ok=True)`), senão o clone falha.
- **Scripts `.sql` recriáveis**: começar com `DROP TABLE/VIEW IF EXISTS`; usar `NOT NULL` e `CHECK`
  (ex.: `CHECK (quantidade >= 0)`); datas como `TEXT` no formato `'AAAA-MM-DD'` (mês = `'AAAA-MM-01'`).
- **`src/queries.py`**: uma função por opção do menu, recebe a conexão e devolve as linhas.
  Diferente da aula, as funções só leem as VIEWs da gold (`SELECT ... FROM vw_...`): a lógica dos
  indicadores fica nos `.sql` de `sql/gold/`, nunca em string dentro do Python.
- **`src/main.py`**: se o banco não existir, roda o pipeline sozinho na primeira execução; menu
  numerado em `while True`; `try / except KeyboardInterrupt / finally conexao.close()`;
  função `imprimir_tabela()` com saída separada por `|`. Formatar números só na exibição
  (ex.: `185.200`), sem calcular nada no Python.
- **Comando para rodar** (a partir da raiz): `python src/main.py`, documentado no topo do `main.py`
  e no README.
- **Conceitos de SQL que o projeto precisa mostrar:** SELECT/WHERE, JOIN, GROUP BY com
  SUM/COUNT/AVG, ORDER BY e VIEW.
- **Testes:** um "seed" pequeno em memória, com casos de borda escolhidos de propósito
  (ex.: um mês que existe nos emplacamentos e falta na Selic), comparando com resultados
  calculados à mão.
- **Teste final antes da entrega:** apagar `data/emplacamentos.db`, seguir só os comandos do README
  e conferir se os indicadores voltam iguais.

## README (obrigatório pelo curso)

Deve conter: fonte (link + licença), o que é uma linha de cada tabela, as três camadas e os indicadores,
como rodar do zero em comandos (incluindo os testes) e a seção
**"Onde a IA errou ou assumiu algo"**, com o erro e como foi descoberto.
