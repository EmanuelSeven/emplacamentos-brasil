# Emplacamentos no Brasil: painel de mercado

Pipeline de dados que acompanha os **emplacamentos de veículos novos no Brasil** (automóveis, comerciais
leves, caminhões e ônibus) e a sua relação com os **juros (Selic)**, do dado bruto da API do Banco Central
até indicadores prontos para decisão.

**Por que este tema:** para quem depende da venda de veículos novos, como montadoras, fornecedores de
autopeças e componentes e toda a cadeia automotiva, os emplacamentos funcionam como um **termômetro da
demanda**: ajudam a planejar vendas, produção e compra de matérias-primas. Este projeto usa **somente
dados públicos**.

Desafio Final da **Trilha Engenharia de Dados JR**.

---

## Perguntas de negócio

| # | Pergunta | Para quem serve |
|---|---|---|
| 1 | **Tendência:** como os emplacamentos evoluem mês a mês e no acumulado de 12 meses, por categoria? | Vendas, diretoria |
| 2 | **Mix:** quanto cada categoria representa do total, ano a ano? | Engenharia, vendas |
| 3 | **Sazonalidade:** quais meses ficam acima ou abaixo da média do ano? | Produção (PCP), compras |
| 4 | **Juros × emplacamentos:** quando a Selic sobe, os emplacamentos caem? Com quantos meses de defasagem? | Orçamento, diretoria |

---

## Fonte dos dados

