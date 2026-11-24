"""Suíte black-box do QA (Grupo 8) contra o Identity-Service publicado.

Carga leve e intencional (≈60 requisições): nada de força bruta ou estresse no ambiente compartilhado.
"""
import base64
import json
import statistics
import time

import jwt
import pytest
from conftest import BASE, FILIAL, MATRIZ, SENHA, TRANSP, contexto, eh_problema, login

AGORA = lambda: int(time.time())


# ---------------- Disponibilidade e JWKS ----------------

def test_readiness(http):
    r = http.get(f"{BASE}/health/ready", timeout=10)
    assert r.status_code == 200 and r.json()["status"] == "UP"
    assert r.json()["checks"] == {"database": "UP", "redis": "UP"}


def test_jwks_formato(http):
    r = http.get(f"{BASE}/.well-known/jwks.json", timeout=10)
    assert r.status_code == 200
    chaves = r.json()["keys"]
    assert chaves and all(k["kty"] == "RSA" and k["alg"] == "RS256" and k["use"] == "sig" and k.get("kid") for k in chaves)
    assert all("d" not in k and "p" not in k for k in chaves), "JWKS expõe parte privada!"
    n = base64.urlsafe_b64decode(chaves[0]["n"] + "==")
    assert len(n) * 8 >= 2048


def test_jwks_user_agent_python(http):
    """PyJWKClient (PyJWT) usa urllib -> UA 'Python-urllib/3.x'. É o cliente do SDK FastAPI oficial e dos
    adaptadores de Produtos/Fornecimentos. Se o Cloudflare barrar esse UA, todo consumidor Python recebe 503."""
    r = http.get(f"{BASE}/.well-known/jwks.json", headers={"User-Agent": "Python-urllib/3.12"}, timeout=10)
    assert r.status_code == 200, f"JWKS bloqueado para Python-urllib: {r.status_code} {r.text[:60]}"


def test_jwks_via_pyjwkclient_padrao():
    jwt.PyJWKClient(f"{BASE}/.well-known/jwks.json").get_signing_keys()


# ---------------- Login ----------------

@pytest.mark.parametrize("quem", ["admin", "fornecedor", "comprador", "transportador"])
def test_login_personas(http, quem):
    r = login(http, quem)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["token_type"] == "Bearer" and j["expires_in"] == 900 and j["refresh_token"] and j["available_contexts"]
    claims = jwt.decode(j["access_token"], options={"verify_signature": False})
    # token temporário: sem contexto -> Produtos/Fornecimentos devem responder 403 CONTEXTO_NAO_SELECIONADO
    assert claims["view_mode"] == "NONE" and claims["tenant_id"] is None and claims["active_scope"] is None


def test_login_senha_errada_e_email_inexistente_mesma_resposta(http):
    a = http.post(f"{BASE}/api/v1/auth/login", json={"email": "fornecedor@agrobrasil.com.br", "password": "SenhaErrada@2026!"}, timeout=20)
    b = http.post(f"{BASE}/api/v1/auth/login", json={"email": "naoexiste-qa@exemplo.com", "password": "SenhaErrada@2026!"}, timeout=20)
    ja, jb = eh_problema(a, 401), eh_problema(b, 401)
    assert ja["code"] == jb["code"] and ja["detail"] == jb["detail"], "permite enumeração de usuários"


@pytest.mark.parametrize("corpo", [{}, {"email": "x"}, {"password": "x"}, {"email": None, "password": None}, [], "texto"])
def test_login_corpo_invalido_retorna_4xx_problem(http, corpo):
    r = http.post(f"{BASE}/api/v1/auth/login", json=corpo, timeout=20)
    assert 400 <= r.status_code < 500, f"{r.status_code} {r.text[:200]}"
    assert r.headers.get("content-type", "").startswith("application/problem+json")


def test_login_json_malformado(http):
    r = http.post(f"{BASE}/api/v1/auth/login", data='{"email": ', headers={"Content-Type": "application/json"}, timeout=20)
    assert 400 <= r.status_code < 500 and r.headers.get("content-type", "").startswith("application/problem+json")


def test_login_email_case_insensitive(http):
    r = http.post(f"{BASE}/api/v1/auth/login", json={"email": "Fornecedor@AgroBrasil.com.br", "password": SENHA}, timeout=20)
    assert r.status_code == 200, "e-mail deveria ser comparado sem diferenciar maiúsculas"


