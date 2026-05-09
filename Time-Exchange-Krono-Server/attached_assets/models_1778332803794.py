import uuid
from datetime import datetime
from sqlalchemy import (
    String, Boolean, Numeric, Integer, DateTime,
    ForeignKey, Enum, UniqueConstraint, CheckConstraint, text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base
from models.enums import (
    RepurchaseType, SeriesStatus, OrderType, OrderStatus,
    PaymentMode, PaymentPriceType, TransactionType
)


def gen_uuid():
    return str(uuid.uuid4())


# ─────────────────────────────────────────────
# USERS
# ─────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    document: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    skills: Mapped[list["UserSkill"]] = relationship(back_populates="user")
    balance: Mapped["Balance"] = relationship(back_populates="user", uselist=False)
    series_issued: Mapped[list["TimeSeries"]] = relationship(back_populates="issuer")
    positions: Mapped[list["Position"]] = relationship(back_populates="holder")


# ─────────────────────────────────────────────
# USER SKILLS
# ─────────────────────────────────────────────

class UserSkill(Base):
    __tablename__ = "user_skills"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="skills")


# ─────────────────────────────────────────────
# BALANCES
# ─────────────────────────────────────────────

class Balance(Base):
    __tablename__ = "balances"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False, unique=True)
    amount: Mapped[float] = mapped_column(Numeric, nullable=False, default=0)
    debt_interest: Mapped[float] = mapped_column(Numeric, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="balance")


# ─────────────────────────────────────────────
# TIME SERIES
# ─────────────────────────────────────────────

class TimeSeries(Base):
    __tablename__ = "time_series"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    issuer_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    quantity_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    repurchase_type: Mapped[RepurchaseType] = mapped_column(Enum(RepurchaseType), nullable=False)
    repurchase_price: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    emitted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[SeriesStatus] = mapped_column(Enum(SeriesStatus), nullable=False, default=SeriesStatus.OPEN)

    issuer: Mapped["User"] = relationship(back_populates="series_issued")
    positions: Mapped[list["Position"]] = relationship(back_populates="time_series")
    orders: Mapped[list["Order"]] = relationship(back_populates="time_series")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="time_series")
    market_prices: Mapped[list["MarketPrice"]] = relationship(back_populates="time_series")

    __table_args__ = (
        CheckConstraint("quantity_hours > 0", name="ck_series_quantity_positive"),
        CheckConstraint(
            "(repurchase_type != 'FIXED') OR (repurchase_price IS NOT NULL)",
            name="ck_fixed_requires_price"
        ),
    )


# ─────────────────────────────────────────────
# POSITIONS
# ─────────────────────────────────────────────

class Position(Base):
    __tablename__ = "positions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    time_series_id: Mapped[str] = mapped_column(String, ForeignKey("time_series.id"), nullable=False)
    holder_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    quantity_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    time_series: Mapped["TimeSeries"] = relationship(back_populates="positions")
    holder: Mapped["User"] = relationship(back_populates="positions")

    __table_args__ = (
        UniqueConstraint("time_series_id", "holder_id", name="uq_position_series_holder"),
        CheckConstraint("quantity_hours > 0", name="ck_position_quantity_positive"),
    )


# ─────────────────────────────────────────────
# ORDER BOOK
# ─────────────────────────────────────────────

class Order(Base):
    __tablename__ = "order_book"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    time_series_id: Mapped[str] = mapped_column(String, ForeignKey("time_series.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    type: Mapped[OrderType] = mapped_column(Enum(OrderType), nullable=False)
    price_hour: Mapped[float] = mapped_column(Numeric, nullable=False)
    quantity_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    payment_mode: Mapped[PaymentMode] = mapped_column(Enum(PaymentMode), nullable=False, default=PaymentMode.MONEY)
    payment_position_id: Mapped[str | None] = mapped_column(String, ForeignKey("positions.id"), nullable=True)
    payment_price_type: Mapped[PaymentPriceType | None] = mapped_column(Enum(PaymentPriceType), nullable=True)
    payment_fixed_price: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), nullable=False, default=OrderStatus.OPEN)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    time_series: Mapped["TimeSeries"] = relationship(back_populates="orders")

    __table_args__ = (
        CheckConstraint("quantity_hours > 0", name="ck_order_quantity_positive"),
        CheckConstraint("price_hour > 0", name="ck_order_price_positive"),
    )