**API pública do Banco Central do Brasil (SGS)**, licença
[Open Data Commons Open Database License (ODbL)](https://opendatacommons.org/licenses/odbl/),
que permite o uso num repositório público citando a fonte.

| Código SGS | Série | Unidade | Início |
|---|---|---|---|
| [7384](https://dadosabertos.bcb.gov.br/dataset/7384-vendas-de-veiculos-pelas-concessionarias---automoveis) | Vendas de veículos pelas concessionárias: Automóveis | veículos | 02/1990 |
| [7385](https://dadosabertos.bcb.gov.br/dataset/7385-vendas-de-veiculos-pelas-concessionarias---comerciais-leves) | Comerciais leves | veículos | 02/1990 |
| [7386](https://dadosabertos.bcb.gov.br/dataset/7386-vendas-de-veiculos-pelas-concessionarias---caminhoes) | Caminhões | veículos | 02/1990 |
| [7387](https://dadosabertos.bcb.gov.br/dataset/7387-vendas-de-veiculos-pelas-concessionarias---onibus) | Ônibus | veículos | 02/1990 |
| [7389](https://dadosabertos.bcb.gov.br/dataset/7389-vendas-de-veiculos-pelas-concessionarias---total) | Total | veículos | 02/1990 |
| [4390](https://dadosabertos.bcb.gov.br/dataset/4390-taxa-de-juros---selic-acumulada-no-mes) | Taxa de juros: Selic acumulada no mês | **% ao mês** | 08/1986 |

As séries de emplacamentos têm como fonte original a **Fenabrave** (Federação Nacional da Distribuição de
Veículos Automotores). Endereço da API:
`https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados?formato=json`

### O que significa cada categoria (e o que fica de fora)
- **Comerciais leves** = picapes (caminhonetes), vans e furgões, com peso bruto abaixo de 3,5 t.
  A API **não separa** vans de picapes.
- **Total (7389)** = soma de automóveis + comerciais leves + caminhões + ônibus. **Não inclui motos nem
  implementos rodoviários**, que entram no "total geral" divulgado pela Fenabrave.
- **Mudança de classificação:** os SUVs eram contados como comerciais leves e passaram a ser automóveis.
  Nos dados, isso aparece como uma quebra no mix entre 2013 (comerciais leves = 21,8%) e 2014 (15,3%).
  **É mudança de régua, não queda do mercado de picapes.**

### Prova cruzada: os números conferem com a Fenabrave
Os totais de **outubro/2026** deste pipeline foram comparados com os divulgados pela imprensa a partir da
Fenabrave, e **batem unidade por unidade**:

| Categoria (out/2026) | Fenabrave (imprensa) | Este pipeline |
|---|---|---|
| Automóveis + comerciais leves | 254.030 | 254.030 ✅ |
| Comerciais leves | 48.066 | 48.066 ✅ |
| Caminhões | 9.498 | 9.498 ✅ |
| Ônibus | 2.061 | 2.061 ✅ |

---

## O que é uma linha de cada tabela

| Camada | Tabela / VIEW | Uma linha é... |
|---|---|---|
| bronze | `bronze_emplacamentos` | um valor de uma série de emplacamentos num mês, **exatamente como a API devolveu** (data e valor em texto) |
| bronze | `bronze_selic` | a Selic de um mês, exatamente como a API devolveu |
| silver | `silver_emplacamentos` | a quantidade de veículos emplacados num mês, numa categoria |
| silver | `silver_selic` | a Selic de um **mês fechado**, em % ao mês e anualizada |
| gold | `vw_tendencia` | um mês de uma categoria, com o acumulado de 12 meses e a variação |
| gold | `vw_mix` | um ano de uma categoria, com a participação % no total do ano |
| gold | `vw_sazonalidade` | um mês do ano (1 a 12) de uma categoria, com o índice médio (100 = média do ano) |
| gold | `vw_juros_emplacamentos` | uma defasagem (0 a 12 meses), com a correlação Selic × emplacamentos |

---

## Camadas e indicadores

```
API do Banco Central (SGS)
        │  src/ingestao.py
        ▼
BRONZE   bronze_emplacamentos, bronze_selic         (bruto, nada é alterado)
        │  sql/silver/*.sql
        ▼
SILVER   silver_emplacamentos, silver_selic         (datas padronizadas, tipos, só meses fechados)
        │  sql/gold/*.sql  (1 arquivo = 1 VIEW = 1 indicador)
        ▼
GOLD     vw_tendencia, vw_mix, vw_sazonalidade, vw_juros_emplacamentos
        │
        ├──► src/main.py       painel no terminal
        └──► src/dashboard.py  dashboard Streamlit (opcional)
```

| Indicador | Arquivo `.sql` de origem |
|---|---|
| Tendência (acumulado 12 meses) | [`sql/gold/01_vw_tendencia.sql`](sql/gold/01_vw_tendencia.sql) |
| Mix anual por categoria | [`sql/gold/02_vw_mix.sql`](sql/gold/02_vw_mix.sql) |
| Sazonalidade | [`sql/gold/03_vw_sazonalidade.sql`](sql/gold/03_vw_sazonalidade.sql) |
| Juros × emplacamentos | [`sql/gold/04_vw_juros_emplacamentos.sql`](sql/gold/04_vw_juros_emplacamentos.sql) |

O painel e o dashboard **só leem as VIEWs da gold**, sem nenhum cálculo na tela. A única exceção, decidida
pelo autor, é a "última atualização" do dashboard, que lê o `carregado_em` da bronze por ser um
**metadado da carga**, e não um indicador.

### Decisões sobre o dado (e por quê)

| Decisão | Motivo |
|---|---|
| Bronze guarda data e valor como **texto**, sem nenhuma conversão | A bronze é intocável: se a API mandar algo estranho, ele fica visível |
| Bronze é **recarregada inteira** a cada execução | A API devolve sempre a série completa; recriar evita duplicar linhas |
| Datas viram `'AAAA-MM-01'` na silver | Ordena corretamente como texto e é a chave do JOIN por mês |
| Selic: **só meses fechados** | O mês da carga ainda está em andamento e a série é acumulada no mês (ex.: 11/2026 = 0,66 contra 1,07 em 10/2026) |
| O corte do mês incompleto usa o `carregado_em`, e não a data do computador | Rodar de novo outro dia dá o mesmo resultado |
| Selic em **% ao mês e % ao ano** | A série vem ao mês, mas a Selic é lida ao ano. Anualizada por juros compostos: `((1 + mes/100)^12 − 1) × 100` |
| O `total` nunca é somado com as 4 categorias | Contaria tudo em dobro. Conferido: 7384 + 7385 + 7386 + 7387 = 7389 nos 441 meses |
| Acumulado de 12 meses é NULL antes do 12º mês | Uma soma parcial pareceria uma queda falsa |
| Sazonalidade só com **anos completos** | 1990 começa em fevereiro e 2026 está incompleto |
| Juros × emplacamentos **a partir de 2000-01** | Antes do câmbio flutuante e do regime de metas (1999), a Selic passa de 80% ao mês e distorce a relação |
| Correlação sobre os **níveis** | Escolha do autor. **Limitação:** correlação não é causalidade, e as duas séries têm tendência e sazonalidade |
| Dashboard monta o pipeline se o banco não existir | Na nuvem não há banco local: data/ não vai para o git |
| Contador de acessos no Supabase | O disco do Streamlit Cloud é apagado a cada reinício; RLS ligado e a função só soma 1 |

### Principais resultados (dados até out/2026)
- **Mercado aquecido:** 3.039.871 veículos em 12 meses, **+13,34%** sobre os 12 meses anteriores.
- **Caminhões na contramão:** acumulado de 12 meses **−6,01%**, e a participação no mix caiu de 4,63% (2024) para 4,13% (2025).
- **Sazonalidade forte:** dezembro fica **13% acima** da média do ano, e fevereiro, **18% abaixo**.
- **Juros:** correlação negativa e moderada (cerca de −0,5), mais forte com **1 mês de defasagem**. Ela quase
  não muda entre 0 e 12 meses, sinal de que boa parte da relação vem da **tendência de longo prazo** das
  duas séries, e não de uma reação mês a mês.

---

## Como rodar do zero

Testado no Windows com **Python 3.15** (SQLite 3.53) e no Linux com Python 3.13.
A função `pow()` do SQLite é usada na silver e exige um SQLite com funções matemáticas (versão 3.35 ou
mais nova, padrão nas instalações recentes do Python).

```bash
# 1. Clonar
git clone https://github.com/EmanuelSeven/emplacamentos-brasil.git
cd emplacamentos-brasil

# 2. Ambiente virtual
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/Mac

# 3. Dependências
pip install -r requirements.txt

# 4. Testes (não precisam de internet nem do banco)
python -m pytest -v

# 5. Painel no terminal (na primeira vez, baixa os dados e monta bronze → silver → gold)
python src/main.py

# 6. Dashboard (opcional, depois do passo 5)
streamlit run src/dashboard.py
```

Para atualizar os dados depois, use a opção **1** do painel ou rode
`python src/ingestao.py` e `python src/transformacao.py`.

### Contador de acessos do dashboard (opcional)
O dashboard conta uma abertura por sessão. **Sem configurar nada, ele conta localmente**, no arquivo
`data/visualizacoes.json`. Na nuvem (Streamlit Community Cloud) o disco é apagado a cada reinício, então o
total fica numa tabela do **Supabase**. Para ligar:

1. No Supabase, abra o **SQL Editor** e rode o SQL abaixo (uma vez).
2. Copie `.streamlit/secrets.toml.exemplo` para `.streamlit/secrets.toml` e preencha com a URL do projeto
   e a **publishable key** (`sb_publishable_...`). Esse arquivo está no `.gitignore` e **nunca** vai para
   o git. No Streamlit Community Cloud, cole o mesmo conteúdo em *Settings → Secrets*.

```sql
-- Uma única linha com o total de acessos.
create table if not exists public.page_views_emplacamentos (
    id    smallint primary key default 1 check (id = 1),
    total bigint   not null default 0 check (total >= 0)
);
insert into public.page_views_emplacamentos (id, total) values (1, 0)
on conflict (id) do nothing;

-- RLS ligado e nenhuma policy: ninguém lê nem altera a tabela direto pela API.
alter table public.page_views_emplacamentos enable row level security;
revoke all on table public.page_views_emplacamentos from anon, authenticated;

-- A única porta de entrada: uma função que só soma 1 e devolve o novo total.
-- security definer: roda com o dono da função (por isso passa pelo RLS);
-- search_path vazio + nomes completos (public.) evitam que outro schema a desvie.
create or replace function public.increment_page_views_emplacamentos()
returns bigint
language sql
security definer
set search_path = ''
as $$
    update public.page_views_emplacamentos
       set total = total + 1
     where id = 1
    returning total;
$$;

-- Só o papel anon (o da publishable key) pode executar a função.
revoke all on function public.increment_page_views_emplacamentos() from public, anon, authenticated;
grant execute on function public.increment_page_views_emplacamentos() to anon;
```

### Como sabemos que os testes testam algo
São 11 testes com **dados inventados** num banco em memória, executando os `.sql` reais do projeto, e um
bloqueio garante que nenhum teste acessa a internet. Para provar que eles pegam erros, o código foi
**sabotado de propósito** duas vezes:

| Sabotagem | Teste que falhou |
|---|---|
| Deixar o mês incompleto da Selic entrar (`<` virou `<=`) | `test_selic_exclui_mes_da_carga_e_mantem_anteriores` |
| Deixar o `total` entrar no mix (contagem em dobro) | `test_mix_soma_100_e_total_nao_entra_como_categoria` |

Nos dois casos, falhou **exatamente o teste certo**, e a sabotagem foi desfeita com `git checkout`.

---

## Contexto de mercado: ranking por modelo

> ⚠️ **Não é um indicador deste pipeline.** A API do Banco Central só traz totais por categoria. O ranking
> por modelo vem dos informativos da Fenabrave, republicados pela imprensa, e está aqui apenas como contexto.
> Consultado em 22/11/2026.

**🚗 Automóveis, outubro/2026**

| # | Modelo | Emplacamentos |
|---|---|---|
| 1 | Hyundai HB20 | 9.037 |
| 2 | BYD Dolphin Mini | 8.432 |
| 3 | Fiat Argo | 8.348 |
| 4 | VW Polo | 8.125 |
| 5 | VW T-Cross | 7.567 |

**🛻 Comerciais leves, outubro/2026**

| # | Modelo | Emplacamentos |
|---|---|---|
| 1 | Fiat Strada | 14.566 |
| 2 | Fiat Toro | 5.198 |
| 3 | VW Saveiro | 4.839 |
| 4 | Toyota Hilux | 3.569 |
| 5 | Ford Ranger | 2.818 |

Fonte das duas tabelas: [Car.blog.br, fechamento de outubro/2026](https://www.car.blog.br/2026/11/carros-mais-vendidos-outubro-2026-fechamento.html) (dados da Fenabrave).

**🚌 Ônibus, outubro/2026 (por marca do chassi)**

| # | Marca | Emplacamentos |
|---|---|---|
| 1 | Mercedes-Benz | 1.108 |
| 2 | Volkswagen Caminhões e Ônibus | 357 |
| 3 | Iveco | 242 |
| 4 | Marcopolo | 221 |
| 5 | Agrale | 48 |

Fonte: [Diário do Transporte](https://diariodotransporte.com.br/2026/11/05/emplacamentos-de-onibus-caem-2538-em-outubro-e-mercado-acumula-retracao-de-299-em-2026-aponta-fenabrave/) (dados da Fenabrave).

**🚛 Caminhões, líderes por segmento (acumulado janeiro a outubro/2026)**

Não foi encontrado um ranking por modelo só de outubro. Os líderes no acumulado do ano:

| Segmento | Modelo | Emplacamentos (jan-out/2026) |
|---|---|---|
| Geral (médios) | VW Delivery 11.180 | 5.349 |
| Pesados | Volvo FH 540 | 4.716 |
| Semipesados | Volvo VM 290 | 2.986 |

Fonte: [Maqvel, ranking Fenabrave 2026](https://maqvel.com.br/blog/caminhao-mais-vendido-2026).

---

## Onde a IA errou ou assumiu algo

O projeto foi construído com IA em todas as etapas: **Claude (chat)** no planejamento, nas decisões e na
revisão, **GitHub Copilot** na Etapa 1 e **Claude Code** (no VS Code) da Etapa 2 em diante. Tudo foi
conferido, quase sempre **contando linhas antes e depois** ou comparando com um cálculo independente.

| Etapa | O que aconteceu | Como foi descoberto |
|---|---|---|
| 1 (Copilot) | O prompt chegou com `pycache/` (os sublinhados se perderam na cópia), e o Copilot **corrigiu por conta própria** para `__pycache__/`, sem avisar | Conferindo o `.gitignore` linha a linha |
| Planejamento (Claude) | As regras diziam que as séries começam em **01/1990**, com base nos metadados do portal. O dado real começa em **02/1990** | O Claude Code olhou o dado carregado e apontou a diferença |
| 2 (Claude Code) | O comentário dizia que, se algo falhasse, "a bronze anterior continua intacta". Isso vale para falhas no download, mas não na gravação, que acontece depois do `DROP` | Revisão do código |
| 2 (Claude Code) | Criou um `.venv` e instalou as dependências **sem ter sido pedido** (decisão correta, aqui documentada) | Lista "o que você assumiu", pedida em todo prompt |
| 4 (processo) | O arquivo de regras (`CLAUDE.md`) foi **sobrescrito** por uma versão antiga aberta no editor. A IA **não inventou** as definições que faltavam: perguntou | Conferindo o conteúdo do arquivo em disco |
| 6b (Claude Code) | O código "aplicava" o formato brasileiro nos gráficos, mas os eixos continuaram em `3,000,000` | Olhando a tela, e não só o código |
| 6b (Claude Code) | A pilha do Mix ficou em ordem alfabética, diferente da legenda | Comparando o gráfico com a legenda |
| 6b (Claude Code) | Exibiu "1 acessos", porque seguiu o formato pedido **ao pé da letra** | Leitura da resposta |
| 6b (Claude chat → Claude Code) | O planejamento afirmou que "colunas calculadas de VIEW não têm tipo". Errado em parte: colunas vindas de um `CAST` (como `ano` e `mes_do_ano`) herdam o tipo | O Claude Code conferiu o resultado do `PRAGMA table_info` e corrigiu a legenda |
| Conferência (Claude) | Na revisão do painel, o gabarito foi digitado como "dezembro 113,33", quando o cálculo dava 113,3 (o painel mostrava o certo: 113,26) | Comparando o gabarito com a saída |

Os indicadores da gold foram **calculados duas vezes de forma independente** (VIEWs em SQL e um script
separado em Python) e bateram até a 4ª casa decimal.

---

## Próximos passos
- **Ranking por modelo:** pipeline próprio sobre os dados da Fenabrave (exige resolver a licença e extrair dados de PDF).
- **Câmbio e matéria-prima importada:** cruzar emplacamentos com o dólar (PTAX) e com as importações de PVB (Comex Stat).
- **Frota por região:** RENAVAM (domínio público) cruzado com a população do IBGE.

---

## Estrutura do projeto

```
emplacamentos-brasil/
├── sql/
│   ├── bronze/01_criar_bronze.sql
│   ├── silver/01_silver_emplacamentos.sql, 02_silver_selic.sql
│   └── gold/01_vw_tendencia.sql ... 04_vw_juros_emplacamentos.sql
├── src/
│   ├── database.py       conexão com o SQLite
│   ├── ingestao.py       API → bronze
│   ├── transformacao.py  executa os .sql da silver e da gold
│   ├── queries.py        consultas do painel e do dashboard (só leem a gold)
│   ├── main.py           painel no terminal
│   └── dashboard.py      dashboard Streamlit
├── tests/                testes com pytest (dados inventados, sem internet)
├── CLAUDE.md             regras e decisões usadas pela IA
├── requirements.txt
└── pytest.ini
```