def test_login_auto_contexto_transportador(http):
    r = login(http, "transportador", auto_context=True)
    assert r.status_code == 200
    c = jwt.decode(r.json()["access_token"], options={"verify_signature": False})
    assert c["tenant_id"] == TRANSP and c["active_scope"] == "CARRIER"


# ---------------- Switch-context ----------------

def test_switch_single_fornecedor_claims_compativeis_com_produtos(http):
    r = contexto(http, "fornecedor", MATRIZ, "SUPPLIER")
    assert r.status_code == 200, r.text
    tok = r.json()["access_token"]
    # User-Agent explícito: o UA padrão do PyJWKClient (Python-urllib) é barrado pelo Cloudflare (ver test_jwks_user_agent_python)
    chave = jwt.PyJWKClient(f"{BASE}/.well-known/jwks.json", headers={"User-Agent": "qa-grupo8"}).get_signing_key_from_jwt(tok).key
    c = jwt.decode(tok, chave, algorithms=["RS256"], audience="b2b-platform", issuer="identity-service")
    assert c["tenant_id"] == MATRIZ and c["active_scope"] == "SUPPLIER" and c["view_mode"] == "SINGLE"
    assert isinstance(c["exp"], int) and 0 < c["exp"] - AGORA() <= 900 + 60
    assert isinstance(c["sub"], str) and c["sub"]


def test_switch_macro_group_comprador(http):
    r = contexto(http, "comprador", None, "BUYER", view_mode="MACRO_GROUP")
    assert r.status_code == 200, r.text
    c = jwt.decode(r.json()["access_token"], options={"verify_signature": False})
    assert c["view_mode"] == "MACRO_GROUP" and c["tenant_id"] is None and set(c["allowed_tenants"]) >= {MATRIZ, FILIAL}


def test_switch_tenant_sem_vinculo_negado(http):
    r = contexto(http, "fornecedor", FILIAL, "SUPPLIER")
    assert r.status_code == 403, r.text


def test_switch_escopo_nao_habilitado_negado(http):
    r = contexto(http, "comprador", FILIAL, "SUPPLIER")  # filial só tem BUYER
    assert r.status_code == 403, r.text


def test_switch_macro_group_sem_permissao(http):
    r = contexto(http, "fornecedor", None, "SUPPLIER", view_mode="MACRO_GROUP", tenants=[MATRIZ])  # can_view_group = False
    assert r.status_code == 403, r.text


def test_switch_escopo_invalido(http):
    r = contexto(http, "fornecedor", MATRIZ, "supplier")
    assert 400 <= r.status_code < 500


# ---------------- Validação de token (/me) ----------------

def test_me_sem_token(http):
    eh_problema(http.get(f"{BASE}/api/v1/auth/me", timeout=10), 401)


def test_me_token_adulterado(http):
    tok = contexto(http, "fornecedor", MATRIZ, "SUPPLIER").json()["access_token"]
    h, p, s = tok.split(".")
    claims = json.loads(base64.urlsafe_b64decode(p + "=="))
    claims["active_scope"] = "TENANT_ADMIN"
    p2 = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    eh_problema(http.get(f"{BASE}/api/v1/auth/me", headers={"Authorization": f"Bearer {h}.{p2}.{s}"}, timeout=10), 401)


def test_me_alg_none(http):
    t = jwt.encode({"sub": "x", "iss": "identity-service", "aud": "b2b-platform", "exp": AGORA() + 600},
                   key=None, algorithm="none", headers={"kid": "key-2026-01"})
    eh_problema(http.get(f"{BASE}/api/v1/auth/me", headers={"Authorization": f"Bearer {t}"}, timeout=10), 401)


def test_me_reflete_claims(http):
    tok = contexto(http, "fornecedor", MATRIZ, "SUPPLIER").json()["access_token"]
    r = http.get(f"{BASE}/api/v1/auth/me", headers={"Authorization": f"Bearer {tok}"}, timeout=10)
    assert r.status_code == 200 and r.json()["active_scope"] == "SUPPLIER" and r.json()["tenant_id"] == MATRIZ


# ---------------- Refresh / logout ----------------

def test_refresh_rotacao_e_reuso_revoga_familia(http):
    rt1 = login(http, "comprador").json()["refresh_token"]
    r1 = http.post(f"{BASE}/api/v1/auth/refresh", json={"refresh_token": rt1}, timeout=20)
    assert r1.status_code == 200
    rt2 = r1.json()["refresh_token"]
    assert rt2 != rt1
    eh_problema(http.post(f"{BASE}/api/v1/auth/refresh", json={"refresh_token": rt1}, timeout=20), 401)  # reuso
    # após reuso detectado, a família inteira deve estar revogada (RFC 9700 §4.14)
    r3 = http.post(f"{BASE}/api/v1/auth/refresh", json={"refresh_token": rt2}, timeout=20)
    assert r3.status_code == 401, "refresh legítimo da família continuou válido após reuso"


