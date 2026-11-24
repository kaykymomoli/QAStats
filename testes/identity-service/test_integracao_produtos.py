"""Integração ponta a ponta: tokens REAIS do Identity-Service validados pelo produtos-service e
fornecimentos-service usando o adaptador JWKS de produção (adaptadores/chaves_jwks.py) apontado ao JWKS público.

Executar com PYTHONPATH=<Sistema-MicServ-SD>/servicos/<svc>-service e SERVICO=produtos|fornecimentos.
"""
import os
from datetime import datetime, timezone

import pytest
from conftest import BASE, FILIAL, MATRIZ, contexto, login
from fastapi.testclient import TestClient

SERVICO = os.environ.get("SERVICO", "produtos")


class RelogioReal:
    def now(self):
        return datetime.now(timezone.utc)


@pytest.fixture(scope="module")
def cli():
    from adaptadores.chaves_jwks import ChavesJwks
    from app.main import create_app
    import tests.conftest as dev
    repo = dev.FakeRepoProdutos() if SERVICO == "produtos" else dev.FakeRepoFornecimentos()
    bus = dev.FakeBus()
    chaves = ChavesJwks(f"{BASE}/.well-known/jwks.json")
    if os.environ.get("CONTORNAR_UA"):  # contorno do bloqueio do Cloudflare ao UA Python-urllib (DEF-ID-01)
        chaves._cliente = __import__("jwt").PyJWKClient(f"{BASE}/.well-known/jwks.json", lifespan=3600, headers={"User-Agent": "qa-grupo8"})
    app = create_app(bus, RelogioReal(), repo, chaves)
    c = TestClient(app)
    c.bus = bus
    if SERVICO == "fornecimentos":
        dev.entregar(type("A", (), {"bus": bus})(), "produto_cadastrado", dev.produto(timestamp="2026-01-01T00:00:00Z"))
    return c


URL = "/api/v1/produtos" if SERVICO == "produtos" else "/api/v1/fornecimentos"
CORPO = ({"nome": "Soja em grãos", "categoria": "GRAOS", "unidade": "TON", "tipo_transporte": "GRANEL"} if SERVICO == "produtos"
         else {"produto_id": "PROD-1", "preco": 142.35, "quantidade_disponivel": 1200.5, "origem": {"cidade": "Sorriso", "uf": "MT"}})


def bearer(r):
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def test_token_real_supplier_cadastra(http, cli):
    r = cli.post(URL, json=CORPO, headers=bearer(contexto(http, "fornecedor", MATRIZ, "SUPPLIER")))
    assert r.status_code == 201, r.text
    dono = r.json().get("cadastrado_por_empresa_id") or r.json().get("fornecedor_id")
    assert dono == MATRIZ


def test_token_temporario_do_login_403_contexto(http, cli):
    r = cli.post(URL, json=CORPO, headers=bearer(login(http, "fornecedor")))
    assert r.status_code == 403 and r.json()["codigo"] == "CONTEXTO_NAO_SELECIONADO", r.text


def test_token_macro_group_le_mas_nao_escreve(http, cli):
    h = bearer(contexto(http, "comprador", None, "BUYER", view_mode="MACRO_GROUP"))
    assert cli.get(URL, headers=h).status_code == 200
    r = cli.post(URL, json=CORPO, headers=h)
    assert r.status_code == 403 and r.json()["codigo"] in ("CONTEXTO_DE_GRUPO_NAO_PERMITIDO", "PERFIL_NAO_PERMITIDO"), r.text


def test_token_real_carrier(http, cli):
    h = bearer(login(http, "transportador", auto_context=True))
    r = cli.post(URL, json=CORPO, headers=h)
    assert r.status_code == 403 and r.json()["codigo"] == "PERFIL_NAO_PERMITIDO"


def test_token_real_buyer_filial(http, cli):
    h = bearer(contexto(http, "comprador", FILIAL, "BUYER"))
    r = cli.post(URL, json=CORPO, headers=h)
    esperado = 201 if SERVICO == "produtos" else 403  # BUYER cadastra produto mas não fornecimento
    assert r.status_code == esperado, r.text


def test_token_pos_logout_continua_aceito_ate_exp(http, cli):
    """Q-16 da ESP: validação offline não vê a denylist. Documenta a janela de até 15 min."""
    r = contexto(http, "fornecedor", MATRIZ, "SUPPLIER")
    h = bearer(r)
    assert http.post(f"{BASE}/api/v1/auth/logout", headers=h, timeout=10).status_code == 204
    assert cli.get(URL, headers=h).status_code == 200
