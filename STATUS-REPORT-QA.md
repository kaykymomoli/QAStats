# Status Report de QA — Grupo 8 (Teste)

**Data:** 24/11/2026 · **Responsável:** Grupo 8 — QA
**Escopo:** (1) Grupo 2: Produtos e Fornecimentos (`produtos-service`, `fornecimentos-service`) · (2) Identity-Service (autenticação B2B multi-tenant)

---

## 1. Resumo executivo

| Sistema | Situação | Testes executados | Aprovados | Defeitos abertos |
|---|---|---|---|---|
| Produtos e Fornecimentos (Grupo 2) | 🟢 **Verde**, implementação conforme a especificação | 268 | 268 (100%) | 0 funcionais · 4 de comunicação/documentação · 2 observações |
| Identity-Service | 🟡 **Amarelo**, núcleo de autenticação OK, mas há bloqueio de integração | 65 (25 asserções Newman + 40 QA) + 7 Playground | 57 + 7 | 1 crítico · 1 alto · 1 médio · 1 baixo |
| **Integração Identity → Produtos/Fornecimentos** | 🔴 **Vermelho** com o cliente JWKS padrão · 🟢 com o contorno | 24 | 12 (só com o contorno) | ligado ao DEF-ID-01 |

**Principal risco:** o Cloudflare na frente do Identity-Service bloqueia (erro 1010) o User-Agent `Python-urllib`, usado pelo `PyJWKClient`. Com isso, **todo serviço Python que buscar o JWKS pela URL pública responde 503 em todas as rotas autenticadas.** Isso inclui o SDK FastAPI oficial do Identity e o adaptador `ChavesJwks` do Grupo 2. Reproduzimos o problema ponta a ponta: 0/12 cenários passam sem o contorno e 12/12 passam com ele.

---

## 2. Grupo 2 — Produtos e Fornecimentos

Referência: `davicalvarenga/Sistema-MicServ-SD`, ESP-PRD-001 v2.1 e ESP-FRN-001 v2.1.

### 2.1 Execução

| Suíte | Tipo | Resultado |
|---|---|---|
| Suíte dos desenvolvedores: `produtos-service` | unidade e contrato + PostgreSQL 16 real | **64/64** ✅ |
| Suíte dos desenvolvedores: `fornecimentos-service` | unidade e contrato + PostgreSQL 16 real | **114/114** ✅ |
| Suíte QA independente: produtos (`testes/grupo2-produtos-fornecimentos/test_qa_produtos.py`) | caixa-preta: valores-limite, mensagem ao UX, segurança | **58/58** ✅ |
| Suíte QA independente: fornecimentos (`test_qa_fornecimentos.py`) | caixa-preta: valores-limite, mensagem ao UX, segurança | **32/32** ✅ |

> Os 18 testes de banco, que antes eram *skipped*, foram executados com um PostgreSQL 16 local e o `01-init.sql` do kit de infraestrutura.

### 2.2 O que foi verificado (destaques)

- Os enums do recado ao UX: as 5 unidades, os 4 tipos de transporte, e "Rodoviário"/`RODOVIARIO` → 422 `DADOS_INVALIDOS`.
- `peso_unitario_kg` opcional (null), limites, `NaN`/`Infinity` recusados e notação científica aceita.
- Fornecimento: o exemplo `{"cidade":"Sorriso","uf":"MT"}` gera 201. `preco` e quantidade com 2 casas são aceitos e com 3 casas → 422. `"142,35"` (string) → 422. `uf` em minúsculas, por extenso ou fora da lista → 422.
- `categoria` enviada no fornecimento é ignorada e `status: "PAUSADO"` também é ignorado. Um produto digitado (não escolhido do catálogo) → 422 `PRODUTO_INEXISTENTE`.
- Aritmética decimal: 0,1 + 0,2 = 0,3 exatos, sem erro de float.
- Erros em `application/problem+json` com `title`, `detail`, `codigo` e `correlationId`. O `X-Correlation-Id` é ecoado e o erro 500 não vaza a mensagem da exceção.
- 401 (ausente, inválido, expirado, `alg: none`), 403 `CONTEXTO_NAO_SELECIONADO`, 503 quando o JWKS cai, e isolamento entre empresas (`PRODUTO_DE_OUTRA_EMPRESA` e `FORNECIMENTO_DE_OUTRA_EMPRESA`).

