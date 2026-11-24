"""Suíte independente do QA (Grupo 8) — produtos-service.

Verifica o que foi comunicado ao UX + casos de borda da ESP-PRD-001 v2.1.
Executar com o PYTHONPATH apontando para servicos/produtos-service (ver run_grupo2.sh).
Reaproveita apenas os dublês de porta (FakeBus/FakeRepo/token) do conftest dos devs.
"""
import json

import pytest
from tests.conftest import PRODUTO_VALIDO, Ambiente, auth, token

URL = "/api/v1/produtos"
CAMPOS_PROBLEMA = {"type", "title", "status", "detail", "instance", "codigo", "correlationId", "timestamp"}


@pytest.fixture
def amb():
    return Ambiente()


def problema(r, status, codigo):
    assert r.status_code == status, r.text
    assert r.headers["content-type"].startswith("application/problem+json")
    corpo = r.json()
    assert CAMPOS_PROBLEMA <= corpo.keys()
    assert corpo["codigo"] == codigo and corpo["status"] == status
    assert corpo["title"] and corpo["detail"]
    return corpo


# ---- Mensagem ao UX: campos do produto -------------------------------------------------

@pytest.mark.parametrize("unidade", ["KG", "TON", "UN", "CX", "L"])
def test_ux_unidades_aceitas(amb, unidade):
    r = amb.cliente.post(URL, json={**PRODUTO_VALIDO, "unidade": unidade}, headers=auth())
    assert r.status_code == 201 and r.json()["unidade"] == unidade


@pytest.mark.parametrize("tipo", ["GRANEL", "REFRIGERADO", "CARGA_SECA", "PERIGOSO"])
def test_ux_tipos_transporte_aceitos(amb, tipo):
    r = amb.cliente.post(URL, json={**PRODUTO_VALIDO, "tipo_transporte": tipo}, headers=auth())
    assert r.status_code == 201


@pytest.mark.parametrize("tipo", ["RODOVIARIO", "Rodoviário", "rodoviario", "refrigerado", "CARGA SECA"])
def test_ux_rodoviario_e_variacoes_recusados(amb, tipo):
    r = amb.cliente.post(URL, json={**PRODUTO_VALIDO, "tipo_transporte": tipo}, headers=auth())
    problema(r, 422, "DADOS_INVALIDOS")
    assert amb.bus.publicadas == []


@pytest.mark.parametrize("unidade", ["kg", "Kg", "LITRO", "M3", "", None])
def test_ux_unidade_fora_da_lista(amb, unidade):
    r = amb.cliente.post(URL, json={**PRODUTO_VALIDO, "unidade": unidade}, headers=auth())
    problema(r, 422, "DADOS_INVALIDOS")


def test_ux_peso_unitario_opcional(amb):
    r = amb.cliente.post(URL, json=PRODUTO_VALIDO, headers=auth())
    assert r.status_code == 201 and r.json()["peso_unitario_kg"] is None


@pytest.mark.parametrize("categoria", ["Frutas", "Ração animal", "laticinios", "Laticínios"])
def test_ux_categoria_texto_livre_e_recusada(amb, categoria):
    """A mensagem ao UX diz 'categoria (texto)'; a ESP (RN-09) define LISTA FIXA.
    Este teste documenta a divergência: texto livre é recusado."""
    r = amb.cliente.post(URL, json={**PRODUTO_VALIDO, "categoria": categoria}, headers=auth())
    problema(r, 422, "DADOS_INVALIDOS")


@pytest.mark.parametrize("cat", ["GRAOS", "INSUMOS", "SUBPRODUTOS", "LATICINIOS", "CARNES", "HORTIFRUTI", "BEBIDAS", "OUTROS"])
def test_categorias_da_lista_fixa(amb, cat):
    assert amb.cliente.post(URL, json={**PRODUTO_VALIDO, "categoria": cat}, headers=auth()).status_code == 201


# ---- Valores-limite adicionais ---------------------------------------------------------

@pytest.mark.parametrize("tam,esperado", [(2, 201), (255, 201), (256, 422)])
def test_nome_limites(amb, tam, esperado):
    r = amb.cliente.post(URL, json={**PRODUTO_VALIDO, "nome": "a" * tam}, headers=auth())
    assert r.status_code == esperado


@pytest.mark.parametrize("bruto", ['NaN', 'Infinity', '-Infinity'])
def test_peso_nao_finito_recusado(amb, bruto):
    corpo = json.dumps(PRODUTO_VALIDO)[:-1] + f', "peso_unitario_kg": {bruto}}}'
    r = amb.cliente.post(URL, content=corpo, headers={**auth(), "Content-Type": "application/json"})
    problema(r, 422, "DADOS_INVALIDOS")