# ─────────────────────────────────────────────
# TRANSACTIONS
# ─────────────────────────────────────────────

class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    time_series_id: Mapped[str] = mapped_column(String, ForeignKey("time_series.id"), nullable=False)
    type: Mapped[TransactionType] = mapped_column(Enum(TransactionType), nullable=False)
    from_user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    to_user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    quantity_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    price_hour: Mapped[float] = mapped_column(Numeric, nullable=False)
    payment_mode: Mapped[PaymentMode] = mapped_column(Enum(PaymentMode), nullable=False, default=PaymentMode.MONEY)
    payment_position_id: Mapped[str | None] = mapped_column(String, ForeignKey("positions.id"), nullable=True)
    payment_price_type: Mapped[PaymentPriceType | None] = mapped_column(Enum(PaymentPriceType), nullable=True)
    payment_fixed_price: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    bid_order_id: Mapped[str | None] = mapped_column(String, ForeignKey("order_book.id"), nullable=True)
    ask_order_id: Mapped[str | None] = mapped_column(String, ForeignKey("order_book.id"), nullable=True)
    transacted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    time_series: Mapped["TimeSeries"] = relationship(back_populates="transactions")


# ─────────────────────────────────────────────
# ROLLS
# ─────────────────────────────────────────────

class Roll(Base):
    __tablename__ = "rolls"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    issuer_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    holder_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)

    from_series_id: Mapped[str] = mapped_column(String, ForeignKey("time_series.id"), nullable=False)
    from_price: Mapped[float] = mapped_column(Numeric, nullable=False)

    to_series_id: Mapped[str] = mapped_column(String, ForeignKey("time_series.id"), nullable=False)
    to_price: Mapped[float] = mapped_column(Numeric, nullable=False)

    quantity_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    rolled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    # spread positivo = contango (série seguinte mais cara = prejuízo ao titular)
    # spread negativo = backwardation (série seguinte mais barata = lucro ao titular)


# ─────────────────────────────────────────────
# MARKET PRICES
# ─────────────────────────────────────────────

class MarketPrice(Base):
    __tablename__ = "market_prices"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    time_series_id: Mapped[str] = mapped_column(String, ForeignKey("time_series.id"), nullable=False)
    transaction_id: Mapped[str] = mapped_column(String, ForeignKey("transactions.id"), nullable=False)
    last_price: Mapped[float] = mapped_column(Numeric, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    time_series: Mapped["TimeSeries"] = relationship(back_populates="market_prices")


# ─────────────────────────────────────────────
# ROLLS
# Registro de rolagem automática no vencimento
# Vincula a série que expirou com a série seguinte
# e registra o spread realizado
# ─────────────────────────────────────────────

class Roll(Base):
    __tablename__ = "rolls"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    issuer_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    holder_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)

    # Série que venceu
    from_series_id: Mapped[str] = mapped_column(String, ForeignKey("time_series.id"), nullable=False)
    from_price: Mapped[float] = mapped_column(Numeric, nullable=False)

    # Série seguinte
    to_series_id: Mapped[str] = mapped_column(String, ForeignKey("time_series.id"), nullable=False)
    to_price: Mapped[float] = mapped_column(Numeric, nullable=False)

    quantity_hours: Mapped[int] = mapped_column(Integer, nullable=False)

    # Spread realizado: positivo = contango, negativo = backwardation
    roll_spread: Mapped[float] = mapped_column(Numeric, nullable=False)

    rolled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    from_series: Mapped["TimeSeries"] = relationship(foreign_keys=[from_series_id])
    to_series: Mapped["TimeSeries"] = relationship(foreign_keys=[to_series_id])
