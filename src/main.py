"""Painel de mercado no terminal: emplacamentos de veículos novos no Brasil.

Como rodar (a partir da raiz do projeto):
    python src/main.py

Na primeira execução, se o banco ou as VIEWs da gold não existirem, o
pipeline completo (API -> bronze -> silver -> gold) roda sozinho.
O painel só lê as VIEWs da gold (via queries.py); nada é calculado aqui,
os números são apenas formatados para exibição.
"""

import ingestao
import queries
import transformacao
from database import conectar

VIEWS_GOLD = ["vw_tendencia", "vw_mix", "vw_sazonalidade", "vw_juros_emplacamentos"]

# Colunas inteiras que são rótulos (ano, mês, defasagem), não quantidades:
# não recebem ponto de milhar (senão 2024 viraria "2.024").
COLUNAS_SEM_MILHAR = {"ano", "mes_do_ano", "defasagem_meses"}

MENU = """
        EMPLACAMENTOS BRASIL - PAINEL DE MERCADO
   1 - Atualizar dados (API -> bronze -> silver -> gold)
   2 - Últimos 12 meses: emplacamentos por categoria
   3 - Filtrar uma categoria (últimos 24 meses)
   4 - Tendência: acumulado de 12 meses do total (últimos 12 meses)
   5 - Mix anual por categoria
   6 - Sazonalidade do total (meses acima/abaixo da média)
   7 - Juros x emplacamentos (correlação por defasagem)
   0 - Sair"""


def formatar(valor, coluna):
    """Formata um valor só para exibição, sem alterar o número."""
    if valor is None:
        return "-"
    if isinstance(valor, bool):
        return str(valor)
    if isinstance(valor, int):
        if coluna in COLUNAS_SEM_MILHAR:
            return str(valor)
        return f"{valor:,}".replace(",", ".")  # 3039871 -> 3.039.871
    if isinstance(valor, float):
        return f"{valor:.2f}".replace(".", ",")  # 13.3388 -> 13,34
    return str(valor)


def imprimir_tabela(linhas):
    """Imprime as linhas com as colunas separadas por ' | '."""
    if not linhas:
        print("\n(nenhuma linha)")
        return

    colunas = list(linhas[0].keys())
    celulas = [[formatar(linha[c], c) for c in colunas] for linha in linhas]
    larguras = [
        max(len(colunas[i]), *(len(celula[i]) for celula in celulas))
        for i in range(len(colunas))
    ]

    def montar(valores):
        # Texto à esquerda; números à direita (mais fácil comparar).
        partes = []
        for i, valor in enumerate(valores):
            if isinstance(linhas[0][colunas[i]], str):
                partes.append(valor.ljust(larguras[i]))
            else:
                partes.append(valor.rjust(larguras[i]))
        return " | ".join(partes)

    print()
    print(" | ".join(c.ljust(larguras[i]) for i, c in enumerate(colunas)))
    print("-+-".join("-" * largura for largura in larguras))
    for celula in celulas:
        print(montar(celula))
    print(f"({len(linhas)} linhas)")


def views_faltando(conexao):
    """Quais VIEWs da gold ainda não existem no banco."""
    existentes = {
        linha["name"]
        for linha in conexao.execute("SELECT name FROM sqlite_master WHERE type = 'view'")
    }
    return [view for view in VIEWS_GOLD if view not in existentes]


def atualizar_dados():
    """Roda o pipeline completo reaproveitando os main() dos outros scripts.

    Devolve True se tudo deu certo. Os scripts param com sys.exit() em caso de
    erro; aqui isso é capturado para o painel não fechar sozinho.
    """
    try:
        ingestao.main()
        transformacao.main()
    except SystemExit as erro:
        if erro.code not in (None, 0):
            print("\nA atualização falhou (veja a mensagem acima).")
            return False
    return True


def opcao_filtrar_categoria(conexao):
    validas = queries.categorias_validas(conexao)
    print("\nCategorias válidas: " + ", ".join(validas))
    categoria = input("Digite a categoria: ").strip().lower()
    if categoria not in validas:
        print(f"Categoria '{categoria}' não existe. Voltando ao menu.")
        return
    imprimir_tabela(queries.filtrar_categoria(conexao, categoria))


def main():
    conexao = conectar()
    try:
        faltando = views_faltando(conexao)
        if faltando:
            print("Banco de dados ou indicadores ainda não criados "
                  f"(faltam: {', '.join(faltando)}).")
            print("Rodando o pipeline pela primeira vez (API -> bronze -> silver -> gold)...\n")
            if not atualizar_dados():
                print("Não foi possível montar o banco. Corrija o erro e rode de novo.")
                return

        while True:
            print(MENU)
            opcao = input("Escolha uma opção: ").strip()

            if opcao == "1":
                if atualizar_dados():
                    print("\nDados atualizados.")
            elif opcao == "2":
                imprimir_tabela(queries.ultimos_12_meses_por_categoria(conexao))
            elif opcao == "3":
                opcao_filtrar_categoria(conexao)
            elif opcao == "4":
                imprimir_tabela(queries.tendencia_total(conexao))
            elif opcao == "5":
                imprimir_tabela(queries.mix_anual(conexao))
            elif opcao == "6":
                print("\nÍndice 100 = mês na média do próprio ano; "
                      "acima de 100 = acima da média; abaixo de 100 = abaixo.")
                imprimir_tabela(queries.sazonalidade_total(conexao))
            elif opcao == "7":
                print("\nSelic do mês X (% ao ano) contra emplacamentos (total) do mês X + defasagem, "
                      "desde 2000-01. Correlação não é causalidade.")
                imprimir_tabela(queries.juros_emplacamentos(conexao))
            elif opcao == "0":
                print("Até logo!")
                break
            else:
                print("Opção inválida. Digite um número de 0 a 7.")
    except (KeyboardInterrupt, EOFError):
        # Ctrl+C, ou fim da entrada quando as opções vêm de um arquivo/pipe.
        print("\nPainel encerrado.")
    finally:
        conexao.close()


if __name__ == "__main__":
    main()