### 2.3 Divergências entre o recado ao UX e a API

| ID | Severidade | Recado ao UX | Comportamento real (ESP v2.1, confirmado em teste) | Ação sugerida |
|---|---|---|---|---|
| DOC-01 | **Alta** | "categoria (texto)" | **Lista fixa**: `GRAOS`, `INSUMOS`, `SUBPRODUTOS`, `LATICINIOS`, `CARNES`, `HORTIFRUTI`, `BEBIDAS`, `OUTROS`. Texto livre, minúsculas ou acento ("Laticínios") → 422 | Corrigir o recado. Na tela, usar *select*, não campo de texto |
| DOC-02 | Média | "Não existe status; pausar ou encerrar depende do professor" | **Encerrar já existe**: `PATCH /api/v1/fornecimentos/{id}` com `{"encerrar": true}` zera o disponível e tira a oferta da vitrine. Também aceita `preco` e `repor`. *Pausar* (reversível) realmente não existe | Atualizar o recado e decidir o fluxo na tela |
| DOC-03 | Média | Erros com `codigo` e `correlationId` | Vale para Produtos e Fornecimentos. O **Identity** usa `code` e `correlation_id` (`ERR-AUTH-xxx`), conforme a Q-02 da ESP | A tela deve tratar os dois formatos |
| DOC-04 | Baixa | (omitido) | Regras que a tela precisa conhecer: `nome` de 2 a 255 caracteres; `uf` = 27 siglas em maiúsculas; preço de 0 a 9.999.999.999,99; peso com até 3 casas; **BUYER também cadastra produto**, mas só SUPPLIER cadastra fornecimento; 403 `PERFIL_NAO_PERMITIDO`; 403 `CONTEXTO_DE_GRUPO_NAO_PERMITIDO` (token MACRO_GROUP não escreve; não deslogar) | Incluir no recado |

### 2.4 Observações (sem bloqueio)

| ID | Severidade | Descrição |
|---|---|---|
| OBS-G2-01 | Baixa | `X-Correlation-Id` sem limite de tamanho: um valor de 5.000 caracteres foi aceito, ecoado na resposta e gravado no log. Sugestão: limitar (ex.: 128 caracteres) ou gerar um UUID novo. |
| OBS-G2-02 | Baixa | `Authorization: bearer <token>` (minúsculo) → 401 `TOKEN_AUSENTE`. A RFC 7235 trata o esquema sem diferenciar maiúsculas. Segue a ESP, mas pode surpreender quem integra. |

---

## 3. Identity-Service

Referência: `Matheus-Allvz/Identity-Service`, API `https://identity.matheus-alves.dev`.

### 3.1 Execução

| Suíte | Resultado |
|---|---|
| Coleção Postman oficial (Newman): 19 requisições, 25 asserções | **23/25** — falham as 2 asserções do token M2M (DEF-ID-02) |
| Suíte QA caixa-preta (`testes/identity-service/test_qa_identity.py`) | **34/40** — 6 falhas = DEF-ID-01 (×2), DEF-ID-02 (×2), DEF-ID-03, DEF-ID-04 |
| Integração real Identity → produtos/fornecimentos (`test_integracao_produtos.py`), cliente JWKS padrão | **0/12** (503 `DEPENDENCIA_INDISPONIVEL`) |
| Mesma integração, com User-Agent explícito no `PyJWKClient` | **12/12** ✅ |
| Suíte interna do Playground (J-01 a J-07), via navegador headless | **7/7** ✅ |
| Suíte .NET do repositório (xUnit + Testcontainers) | ⚪ **não executada**: o SDK .NET 10 e as imagens de container não estavam acessíveis no ambiente de QA |

**Funcionando corretamente:** health/readiness, JWKS (RS256, 2048 bits, sem parte privada), login das 4 personas, token temporário sem contexto (`view_mode: NONE`), switch-context SINGLE e MACRO_GROUP, negação de tenant sem vínculo, de escopo não habilitado e de MACRO_GROUP sem permissão, `/me`, recusa de token adulterado e de `alg: none`, rotação de refresh com revogação da família no reuso, logout com denylist imediata, mesma resposta para senha errada e e-mail inexistente (sem enumeração), autorização em governança, e latência de `/me` com p95 de 90 ms (meta: 500 ms).

