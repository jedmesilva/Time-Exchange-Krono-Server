from datetime import datetime
from pydantic import BaseModel, EmailStr
from models.enums import (
    RepurchaseType, SeriesStatus, OrderType, OrderStatus,
    PaymentMode, PaymentPriceType, TransactionType, KycStatus,
)


# ─────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────

class RegisterRequest(BaseModel):
    full_name: str
    email: EmailStr
    document: str
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


# ─────────────────────────────────────────────
# USERS
# ─────────────────────────────────────────────

class UserPublic(BaseModel):
    id: str
    full_name: str
    verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class SkillCreate(BaseModel):
    name: str
    description: str | None = None


class SkillResponse(BaseModel):
    id: str
    name: str
    description: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────
# BALANCES
# ─────────────────────────────────────────────

class BalanceDepositRequest(BaseModel):
    amount: float


class BalanceResponse(BaseModel):
    amount: float
    debt_interest: float
    updated_at: datetime

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────
# TIME SERIES
# ─────────────────────────────────────────────

class SeriesCreate(BaseModel):
    quantity_hours: int
    repurchase_type: RepurchaseType
    repurchase_price: float | None = None
    expires_at: datetime


class SeriesResponse(BaseModel):
    id: str
    issuer_id: str
    quantity_hours: int
    repurchase_type: RepurchaseType
    repurchase_price: float | None
    emitted_at: datetime
    expires_at: datetime
    status: SeriesStatus

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────
# POSITIONS
# ─────────────────────────────────────────────

class PositionResponse(BaseModel):
    id: str
    time_series_id: str
    holder_id: str
    quantity_hours: int
    updated_at: datetime

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────
# ORDER BOOK
# ─────────────────────────────────────────────

class OrderCreate(BaseModel):
    time_series_id: str
    type: OrderType
    price_hour: float
    quantity_hours: int
    payment_mode: PaymentMode = PaymentMode.MONEY
    payment_position_id: str | None = None
    payment_price_type: PaymentPriceType | None = None
    payment_fixed_price: float | None = None
    expires_at: datetime | None = None


class OrderResponse(BaseModel):
    id: str
    time_series_id: str
    user_id: str
    type: OrderType
    price_hour: float
    quantity_hours: int
    payment_mode: PaymentMode
    status: OrderStatus
    created_at: datetime
    expires_at: datetime | None

    model_config = {"from_attributes": True}


class OrderBookResponse(BaseModel):
    bids: list[OrderResponse]
    asks: list[OrderResponse]


# ─────────────────────────────────────────────
# TRANSACTIONS
# ─────────────────────────────────────────────

class TransactionResponse(BaseModel):
    id: str
    time_series_id: str
    type: TransactionType
    from_user_id: str
    to_user_id: str
    quantity_hours: int
    price_hour: float
    total: float
    payment_mode: PaymentMode
    transacted_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_obj(cls, obj):
        return cls(
            id=obj.id,
            time_series_id=obj.time_series_id,
            type=obj.type,
            from_user_id=obj.from_user_id,
            to_user_id=obj.to_user_id,
            quantity_hours=obj.quantity_hours,
            price_hour=float(obj.price_hour),
            total=float(obj.quantity_hours) * float(obj.price_hour),
            payment_mode=obj.payment_mode,
            transacted_at=obj.transacted_at,
        )


# ─────────────────────────────────────────────
# MARKET
# ─────────────────────────────────────────────

class MarketPriceResponse(BaseModel):
    time_series_id: str
    last_price: float
    recorded_at: datetime

    model_config = {"from_attributes": True}


class LiabilityResponse(BaseModel):
    issuer_id: str
    total_liability: float


class HonorScoreResponse(BaseModel):
    issuer_id: str
    liquidated: int
    expired: int
    total_settled: int
    honor_score: float | None


class YieldCurvePoint(BaseModel):
    series_id: str
    expires_at: datetime
    last_price: float | None
    repurchase_type: RepurchaseType
    repurchase_price: float | None
    hours_in_circulation: int
    status: SeriesStatus

    model_config = {"from_attributes": True}


class YieldCurveResponse(BaseModel):
    issuer_id: str
    points: list[YieldCurvePoint]


class RollCheckResponse(BaseModel):
    series_id: str
    expires_at: datetime
    roll_available: bool
    next_series_id: str | None
    next_expires_at: datetime | None
    next_last_price: float | None
    roll_spread: float | None


# ─────────────────────────────────────────────
# ROLLS
# ─────────────────────────────────────────────

class RollResponse(BaseModel):
    id: str
    issuer_id: str
    holder_id: str
    from_series_id: str
    from_price: float
    to_series_id: str
    to_price: float
    roll_spread: float
    quantity_hours: int
    rolled_at: datetime

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────
# PERFIL FINANCEIRO DO EMISSOR
# ─────────────────────────────────────────────

class EmitterComposition(BaseModel):
    total_series_active: int
    fixed_series: int
    market_series: int
    fixed_pct: float
    market_pct: float
    hours_in_circulation: int
    hours_own_portfolio: int
    emitting_continuously: bool


class EmitterProfileResponse(BaseModel):
    issuer_id: str
    honor_score: float | None
    total_liability: float
    composition: EmitterComposition
    yield_curve: list[YieldCurvePoint]
