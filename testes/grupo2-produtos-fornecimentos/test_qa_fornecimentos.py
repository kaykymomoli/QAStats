"""Suíte independente do QA (Grupo 8) — fornecimentos-service (ESP-FRN-001 v2.1)."""
import json

import pytest
from tests.conftest import FORNECIMENTO_VALIDO, Ambiente, auth, entregar, produto, token

URL = "/api/v1/fornecimentos"
CAMPOS_PROBLEMA = {"type", "title", "status", "detail", "instance", "codigo", "correlationId", "timestamp"}
SORRISO = {"produto_id": "PROD-1", "preco": 142.35, "quantidade_disponivel": 1200.50, "origem": {"cidade": "Sorriso", "uf": "MT"}}


@pytest.fixture
def amb():
    a = Ambiente()
    entregar(a, "produto_cadastrado", produto())
    return a


def problema(r, status, codigo):
    assert r.status_code == status, r.text
    assert r.headers["content-type"].startswith("application/problem+json")
    corpo = r.json()
    assert CAMPOS_PROBLEMA <= corpo.keys() and corpo["codigo"] == codigo
    return corpo


def test_ux_exemplo_sorriso_mt(amb):
    r = amb.cliente.post(URL, json=SORRISO, headers=auth())
    assert r.status_code == 201, r.text
    c = r.json()
    assert c["origem"] == {"cidade": "Sorriso", "uf": "MT"} and c["preco"] == 142.35 and c["quantidade_disponivel"] == 1200.5
    assert c["unidade"] == "L"  # herdada do produto


def test_ux_categoria_no_fornecimento_e_ignorada(amb):
    r = amb.cliente.post(URL, json={**SORRISO, "categoria": "GRAOS"}, headers=auth())
    assert r.status_code == 201 and "categoria" not in r.json()


def test_ux_status_ativo_nao_existe(amb):
    r = amb.cliente.post(URL, json={**SORRISO, "status": "PAUSADO"}, headers=auth())
    assert r.status_code == 201 and "status" not in r.json()


def test_ux_produto_digitado_inexistente(amb):
    problema(amb.cliente.post(URL, json={**SORRISO, "produto_id": "Soja"}, headers=auth()), 422, "PRODUTO_INEXISTENTE")


@pytest.mark.parametrize("preco,esperado", [(0.01, 201), (10.1, 201), (10.10, 201), (5.555, 422), ("142,35", 422), ("R$ 10", 422)])
def test_ux_preco_duas_casas(amb, preco, esperado):
    assert amb.cliente.post(URL, json={**SORRISO, "preco": preco}, headers=auth()).status_code == esperado


@pytest.mark.parametrize("qtd,esperado", [(0.01, 201), (1.239, 422), (True, 422), (None, 422)])
def test_ux_quantidade_duas_casas(amb, qtd, esperado):
    assert amb.cliente.post(URL, json={**SORRISO, "quantidade_disponivel": qtd}, headers=auth()).status_code == esperado


@pytest.mark.parametrize("origem", ["Sorriso-MT", {"cidade": "Sorriso", "uf": "Mato Grosso"}, {"cidade": "Sorriso", "uf": "mt"},
                                    {"cidade": "Sorriso"}, {"uf": "MT"}, {"cidade": "", "uf": "MT"}, None, ["Sorriso", "MT"]])
def test_ux_origem_invalida(amb, origem):
    problema(amb.cliente.post(URL, json={**SORRISO, "origem": origem}, headers=auth()), 422, "DADOS_INVALIDOS")


def test_origem_extra_nao_gravado(amb):
    r = amb.cliente.post(URL, json={**SORRISO, "origem": {"cidade": "Sorriso", "uf": "MT", "cep": "78890-000"}}, headers=auth())
    assert r.status_code == 201 and r.json()["origem"] == {"cidade": "Sorriso", "uf": "MT"}


@pytest.mark.parametrize("bruto", ["NaN", "Infinity"])
def test_preco_nao_finito(amb, bruto):
    corpo = json.dumps(SORRISO).replace("142.35", bruto)
    r = amb.cliente.post(URL, content=corpo, headers={**auth(), "Content-Type": "application/json"})
    problema(r, 422, "DADOS_INVALIDOS")


def test_precisao_decimal_float(amb):
    """0.1 + 0.2 em float = 0.30000000000000004; o serviço deve usar Decimal."""
    r = amb.cliente.post(URL, json={**SORRISO, "quantidade_disponivel": 0.1}, headers=auth())
    fid = r.json()["fornecimento_id"]
    r = amb.cliente.patch(f"{URL}/{fid}", json={"repor": 0.2}, headers=auth())
    assert r.status_code == 200 and r.json()["quantidade_disponivel"] == 0.3


def test_buyer_nao_cadastra(amb):
    problema(amb.cliente.post(URL, json=SORRISO, headers=auth("BUYER")), 403, "PERFIL_NAO_PERMITIDO")


def test_carrier_nao_consulta(amb):
    problema(amb.cliente.get(URL, headers=auth("CARRIER")), 403, "PERFIL_NAO_PERMITIDO")


def test_ux_403_contexto_nao_selecionado(amb):
    h = {"Authorization": "Bearer " + token(tenant_id=None, active_scope=None)}
    problema(amb.cliente.post(URL, json=SORRISO, headers=h), 403, "CONTEXTO_NAO_SELECIONADO")


def test_encerrar_existe_via_patch(amb):
    """Mensagem ao UX: 'pausar ou encerrar depende do professor'. A ESP v2.1 já tem PATCH {encerrar: true}."""
    fid = amb.cliente.post(URL, json=SORRISO, headers=auth()).json()["fornecimento_id"]
    r = amb.cliente.patch(f"{URL}/{fid}", json={"encerrar": True}, headers=auth())
    assert r.status_code == 200 and r.json()["quantidade_disponivel"] == 0
    lista = amb.cliente.get(URL, headers=auth("BUYER", tenant="EMP-12")).json()
    assert lista["total"] == 0  # some da vitrine do comprador


def test_outra_empresa_nao_altera(amb):
    fid = amb.cliente.post(URL, json=SORRISO, headers=auth()).json()["fornecimento_id"]
    problema(amb.cliente.patch(f"{URL}/{fid}", json={"preco": 1}, headers=auth(tenant="EMP-99")), 403, "FORNECIMENTO_DE_OUTRA_EMPRESA")


def test_produto_excluido_bloqueia_fornecimento(amb):
    from tests.conftest import evento
    entregar(amb, "produto_excluido", evento("produto_excluido", {"produtoId": "PROD-1"}, timestamp="2026-10-26T13:59:30Z"))
    problema(amb.cliente.post(URL, json=SORRISO, headers=auth()), 422, "PRODUTO_INEXISTENTE")