def test_refresh_lixo(http):
    r = http.post(f"{BASE}/api/v1/auth/refresh", json={"refresh_token": "nao-e-um-token"}, timeout=20)
    assert r.status_code in (400, 401) and r.headers["content-type"].startswith("application/problem+json")


def test_logout_invalida_token_no_identity(http):
    tok = contexto(http, "fornecedor", MATRIZ, "SUPPLIER").json()["access_token"]
    assert http.post(f"{BASE}/api/v1/auth/logout", headers={"Authorization": f"Bearer {tok}"}, timeout=10).status_code == 204
    eh_problema(http.get(f"{BASE}/api/v1/auth/me", headers={"Authorization": f"Bearer {tok}"}, timeout=10), 401)


# ---------------- M2M ----------------

@pytest.mark.parametrize("cliente", ["order-service", "catalog-service"])
def test_client_credentials_documentado(http, cliente):
    r = http.post(f"{BASE}/api/v1/auth/token", data={"grant_type": "client_credentials", "client_id": cliente,
                                                      "client_secret": SENHA}, timeout=20)
    assert r.status_code == 200, f"Guia §Passo 7 promete 200; obtido {r.status_code}: {r.text[:200]}"


def test_client_credentials_grant_invalido(http):
    r = http.post(f"{BASE}/api/v1/auth/token", data={"grant_type": "password", "client_id": "x", "client_secret": "y"}, timeout=20)
    assert 400 <= r.status_code < 500


# ---------------- Autorização em governança ----------------

def test_fornecedor_nao_cria_tenant(http):
    tok = contexto(http, "fornecedor", MATRIZ, "SUPPLIER").json()["access_token"]
    r = http.post(f"{BASE}/api/v1/tenants", headers={"Authorization": f"Bearer {tok}"},
                  json={"group_id": "01900000-0000-7000-8000-000000000001", "cnpj": "00000000000191", "legal_name": "QA",
                        "branch_type": "BRANCH", "geo_lat": -15.6, "geo_lng": -56.1, "scopes": ["BUYER"]}, timeout=20)
    assert r.status_code == 403, r.text


def test_token_temporario_nao_acessa_governanca(http):
    temp = login(http, "admin").json()["access_token"]
    r = http.patch(f"{BASE}/api/v1/users/01900000-0000-7000-8000-000000000102/status",
                   headers={"Authorization": f"Bearer {temp}"}, json={"status": "SUSPENDED", "reason": "teste de autorizacao QA"}, timeout=20)
    assert r.status_code == 403, r.text


def test_introspect_exposto_em_producao(http):
    """Guia diz que introspect é 'apenas desenvolvimento'. Registra se está aberto em produção."""
    r = http.post(f"{BASE}/api/v1/auth/introspect", json={"token": "x"}, timeout=10)
    pytest.introspect_status = r.status_code
    assert r.status_code in (404, 403, 401), f"introspect acessível sem autenticação em produção: {r.status_code}"


# ---------------- Formato de erro e cabeçalhos ----------------

def test_rota_inexistente_problem_json(http):
    eh_problema(http.get(f"{BASE}/api/v1/nao-existe", timeout=10), 404)


def test_cabecalhos_de_seguranca(http):
    r = http.get(f"{BASE}/health/live", timeout=10)
    faltando = [h for h in ("Strict-Transport-Security", "X-Content-Type-Options") if h not in r.headers]
    assert not faltando, f"cabeçalhos ausentes: {faltando}"


# ---------------- Desempenho (amostra leve) ----------------

def test_latencia_jwks_e_me(http):
    tok = contexto(http, "fornecedor", MATRIZ, "SUPPLIER").json()["access_token"]
    tempos = []
    for _ in range(15):
        t0 = time.perf_counter()
        assert http.get(f"{BASE}/api/v1/auth/me", headers={"Authorization": f"Bearer {tok}"}, timeout=10).status_code == 200
        tempos.append((time.perf_counter() - t0) * 1000)
    p95 = sorted(tempos)[int(len(tempos) * 0.95) - 1]
    print(f"\n/me: mediana {statistics.median(tempos):.0f} ms, p95 {p95:.0f} ms")
    assert p95 <= 500, f"p95 {p95:.0f} ms acima da meta de 500 ms da plataforma"
