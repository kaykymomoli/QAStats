# Playground Identity — "Suíte de Testes (J-08)" executada via Playwright (headless)

Data: 2026-11-24 · Ambiente: Produção (PRD) · Resultado: **✓ 100% CONFORME (7/7 aprovados em 2704 ms)**

| ID | Jornada | Endpoint(s) | ms | Resultado | Mensagem |
|---|---|---|---|---|---|
| J-01 | Health & Cryptography Discovery | GET /health/ready, /.well-known/jwks.json | 401 | PASS | Live UP, Ready UP, JWKS RS256 verificado (kid: key-2026-01) |
| J-02 | Autenticação B2B & Context Switch | POST /auth/login → /switch-context | 702 | PASS | Login OK + Contexto Matriz ativo (TENANT_ADMIN) |
| J-03 | Rotação de Refresh Token | POST /auth/refresh | 230 | PASS | Token rotacionado, novo RT emitido |
| J-04 | Detecção de Reúso & Antifraude | POST /auth/refresh (replay) | 106 | PASS | ERR-AUTH-006 (família de sessões invalidada) |
| J-05 | Comutação Cross-Tenant | POST /auth/switch-context | 394 | PASS | Contexto comutado para Cooperativa AgroBrasil Sul |
| J-06 | Logout & Denylist Redis | POST /auth/logout → retry | 616 | PASS | Token rejeitado imediatamente: ERR-AUTH-002 |
| J-07 | Força Bruta & Lockout | POST /auth/login (5x) | 248 | PASS | Credenciais inválidas rejeitadas (sem enumeração) |

Observação do QA: J-07 só confirma 5 respostas 401; não demonstra bloqueio (lockout/429) depois das tentativas.
Os erros de console `ERR_TUNNEL_CONNECTION_FAILED` vieram de recursos de CDN barrados pelo proxy da sessão de testes, não do produto.
