# Newman — coleção oficial Identity-Service B2B

Requisições: 19 (0 falhas de rede) · Asserções: 25 (2 falhas)

| Requisição | Método | HTTP | ms | Asserções OK | Falhas |
|---|---|---|---|---|---|
| Obter Chaves Públicas (JWKS) | GET | 200 | 724 | 2/2 |  |
| Login - Admin Matriz (Salva tempToken e tenants) | POST | 200 | 666 | 2/2 |  |
| Login - Fornecedor Matriz | POST | 200 | 827 | 1/1 |  |
| Login - Comprador Multi-Tenant (Matriz e Filial) | POST | 200 | 552 | 1/1 |  |
| Login com Auto-Contexto - Transportadora (SINGLE numa chamada) | POST | 200 | 602 | 2/2 |  |
| Login - Falha de Credenciais (401) | POST | 401 | 565 | 1/1 |  |
| Trocar Contexto - Admin Matriz (SINGLE - TENANT_ADMIN) | POST | 200 | 585 | 1/1 |  |
| Trocar Contexto - Comprador Macro Grupo (MACRO_GROUP - BUYER) | POST | 200 | 543 | 1/1 |  |
| Trocar Contexto - Comprador Filial (SINGLE - BUYER) | POST | 200 | 711 | 1/1 |  |
| Inspecionar Contexto Ativo - Admin Matriz | GET | 200 | 720 | 3/3 |  |
| Emitir Token M2M - order-service | POST | 401 | 481 | 0/2 | expected response to have status code 200 but got 401; expected undefined to deeply equal 'Bearer' |
| Renovar Sessão - Rotação de Refresh Token (Admin) | POST | 200 | 561 | 1/1 |  |
| Consumir Refresh Token (Sessão Fornecedor) | POST | 200 | 519 | 1/1 |  |
| Detecção de Reúso de Refresh Token (401) | POST | 401 | 511 | 1/1 |  |
| Criar Novo Tenant no Grupo | POST | 201 | 772 | 1/1 |  |
| Atualizar Status do Tenant (Governança) | PATCH | 200 | 780 | 1/1 |  |
| Suspender Usuário | PATCH | 200 | 523 | 1/1 |  |
| Reativar Usuário | PATCH | 200 | 540 | 1/1 |  |
| Logout Ativo | POST | 204 | 508 | 1/1 |  |
