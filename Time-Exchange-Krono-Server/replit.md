# Krono

A bolsa de tempo humano — plataforma onde pessoas emitem contratos de tempo futuro, o mercado precifica esses contratos via transações, e a liquidação conecta organicamente ao mercado de trabalho.

## Run & Operate

- Servidor: inicia automaticamente via workflow `artifacts/api-server: API Server`
- URL local: `http://localhost:80/api`
- Docs interativos: `http://localhost:80/api/docs`
- Liquidação automática: roda a cada hora via APScheduler

## Stack

- Python 3.12 + FastAPI + uvicorn
- PostgreSQL + SQLAlchemy (async, asyncpg)
- Autenticação: JWT (python-jose) + bcrypt (passlib)
- Scheduler: APScheduler (liquidação automática)
- Pydantic v2 para validação de schemas

## Where things live

```
artifacts/api-server/
├── main.py              # FastAPI app + lifespan + routers
├── database.py          # Engine asyncpg + Base + get_db
├── auth.py              # JWT + bcrypt + get_current_user
├── config.py            # Settings (secret_key, interest_rate)
├── requirements.txt
├── models/
│   ├── enums.py         # RepurchaseType, SeriesStatus, OrderType, etc.
│   └── models.py        # SQLAlchemy ORM: User, TimeSeries, Position, Order, Transaction, Roll, MarketPrice
├── schemas/
│   └── schemas.py       # Pydantic v2 schemas (request/response)
├── routers/
│   └── routers.py       # Todos os routers: auth, users, balances, series, positions, orders, transactions, market, rolls
└── services/
    ├── matching.py      # Matching engine (BID/ASK, FIFO, price priority)
    └── liquidation.py   # Liquidação automática + rolagem + juros sobre saldo negativo
```

## Architecture decisions

- Todas as tabelas criadas automaticamente no startup via `Base.metadata.create_all`
- Matching engine executa sincronamente na criação de cada ordem (within the same DB transaction)
- Liquidação roda a cada hora via APScheduler; spread de rolagem resolvido via saldo
- `sslmode` removido da DATABASE_URL para compatibilidade com asyncpg
- Prefixo `/api` aplicado a todos os routers no `main.py`

## Product

Primitivo central: **contrato de tempo** — ativo (emissor), quantidade (horas), vencimento, tipo (FIXED/MARKET).

Funcionalidades:
- Emissão de séries de tempo futuro (FIXED ou MARKET)
- Livro de ordens (BID/ASK) com matching engine automático
- Mercado secundário (contratos fungíveis por emissor+vencimento)
- Liquidação automática no vencimento com rolagem automática
- Curva de prazo por emissor
- Score de honramento (% de séries liquidadas)
- Perfil financeiro completo do emissor

## Endpoints principais

- `POST /api/auth/register` — cadastro
- `POST /api/auth/login` — login (retorna JWT)
- `POST /api/auth/verify` — verificação de identidade
- `POST /api/series` — emitir série (requer verificação)
- `POST /api/orders` — colocar ordem no livro
- `GET  /api/market/curve/{issuer_id}` — curva de prazo
- `GET  /api/market/profile/{issuer_id}` — perfil financeiro completo
- `GET  /api/market/honor/{issuer_id}` — score de honramento
- `GET  /api/docs` — documentação interativa (Swagger UI)

## Gotchas

- asyncpg não aceita `sslmode` na URL — removido em `database.py`
- `quantity_hours` deve ser inteiro positivo; `price_hour` deve ser positivo
- Somente usuários com `verified=True` podem emitir séries, colocar ordens, etc.
- O matching engine roda dentro da mesma sessão DB da criação da ordem (sem transação separada)
- Liquidação em série ACTIVE com `expires_at` no passado — nunca em OPEN
