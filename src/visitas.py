"""Contador de acessos do dashboard no Supabase.

Na nuvem (Streamlit Community Cloud) o disco é apagado a cada reinício, então o
total fica numa tabela do Supabase. O dashboard chama uma função (RPC) que soma 1
e devolve o novo total. O SQL da tabela e da função está no README.

A chave é uma publishable key (sb_publishable_...), que não é um JWT: vai SÓ no
header apikey, nunca em "Authorization: Bearer".
"""

import requests

FUNCAO_RPC = "increment_page_views_emplacamentos"


def registrar_visita(url, chave):
    """Soma 1 no contador do Supabase e devolve o total (int).

    Qualquer problema (rede, timeout, erro HTTP, resposta que não seja um
    inteiro) devolve None, sem levantar exceção: o contador nunca pode
    derrubar o dashboard.
    """
    try:
        resposta = requests.post(
            url.rstrip("/") + f"/rest/v1/rpc/{FUNCAO_RPC}",
            headers={"apikey": chave},
            json={},
            timeout=3,
        )
        resposta.raise_for_status()
        total = resposta.json()
    except Exception:
        return None
    # bool é subclasse de int em Python: True não é um total válido.
    if isinstance(total, int) and not isinstance(total, bool):
        return total
    return None
