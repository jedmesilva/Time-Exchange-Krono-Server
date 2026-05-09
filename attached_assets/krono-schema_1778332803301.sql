-- ─────────────────────────────────────────────────────────────
-- KRONO — Schema v0.1
-- Bolsa de Tempo Humano
-- ─────────────────────────────────────────────────────────────


-- ─────────────────────────────────────────────────────────────
-- ENUMS
-- ─────────────────────────────────────────────────────────────

CREATE TYPE repurchase_type   AS ENUM ('FIXED', 'MARKET');
CREATE TYPE series_status     AS ENUM ('OPEN', 'ACTIVE', 'LIQUIDATED', 'EXPIRED');
CREATE TYPE order_type        AS ENUM ('BID', 'ASK');
CREATE TYPE order_status      AS ENUM ('OPEN', 'FILLED', 'CANCELLED');
CREATE TYPE payment_mode      AS ENUM ('MONEY', 'CONTRACT', 'BOTH');
CREATE TYPE payment_price     AS ENUM ('FIXED', 'MARKET');
CREATE TYPE transaction_type  AS ENUM ('PRIMARY', 'SECONDARY', 'LIQUIDATION');


-- ─────────────────────────────────────────────────────────────
-- USERS
-- Identidade verificada — lastro de todos os contratos
-- ─────────────────────────────────────────────────────────────

CREATE TABLE users (
  id                UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  full_name         TEXT          NOT NULL,
  email             TEXT          NOT NULL UNIQUE,
  document          TEXT          NOT NULL UNIQUE,  -- CPF ou equivalente
  verified          BOOLEAN       NOT NULL DEFAULT FALSE,
  verified_at       TIMESTAMP,
  created_at        TIMESTAMP     NOT NULL DEFAULT NOW()
);


-- ─────────────────────────────────────────────────────────────
-- USER SKILLS
-- Habilidades do emissor — escopo da liquidação em serviço
-- ─────────────────────────────────────────────────────────────

CREATE TABLE user_skills (
  id                UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id           UUID          NOT NULL REFERENCES users(id),
  name              TEXT          NOT NULL,
  description       TEXT,
  created_at        TIMESTAMP     NOT NULL DEFAULT NOW()
);


-- ─────────────────────────────────────────────────────────────
-- BALANCES
-- Saldo financeiro de cada usuário dentro da Krono
-- Pode ser negativo (emissor inadimplente)
-- ─────────────────────────────────────────────────────────────

CREATE TABLE balances (
  id                UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id           UUID          NOT NULL UNIQUE REFERENCES users(id),
  amount            NUMERIC       NOT NULL DEFAULT 0,  -- pode ser negativo
  debt_interest     NUMERIC       NOT NULL DEFAULT 0,  -- juros acumulados sobre saldo negativo
  updated_at        TIMESTAMP     NOT NULL DEFAULT NOW()
);


-- ─────────────────────────────────────────────────────────────
-- TIME SERIES
-- Unidade negociável — par emissor + vencimento
-- Equivalente ao contrato futuro em bolsas de commodities
-- ─────────────────────────────────────────────────────────────

CREATE TABLE time_series (
  id                UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  issuer_id         UUID          NOT NULL REFERENCES users(id),

  -- Quantidade total emitida
  quantity_hours    INTEGER       NOT NULL CHECK (quantity_hours > 0),

  -- Tipo de recompra
  repurchase_type   repurchase_type NOT NULL,
  repurchase_price  NUMERIC,  -- R$/hora; obrigatório se FIXED, null se MARKET

  -- Datas
  emitted_at        TIMESTAMP     NOT NULL DEFAULT NOW(),
  expires_at        TIMESTAMP     NOT NULL,

  -- Status
  status            series_status NOT NULL DEFAULT 'OPEN',

  CONSTRAINT fixed_requires_price
    CHECK (repurchase_type != 'FIXED' OR repurchase_price IS NOT NULL)
);


-- ─────────────────────────────────────────────────────────────
-- POSITIONS
-- Posse de horas por usuário em uma série
-- Atualizada a cada transação
-- ─────────────────────────────────────────────────────────────

CREATE TABLE positions (
  id                UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  time_series_id    UUID          NOT NULL REFERENCES time_series(id),
  holder_id         UUID          NOT NULL REFERENCES users(id),
  quantity_hours    INTEGER       NOT NULL CHECK (quantity_hours > 0),
  updated_at        TIMESTAMP     NOT NULL DEFAULT NOW(),

  UNIQUE (time_series_id, holder_id)
);


-- ─────────────────────────────────────────────────────────────
-- ORDER BOOK
-- Livro de ordens por série — forma o preço de mercado
-- ─────────────────────────────────────────────────────────────

