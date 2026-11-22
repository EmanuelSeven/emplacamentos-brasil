"""Testes do contador de acessos no Supabase (src/visitas.py), SEM rede.

requests.post é trocado por uma função falsa com monkeypatch; a URL e a chave
são inventadas.
"""

import requests

import visitas

URL = "https://projeto-inventado.supabase.co/"  # com "/" no fim, de propósito
CHAVE = "sb_publishable_chave_inventada"


class RespostaFalsa:
    """Imita a resposta do requests: status HTTP e corpo JSON."""

    def __init__(self, status, corpo):
        self.status_code = status
        self._corpo = corpo

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._corpo


def test_resposta_200_com_inteiro_devolve_o_total(monkeypatch):
    # A função do Supabase devolve o novo total como um número JSON: 5.
    # Esperado: 5. Também confere a chamada: URL sem "//", chave SÓ no header
    # apikey (publishable key não é JWT: nada de Authorization: Bearer).
    chamadas = []

    def post_falso(url, headers, json, timeout):
        chamadas.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return RespostaFalsa(200, 5)

    monkeypatch.setattr(requests, "post", post_falso)
    assert visitas.registrar_visita(URL, CHAVE) == 5

    assert chamadas == [{
        "url": "https://projeto-inventado.supabase.co/rest/v1/rpc/increment_page_views_emplacamentos",
        "headers": {"apikey": CHAVE},
        "json": {},
        "timeout": 3,
    }]


def test_erro_http_devolve_none(monkeypatch):
    # Ex.: chave errada (401) ou função inexistente (404). Esperado: None, sem exceção.
    monkeypatch.setattr(requests, "post", lambda *a, **k: RespostaFalsa(401, {"message": "Invalid API key"}))
    assert visitas.registrar_visita(URL, CHAVE) is None


def test_timeout_devolve_none(monkeypatch):
    # O Supabase não respondeu em 3 segundos. Esperado: None, sem exceção.
    def post_lento(*args, **kwargs):
        raise requests.exceptions.Timeout("demorou demais")

    monkeypatch.setattr(requests, "post", post_lento)
    assert visitas.registrar_visita(URL, CHAVE) is None


def test_resposta_que_nao_e_inteiro_devolve_none(monkeypatch):
    # Status 200, mas o corpo não é um total inteiro: texto, decimal, lista ou True.
    # Esperado: None em todos (True é bool, que em Python é subclasse de int).
    for corpo in ["5", 5.5, [5], None, True]:
        monkeypatch.setattr(requests, "post", lambda *a, c=corpo, **k: RespostaFalsa(200, c))
        assert visitas.registrar_visita(URL, CHAVE) is None, corpo