**Compatibilidade com o contrato do Grupo 2:** confirmada. Os tokens reais trazem `iss: identity-service`, `aud: b2b-platform`, `sub`, `tenant_id`, `active_scope`, `exp` inteiro e `kid` no cabeçalho. Com tokens reais, Produtos e Fornecimentos se comportaram como especificado: SUPPLIER cadastra; token do login → 403 `CONTEXTO_NAO_SELECIONADO`; MACRO_GROUP lê, mas não escreve; CARRIER → 403; BUYER cadastra produto, mas não fornecimento.

### 3.2 Defeitos

| ID | Severidade | Título | Evidência / reprodução | Responsável sugerido |
|---|---|---|---|---|
| **DEF-ID-01** | 🔴 **Crítica** | Cloudflare bloqueia o JWKS para o User-Agent `Python-urllib` (erro 1010) | `curl -A "Python-urllib/3.12" https://identity.matheus-alves.dev/.well-known/jwks.json` → **403**; com `curl/…` ou `python-requests/…` → 200. O `jwt.PyJWKClient` (usado no SDK `Docs/sdks/b2b_auth_fastapi.py` e no `ChavesJwks` do Grupo 2) recebe 403, e o serviço responde 503 em tudo | Identity: liberar a rota `/.well-known/jwks.json` na regra do WAF (Browser Integrity Check). Consumidores: passar `headers={"User-Agent": "..."}` ao `PyJWKClient`. Grupo 2/Infra: confirmar que `AUTH_JWKS_URL` aponta ao gateway interno e não à URL pública |
| **DEF-ID-02** | 🟠 Alta | Token de serviço (client_credentials) não funciona em produção | `POST /api/v1/auth/token` com `order-service` ou `catalog-service` e o segredo do Guia (Passo 7) → 401 `ERR-AUTH-001`. A asserção da própria coleção Postman falha | Identity: reaplicar o seed das contas de serviço ou corrigir o Guia |
| **DEF-ID-03** | 🟡 Média | `/api/v1/auth/introspect` aberto sem autenticação em produção | O Guia diz "apenas desenvolvimento". Qualquer pessoa que envie um token recebe `sub`, `tenant_id`, `roles` e `permissions`. A RFC 7662 §2.1 exige proteger o endpoint | Identity: desabilitar em PRD ou exigir credencial |
| **DEF-ID-04** | 🔵 Baixa | Faltam cabeçalhos de segurança | As respostas da API não trazem `Strict-Transport-Security` nem `X-Content-Type-Options` | Identity/Infra: adicionar no Caddy ou no Cloudflare |

### 3.3 Observações

- **OBS-ID-01:** login com senha fora da política retorna 422 `ERR-VAL-003` ("política de palavra-passe violada") em vez de 401. Não permite enumerar contas, mas expõe a política e foge do padrão.
- **OBS-ID-02:** em governança, a validação do corpo (400) acontece antes da autorização (403). Um usuário sem permissão descobre o schema.
- **OBS-ID-03 (risco aceito, Q-16):** confirmado com tokens reais. Depois do logout, Produtos e Fornecimentos **continuam aceitando o token por até 15 minutos**, porque a validação offline não consulta a denylist. O próprio Identity recusa o token na hora.
- **OBS-ID-04:** o J-07 do Playground ("Lockout") só verifica 5 respostas 401 e não comprova bloqueio por excesso de tentativas. Não fizemos força bruta no ambiente compartilhado.

---

## 4. Próximos passos

1. **[Identity + Grupo 2 + Infra] DEF-ID-01:** corrigir antes de qualquer teste integrado. É bloqueante para todo consumidor Python.
2. **[Identity] DEF-ID-02 e DEF-ID-03.**
3. **[Grupo 2] DOC-01 a DOC-04:** reenviar o recado ao UX corrigido (principalmente a categoria como lista fixa).
4. **[QA]** Rodar a suíte .NET do Identity num ambiente com Docker e .NET 10, e o teste de carga k6 (p95 ≤ 500 ms com 200 usuários simultâneos), assim que o ambiente integrado estiver no ar.

## 5. Como reproduzir

Instruções em [`README.md`](README.md). Evidências em [`evidencias/`](evidencias/): relatórios JUnit sem tokens, resumo do Newman e saída da suíte do Playground.