CREATE TABLE order_book (
  id                    UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  time_series_id        UUID          NOT NULL REFERENCES time_series(id),
  user_id               UUID          NOT NULL REFERENCES users(id),

  type                  order_type    NOT NULL,   -- BID | ASK
  price_hour            NUMERIC       NOT NULL,
  quantity_hours        INTEGER       NOT NULL CHECK (quantity_hours > 0),

  -- Meio de pagamento da ordem
  payment_mode          payment_mode  NOT NULL DEFAULT 'MONEY',
  payment_position_id   UUID          REFERENCES positions(id),  -- se CONTRACT
  payment_price_type    payment_price,                            -- se CONTRACT
  payment_fixed_price   NUMERIC,                                  -- se FIXED

  status                order_status  NOT NULL DEFAULT 'OPEN',
  created_at            TIMESTAMP     NOT NULL DEFAULT NOW(),
  expires_at            TIMESTAMP     -- ordem pode ter validade
);


-- ─────────────────────────────────────────────────────────────
-- TRANSACTIONS
-- Registro imutável de todas as negociações fechadas
-- PRIMARY   → emissão inicial (emissor → primeiro comprador)
-- SECONDARY → mercado secundário (titular → novo titular)
-- LIQUIDATION → honramento no vencimento
-- ─────────────────────────────────────────────────────────────

CREATE TABLE transactions (
  id                    UUID              PRIMARY KEY DEFAULT gen_random_uuid(),
  time_series_id        UUID              NOT NULL REFERENCES time_series(id),
  type                  transaction_type  NOT NULL,

  from_user_id          UUID              NOT NULL REFERENCES users(id),
  to_user_id            UUID              NOT NULL REFERENCES users(id),

  quantity_hours        INTEGER           NOT NULL,
  price_hour            NUMERIC           NOT NULL,
  total                 NUMERIC           GENERATED ALWAYS AS (quantity_hours * price_hour) STORED,

  -- Meio de pagamento
  payment_mode          payment_mode      NOT NULL DEFAULT 'MONEY',
  payment_position_id   UUID              REFERENCES positions(id),  -- se CONTRACT
  payment_price_type    payment_price,
  payment_fixed_price   NUMERIC,

  -- Referência às ordens que geraram a transação
  bid_order_id          UUID              REFERENCES order_book(id),
  ask_order_id          UUID              REFERENCES order_book(id),

  transacted_at         TIMESTAMP         NOT NULL DEFAULT NOW()
);


-- ─────────────────────────────────────────────────────────────
-- MARKET PRICES
-- Último preço negociado por série
-- Inserido a cada transação fechada
-- ─────────────────────────────────────────────────────────────

CREATE TABLE market_prices (
  id                UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  time_series_id    UUID          NOT NULL REFERENCES time_series(id),
  transaction_id    UUID          NOT NULL REFERENCES transactions(id),
  last_price        NUMERIC       NOT NULL,
  recorded_at       TIMESTAMP     NOT NULL DEFAULT NOW()
);


-- ─────────────────────────────────────────────────────────────
-- VIEWS
-- ─────────────────────────────────────────────────────────────

-- Último preço por série
CREATE VIEW current_market_prices AS
SELECT DISTINCT ON (time_series_id)
  time_series_id,
  last_price,
  recorded_at
FROM market_prices
ORDER BY time_series_id, recorded_at DESC;


-- Débito potencial por emissor
-- Soma do que o emissor deve ao mercado, a preço corrente
CREATE VIEW issuer_liability AS
SELECT
  ts.issuer_id,
  SUM(
    CASE
      WHEN ts.repurchase_type = 'FIXED'
        THEN p.quantity_hours * ts.repurchase_price
      WHEN ts.repurchase_type = 'MARKET'
        THEN p.quantity_hours * cmp.last_price
    END
  ) AS total_liability
FROM time_series ts
JOIN positions p
  ON p.time_series_id = ts.id
  AND p.holder_id != ts.issuer_id  -- exclui horas que o emissor já recomprou
JOIN current_market_prices cmp
  ON cmp.time_series_id = ts.id
WHERE ts.status = 'ACTIVE'
GROUP BY ts.issuer_id;


-- Honor score por emissor
-- Percentual de séries liquidadas sobre total vencido
CREATE VIEW honor_scores AS
SELECT
  issuer_id,
  COUNT(*) FILTER (WHERE status = 'LIQUIDATED') AS liquidated,
  COUNT(*) FILTER (WHERE status = 'EXPIRED')    AS expired,
  COUNT(*) FILTER (WHERE status IN ('LIQUIDATED', 'EXPIRED')) AS total_settled,
  ROUND(
    COUNT(*) FILTER (WHERE status = 'LIQUIDATED')::NUMERIC /
    NULLIF(COUNT(*) FILTER (WHERE status IN ('LIQUIDATED', 'EXPIRED')), 0) * 100,
    2
  ) AS honor_score
FROM time_series
GROUP BY issuer_id;
