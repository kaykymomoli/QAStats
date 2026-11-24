import os

import pytest
import requests

BASE = os.environ.get("IDENTITY_BASE_URL", "https://identity.matheus-alves.dev")
SENHA = os.environ.get("IDENTITY_SENHA_DEMO", "SenhaForte@2026!")  # credencial pública de demonstração (Guia de Testes)
MATRIZ = "01900000-0000-7000-8000-000000000010"
FILIAL = "01900000-0000-7000-8000-000000000020"
TRANSP = "01900000-0000-7000-8000-000000000030"
EMAILS = {"admin": "admin@agrobrasil.com.br", "fornecedor": "fornecedor@agrobrasil.com.br",
          "comprador": "comprador@agrobrasil.com.br", "transportador": "transportador@agrobrasil.com.br"}


@pytest.fixture(scope="session")
def http():
    s = requests.Session()
    s.headers["User-Agent"] = "qa-grupo8-tests"
    return s


def login(http, quem, **extra):
    return http.post(f"{BASE}/api/v1/auth/login", json={"email": EMAILS[quem], "password": SENHA, **extra}, timeout=20)


GRUPO = "01900000-0000-7000-8000-000000000001"


def contexto(http, quem, tenant, escopo, view_mode="SINGLE", tenants=None):
    temp = login(http, quem).json()["access_token"]
    corpo = {"view_mode": view_mode, "target_scope": escopo}
    if tenant:
        corpo["target_tenant_id"] = tenant
    if view_mode == "MACRO_GROUP":
        corpo["target_group_id"] = GRUPO
        corpo["target_tenants"] = tenants or [MATRIZ, FILIAL]
    return http.post(f"{BASE}/api/v1/auth/switch-context", headers={"Authorization": f"Bearer {temp}"}, json=corpo, timeout=20)


def eh_problema(r, status):
    assert r.status_code == status, f"{r.status_code} {r.text[:300]}"
    assert r.headers.get("content-type", "").startswith("application/problem+json"), r.headers.get("content-type")
    j = r.json()
    for campo in ("type", "title", "status", "detail", "code", "correlation_id"):
        assert campo in j, f"faltou {campo}: {j}"
    return j
