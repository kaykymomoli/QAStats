# QAStats: testes do Grupo 8 (QA)

- [`STATUS-REPORT-QA.md`](STATUS-REPORT-QA.md): status report consolidado.
- `testes/grupo2-produtos-fornecimentos/`: suíte independente para produtos-service e fornecimentos-service.
- `testes/identity-service/`: suíte caixa-preta do Identity-Service e teste de integração com tokens reais.
- `evidencias/`: JUnit XML (sem tokens), resumo do Newman e da suíte do Playground.

## Pré-requisitos

```bash
python3 -m venv .venv && . .venv/bin/activate
git clone https://github.com/davicalvarenga/Sistema-MicServ-SD.git ../Sistema-MicServ-SD
pip install -r ../Sistema-MicServ-SD/servicos/fornecimentos-service/requirements-dev.txt requests
```

## Grupo 2: Produtos e Fornecimentos

```bash
# opcional, para os testes de banco: PostgreSQL local + init do kit de infraestrutura
export PG_ADMIN_DSN="host=localhost port=5432 dbname=postgres user=postgres"
export KIT_INIT_SQL=../portal-b2b-kit-infra/database/01-init.sql
testes/grupo2-produtos-fornecimentos/run_grupo2.sh ../Sistema-MicServ-SD ./resultados
```

## Identity-Service

```bash
cd testes/identity-service
python -m pytest -q test_qa_identity.py -s
# integração real: tokens do Identity → serviços do Grupo 2 (JWKS de produção)
SERVICO=produtos      PYTHONPATH=../../../Sistema-MicServ-SD/servicos/produtos-service:.      python -m pytest -q test_integracao_produtos.py
SERVICO=fornecimentos PYTHONPATH=../../../Sistema-MicServ-SD/servicos/fornecimentos-service:. python -m pytest -q test_integracao_produtos.py
# CONTORNAR_UA=1 aplica o contorno do DEF-ID-01 (User-Agent explícito no PyJWKClient)
# Coleção oficial:
npx newman run <Identity-Service>/Docs/postman-collection-b2b.json --reporters cli
```

A suíte do Identity faz cerca de 60 requisições leves ao ambiente compartilhado, sem força bruta nem carga.
Ela usa as credenciais públicas de demonstração do Guia de Testes do Identity (`IDENTITY_SENHA_DEMO` permite trocar).