def test_peso_notacao_cientifica_valida(amb):
    corpo = json.dumps(PRODUTO_VALIDO)[:-1] + ', "peso_unitario_kg": 1.5e1}'
    r = amb.cliente.post(URL, content=corpo, headers={**auth(), "Content-Type": "application/json"})
    assert r.status_code == 201 and r.json()["peso_unitario_kg"] == 15


def test_corpo_vazio(amb):
    r = amb.cliente.post(URL, content=b"", headers={**auth(), "Content-Type": "application/json"})
    problema(r, 422, "DADOS_INVALIDOS")


def test_corpo_nao_utf8(amb):
    r = amb.cliente.post(URL, content=b'{"nome": "\xff\xfe"}', headers={**auth(), "Content-Type": "application/json"})
    problema(r, 422, "DADOS_INVALIDOS")


def test_nome_com_unicode_e_emoji(amb):
    r = amb.cliente.post(URL, json={**PRODUTO_VALIDO, "nome": "Café ☕ Arábica"}, headers=auth())
    assert r.status_code == 201 and r.json()["nome"] == "Café ☕ Arábica"


# ---- Erros conforme comunicado ao UX ---------------------------------------------------

def test_ux_401_sem_token(amb):
    problema(amb.cliente.post(URL, json=PRODUTO_VALIDO), 401, "TOKEN_AUSENTE")


def test_ux_401_token_expirado(amb):
    from tests.conftest import T0
    problema(amb.cliente.get(URL, headers=auth(exp=T0)), 401, "TOKEN_EXPIRADO")


def test_ux_401_token_lixo(amb):
    problema(amb.cliente.get(URL, headers={"Authorization": "Bearer abc.def.ghi"}), 401, "TOKEN_INVALIDO")


def test_ux_403_contexto_nao_selecionado(amb):
    h = {"Authorization": "Bearer " + token(tenant_id=None, active_scope=None)}
    problema(amb.cliente.post(URL, json=PRODUTO_VALIDO, headers=h), 403, "CONTEXTO_NAO_SELECIONADO")


def test_ux_503_chaves_indisponiveis(amb):
    def falha(kid):
        raise ConnectionError("jwks fora")
    amb.chaves.obter = falha
    problema(amb.cliente.get(URL, headers=auth()), 503, "DEPENDENCIA_INDISPONIVEL")


def test_ux_correlation_id_ecoado(amb):
    r = amb.cliente.get(URL + "/NAO-EXISTE", headers={**auth("BUYER"), "X-Correlation-Id": "qa-corr-123"})
    corpo = problema(r, 404, "PRODUTO_NAO_ENCONTRADO")
    assert r.headers["x-correlation-id"] == "qa-corr-123" and corpo["correlationId"] == "qa-corr-123"


def test_erro_500_nao_vaza_excecao(amb):
    amb.repo.falhar_insercao = True
    corpo = problema(amb.cliente.post(URL, json=PRODUTO_VALIDO, headers=auth()), 500, "ERRO_INTERNO")
    assert "banco indisponível" not in json.dumps(corpo, ensure_ascii=False)


# ---- Segurança / autorização -----------------------------------------------------------

def test_alg_none_recusado(amb):
    import jwt as pyjwt
    t = pyjwt.encode({"sub": "USR-7", "tenant_id": "EMP-34", "active_scope": "SUPPLIER", "iss": "identity-service",
                      "aud": "b2b-platform", "exp": 9999999999}, key=None, algorithm="none", headers={"kid": "chave-teste-1"})
    problema(amb.cliente.post(URL, json=PRODUTO_VALIDO, headers={"Authorization": "Bearer " + t}), 401, "TOKEN_INVALIDO")


def test_outra_empresa_nao_exclui(amb):
    pid = amb.cliente.post(URL, json=PRODUTO_VALIDO, headers=auth()).json()["produto_id"]
    problema(amb.cliente.delete(f"{URL}/{pid}", headers=auth(tenant="EMP-99")), 403, "PRODUTO_DE_OUTRA_EMPRESA")
    assert amb.cliente.get(f"{URL}/{pid}", headers=auth("BUYER")).status_code == 200


def test_bearer_minusculo(amb):
    """RFC 6750 trata o esquema como case-insensitive; a ESP exige 'Bearer '. Registra o comportamento."""
    t = token()
    r = amb.cliente.get(URL, headers={"Authorization": "bearer " + t})
    assert r.status_code in (200, 401)
    pytest.bearer_minusculo = r.status_code


@pytest.mark.parametrize("qs", ["page=-1", "size=-5", "page=1e0", "size=%2010", "page=99999999999999999999"])
def test_paginacao_bordas(amb, qs):
    r = amb.cliente.get(f"{URL}?{qs}", headers=auth("BUYER"))
    assert r.status_code in (200, 422), r.text
    if qs.startswith(("page=-", "size=-", "page=1e")):
        problema(r, 422, "PAGINACAO_INVALIDA")
