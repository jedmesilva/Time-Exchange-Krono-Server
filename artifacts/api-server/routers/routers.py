from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from database import get_db
from models.models import User, UserSkill, Balance, TimeSeries, Position, Order, Transaction, MarketPrice, Roll
from models.enums import OrderStatus, OrderType, SeriesStatus, RepurchaseType
from schemas.schemas import (
    RegisterRequest, LoginRequest, TokenResponse,
    UserPublic, SkillCreate, SkillResponse,
    BalanceResponse, SeriesCreate, SeriesResponse,
    PositionResponse, OrderCreate, OrderResponse, OrderBookResponse,
    TransactionResponse, MarketPriceResponse, LiabilityResponse, HonorScoreResponse,
    YieldCurvePoint, YieldCurveResponse, RollCheckResponse,
    EmitterComposition, EmitterProfileResponse, RollResponse,
)
from auth import (
    hash_password, verify_password,
    create_access_token, create_refresh_token,
    get_current_user, get_verified_user,
)
from services.matching import match_order


# ─────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────

auth_router = APIRouter(prefix="/auth", tags=["auth"])


@auth_router.post("/register", response_model=UserPublic, status_code=201)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email já cadastrado")

    doc_existing = await db.execute(select(User).where(User.document == body.document))
    if doc_existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Documento já cadastrado")

    user = User(
        full_name=body.full_name,
        email=body.email,
        document=body.document,
        hashed_password=hash_password(body.password),
    )
    db.add(user)
    await db.flush()

    balance = Balance(user_id=user.id)
    db.add(balance)

    return user


@auth_router.post("/verify", response_model=UserPublic)
async def verify_identity(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    current_user.verified = True
    current_user.verified_at = datetime.utcnow()
    return current_user


@auth_router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Credenciais inválidas")

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


# ─────────────────────────────────────────────
# USERS
# ─────────────────────────────────────────────

users_router = APIRouter(prefix="/users", tags=["users"])


@users_router.get("/me", response_model=UserPublic)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@users_router.get("/{user_id}", response_model=UserPublic)
async def get_user(user_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return user


@users_router.get("/{user_id}/skills", response_model=list[SkillResponse])
async def get_user_skills(user_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserSkill).where(UserSkill.user_id == user_id))
    return result.scalars().all()


@users_router.post("/me/skills", response_model=SkillResponse, status_code=201)
async def add_skill(
    body: SkillCreate,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
):
    skill = UserSkill(user_id=current_user.id, **body.model_dump())
    db.add(skill)
    await db.flush()
    return skill


@users_router.delete("/me/skills/{skill_id}", status_code=204)
async def delete_skill(
    skill_id: str,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserSkill).where(
            and_(UserSkill.id == skill_id, UserSkill.user_id == current_user.id)
        )
    )
    skill = result.scalar_one_or_none()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill não encontrada")
    await db.delete(skill)


# ─────────────────────────────────────────────
# BALANCES
# ─────────────────────────────────────────────

balances_router = APIRouter(prefix="/balances", tags=["balances"])


@balances_router.get("/me", response_model=BalanceResponse)
async def get_balance(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Balance).where(Balance.user_id == current_user.id))
    balance = result.scalar_one_or_none()
    if not balance:
        raise HTTPException(status_code=404, detail="Saldo não encontrado")
    return balance


# ─────────────────────────────────────────────
# TIME SERIES
# ─────────────────────────────────────────────

series_router = APIRouter(prefix="/series", tags=["series"])


@series_router.post("", response_model=SeriesResponse, status_code=201)
async def emit_series(
    body: SeriesCreate,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
):
    if body.repurchase_type == RepurchaseType.FIXED and body.repurchase_price is None:
        raise HTTPException(status_code=400, detail="Preço de recompra obrigatório para contratos FIXED")

    series = TimeSeries(issuer_id=current_user.id, **body.model_dump())
    db.add(series)
    await db.flush()

    position = Position(
        time_series_id=series.id,
        holder_id=current_user.id,
        quantity_hours=series.quantity_hours,
    )
    db.add(position)

    return series


@series_router.get("/me", response_model=list[SeriesResponse])
async def my_series(
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TimeSeries).where(TimeSeries.issuer_id == current_user.id)
        .order_by(TimeSeries.emitted_at.desc())
    )
    return result.scalars().all()


@series_router.get("/issuer/{issuer_id}", response_model=list[SeriesResponse])
async def issuer_series(issuer_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(TimeSeries).where(TimeSeries.issuer_id == issuer_id)
        .order_by(TimeSeries.expires_at.asc())
    )
    return result.scalars().all()


@series_router.get("/{series_id}", response_model=SeriesResponse)
async def get_series(series_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TimeSeries).where(TimeSeries.id == series_id))
    series = result.scalar_one_or_none()
    if not series:
        raise HTTPException(status_code=404, detail="Série não encontrada")
    return series


# ─────────────────────────────────────────────
# POSITIONS
# ─────────────────────────────────────────────

positions_router = APIRouter(prefix="/positions", tags=["positions"])


@positions_router.get("/me", response_model=list[PositionResponse])
async def my_positions(
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Position).where(Position.holder_id == current_user.id)
    )
    return result.scalars().all()


@positions_router.get("/series/{series_id}", response_model=list[PositionResponse])
async def series_positions(series_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Position).where(Position.time_series_id == series_id)
    )
    return result.scalars().all()


# ─────────────────────────────────────────────
# ORDER BOOK
# ─────────────────────────────────────────────

orders_router = APIRouter(prefix="/orders", tags=["orders"])


@orders_router.post("", response_model=OrderResponse, status_code=201)
async def place_order(
    body: OrderCreate,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
):
    series_result = await db.execute(
        select(TimeSeries).where(TimeSeries.id == body.time_series_id)
    )
    series = series_result.scalar_one_or_none()
    if not series:
        raise HTTPException(status_code=404, detail="Série não encontrada")
    if series.status in (SeriesStatus.EXPIRED, SeriesStatus.LIQUIDATED):
        raise HTTPException(status_code=400, detail="Série não está disponível para negociação")

    if body.type == OrderType.ASK:
        position_result = await db.execute(
            select(Position).where(
                and_(
                    Position.time_series_id == body.time_series_id,
                    Position.holder_id == current_user.id,
                )
            )
        )
        position = position_result.scalar_one_or_none()
        if not position or position.quantity_hours < body.quantity_hours:
            raise HTTPException(status_code=400, detail="Posição insuficiente para vender")

    order = Order(user_id=current_user.id, **body.model_dump())
    db.add(order)
    await db.flush()

    await match_order(order, db)

    return order


@orders_router.delete("/{order_id}", status_code=204)
async def cancel_order(
    order_id: str,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Order).where(
            and_(Order.id == order_id, Order.user_id == current_user.id)
        )
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Ordem não encontrada")
    if order.status != OrderStatus.OPEN:
        raise HTTPException(status_code=400, detail="Ordem não pode ser cancelada")
    order.status = OrderStatus.CANCELLED


@orders_router.get("/series/{series_id}", response_model=OrderBookResponse)
async def get_order_book(series_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Order).where(
            and_(
                Order.time_series_id == series_id,
                Order.status == OrderStatus.OPEN,
            )
        ).order_by(Order.price_hour.desc())
    )
    orders = result.scalars().all()

    return OrderBookResponse(
        bids=[o for o in orders if o.type == OrderType.BID],
        asks=[o for o in orders if o.type == OrderType.ASK],
    )


@orders_router.get("/me", response_model=list[OrderResponse])
async def my_orders(
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Order).where(Order.user_id == current_user.id)
        .order_by(Order.created_at.desc())
    )
    return result.scalars().all()


# ─────────────────────────────────────────────
# TRANSACTIONS
# ─────────────────────────────────────────────

transactions_router = APIRouter(prefix="/transactions", tags=["transactions"])


@transactions_router.get("/series/{series_id}", response_model=list[TransactionResponse])
async def series_transactions(series_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Transaction)
        .where(Transaction.time_series_id == series_id)
        .order_by(Transaction.transacted_at.desc())
    )
    return [TransactionResponse.from_orm_obj(t) for t in result.scalars().all()]


@transactions_router.get("/me", response_model=list[TransactionResponse])
async def my_transactions(
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Transaction).where(
            (Transaction.from_user_id == current_user.id) |
            (Transaction.to_user_id == current_user.id)
        ).order_by(Transaction.transacted_at.desc())
    )
    return [TransactionResponse.from_orm_obj(t) for t in result.scalars().all()]


# ─────────────────────────────────────────────
# ROLLS
# ─────────────────────────────────────────────

rolls_router = APIRouter(prefix="/rolls", tags=["rolls"])


@rolls_router.get("/issuer/{issuer_id}", response_model=list[RollResponse])
async def issuer_rolls(issuer_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Roll)
        .where(Roll.issuer_id == issuer_id)
        .order_by(Roll.rolled_at.desc())
    )
    return result.scalars().all()


@rolls_router.get("/holder/me", response_model=list[RollResponse])
async def my_rolls(
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Roll)
        .where(Roll.holder_id == current_user.id)
        .order_by(Roll.rolled_at.desc())
    )
    return result.scalars().all()


@rolls_router.get("/series/{series_id}", response_model=list[RollResponse])
async def series_rolls(series_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Roll)
        .where(Roll.from_series_id == series_id)
        .order_by(Roll.rolled_at.desc())
    )
    return result.scalars().all()


# ─────────────────────────────────────────────
# MARKET
# ─────────────────────────────────────────────

market_router = APIRouter(prefix="/market", tags=["market"])


@market_router.get("/prices/{series_id}", response_model=MarketPriceResponse)
async def get_market_price(series_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(MarketPrice)
        .where(MarketPrice.time_series_id == series_id)
        .order_by(MarketPrice.recorded_at.desc())
        .limit(1)
    )
    mp = result.scalar_one_or_none()
    if not mp:
        raise HTTPException(status_code=404, detail="Sem preço de mercado para esta série")
    return mp


@market_router.get("/prices/issuer/{issuer_id}", response_model=list[MarketPriceResponse])
async def get_issuer_prices(issuer_id: str, db: AsyncSession = Depends(get_db)):
    series_result = await db.execute(
        select(TimeSeries.id).where(TimeSeries.issuer_id == issuer_id)
    )
    series_ids = [row[0] for row in series_result.all()]

    prices = []
    for sid in series_ids:
        result = await db.execute(
            select(MarketPrice)
            .where(MarketPrice.time_series_id == sid)
            .order_by(MarketPrice.recorded_at.desc())
            .limit(1)
        )
        mp = result.scalar_one_or_none()
        if mp:
            prices.append(mp)
    return prices


@market_router.get("/liability/{issuer_id}", response_model=LiabilityResponse)
async def get_issuer_liability(issuer_id: str, db: AsyncSession = Depends(get_db)):
    series_result = await db.execute(
        select(TimeSeries).where(
            and_(
                TimeSeries.issuer_id == issuer_id,
                TimeSeries.status == SeriesStatus.ACTIVE,
            )
        )
    )
    series_list = series_result.scalars().all()

    total = 0.0
    for series in series_list:
        pos_result = await db.execute(
            select(Position).where(
                and_(
                    Position.time_series_id == series.id,
                    Position.holder_id != issuer_id,
                )
            )
        )
        positions = pos_result.scalars().all()
        hours_in_circulation = sum(p.quantity_hours for p in positions)

        if series.repurchase_type == RepurchaseType.FIXED:
            total += hours_in_circulation * float(series.repurchase_price)
        else:
            mp_result = await db.execute(
                select(MarketPrice)
                .where(MarketPrice.time_series_id == series.id)
                .order_by(MarketPrice.recorded_at.desc())
                .limit(1)
            )
            mp = mp_result.scalar_one_or_none()
            if mp:
                total += hours_in_circulation * float(mp.last_price)

    return LiabilityResponse(issuer_id=issuer_id, total_liability=total)


@market_router.get("/honor/{issuer_id}", response_model=HonorScoreResponse)
async def get_honor_score(issuer_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(
            func.count(TimeSeries.id).filter(TimeSeries.status == SeriesStatus.LIQUIDATED).label("liquidated"),
            func.count(TimeSeries.id).filter(TimeSeries.status == SeriesStatus.EXPIRED).label("expired"),
        ).where(TimeSeries.issuer_id == issuer_id)
    )
    row = result.one()
    liquidated = row.liquidated or 0
    expired = row.expired or 0
    total = liquidated + expired
    score = round((liquidated / total) * 100, 2) if total > 0 else None

    return HonorScoreResponse(
        issuer_id=issuer_id,
        liquidated=liquidated,
        expired=expired,
        total_settled=total,
        honor_score=score,
    )


@market_router.get("/curve/{issuer_id}", response_model=YieldCurveResponse)
async def get_yield_curve(issuer_id: str, db: AsyncSession = Depends(get_db)):
    series_result = await db.execute(
        select(TimeSeries)
        .where(
            and_(
                TimeSeries.issuer_id == issuer_id,
                TimeSeries.status.in_([SeriesStatus.OPEN, SeriesStatus.ACTIVE]),
            )
        )
        .order_by(TimeSeries.expires_at.asc())
    )
    series_list = series_result.scalars().all()

    points = []
    for series in series_list:
        mp_result = await db.execute(
            select(MarketPrice)
            .where(MarketPrice.time_series_id == series.id)
            .order_by(MarketPrice.recorded_at.desc())
            .limit(1)
        )
        mp = mp_result.scalar_one_or_none()

        pos_result = await db.execute(
            select(func.sum(Position.quantity_hours))
            .where(
                and_(
                    Position.time_series_id == series.id,
                    Position.holder_id != issuer_id,
                )
            )
        )
        hours_in_circulation = pos_result.scalar() or 0

        points.append(YieldCurvePoint(
            series_id=series.id,
            expires_at=series.expires_at,
            last_price=float(mp.last_price) if mp else None,
            repurchase_type=series.repurchase_type,
            repurchase_price=float(series.repurchase_price) if series.repurchase_price else None,
            hours_in_circulation=hours_in_circulation,
            status=series.status,
        ))

    return YieldCurveResponse(issuer_id=issuer_id, points=points)


@market_router.get("/roll/{series_id}", response_model=RollCheckResponse)
async def check_roll_availability(series_id: str, db: AsyncSession = Depends(get_db)):
    series_result = await db.execute(select(TimeSeries).where(TimeSeries.id == series_id))
    series = series_result.scalar_one_or_none()
    if not series:
        raise HTTPException(status_code=404, detail="Série não encontrada")

    current_mp_result = await db.execute(
        select(MarketPrice)
        .where(MarketPrice.time_series_id == series_id)
        .order_by(MarketPrice.recorded_at.desc())
        .limit(1)
    )
    current_mp = current_mp_result.scalar_one_or_none()
    current_price = float(current_mp.last_price) if current_mp else None

    next_result = await db.execute(
        select(TimeSeries)
        .where(
            and_(
                TimeSeries.issuer_id == series.issuer_id,
                TimeSeries.expires_at > series.expires_at,
                TimeSeries.status.in_([SeriesStatus.OPEN, SeriesStatus.ACTIVE]),
            )
        )
        .order_by(TimeSeries.expires_at.asc())
        .limit(1)
    )
    next_series = next_result.scalar_one_or_none()

    if not next_series:
        return RollCheckResponse(
            series_id=series_id,
            expires_at=series.expires_at,
            roll_available=False,
            next_series_id=None,
            next_expires_at=None,
            next_last_price=None,
            roll_spread=None,
        )

    next_mp_result = await db.execute(
        select(MarketPrice)
        .where(MarketPrice.time_series_id == next_series.id)
        .order_by(MarketPrice.recorded_at.desc())
        .limit(1)
    )
    next_mp = next_mp_result.scalar_one_or_none()
    next_price = float(next_mp.last_price) if next_mp else None

    spread = round(next_price - current_price, 4) if (next_price and current_price) else None

    return RollCheckResponse(
        series_id=series_id,
        expires_at=series.expires_at,
        roll_available=True,
        next_series_id=next_series.id,
        next_expires_at=next_series.expires_at,
        next_last_price=next_price,
        roll_spread=spread,
    )


@market_router.get("/profile/{issuer_id}", response_model=EmitterProfileResponse)
async def get_emitter_profile(issuer_id: str, db: AsyncSession = Depends(get_db)):
    honor_result = await db.execute(
        select(
            func.count(TimeSeries.id).filter(TimeSeries.status == SeriesStatus.LIQUIDATED).label("liquidated"),
            func.count(TimeSeries.id).filter(TimeSeries.status == SeriesStatus.EXPIRED).label("expired"),
        ).where(TimeSeries.issuer_id == issuer_id)
    )
    honor_row = honor_result.one()
    liquidated = honor_row.liquidated or 0
    expired = honor_row.expired or 0
    total_settled = liquidated + expired
    honor_score = round((liquidated / total_settled) * 100, 2) if total_settled > 0 else None

    series_result = await db.execute(
        select(TimeSeries)
        .where(
            and_(
                TimeSeries.issuer_id == issuer_id,
                TimeSeries.status.in_([SeriesStatus.OPEN, SeriesStatus.ACTIVE]),
            )
        )
        .order_by(TimeSeries.expires_at.asc())
    )
    active_series = series_result.scalars().all()

    total_liability = 0.0
    hours_in_circulation = 0
    hours_own_portfolio = 0
    fixed_count = 0
    market_count = 0
    curve_points = []

    for series in active_series:
        if series.repurchase_type == RepurchaseType.FIXED:
            fixed_count += 1
        else:
            market_count += 1

        pos_result = await db.execute(
            select(Position).where(Position.time_series_id == series.id)
        )
        positions = pos_result.scalars().all()

        series_circulation = 0
        series_own = 0
        for p in positions:
            if p.holder_id == issuer_id:
                series_own += p.quantity_hours
            else:
                series_circulation += p.quantity_hours

        hours_in_circulation += series_circulation
        hours_own_portfolio += series_own

        mp_result = await db.execute(
            select(MarketPrice)
            .where(MarketPrice.time_series_id == series.id)
            .order_by(MarketPrice.recorded_at.desc())
            .limit(1)
        )
        mp = mp_result.scalar_one_or_none()
        last_price = float(mp.last_price) if mp else None

        if series.repurchase_type == RepurchaseType.FIXED:
            total_liability += series_circulation * float(series.repurchase_price)
        elif last_price:
            total_liability += series_circulation * last_price

        curve_points.append(YieldCurvePoint(
            series_id=series.id,
            expires_at=series.expires_at,
            last_price=last_price,
            repurchase_type=series.repurchase_type,
            repurchase_price=float(series.repurchase_price) if series.repurchase_price else None,
            hours_in_circulation=series_circulation,
            status=series.status,
        ))

    total_active = fixed_count + market_count
    emitting_continuously = len(active_series) > 1

    composition = EmitterComposition(
        total_series_active=total_active,
        fixed_series=fixed_count,
        market_series=market_count,
        fixed_pct=round((fixed_count / total_active) * 100, 2) if total_active > 0 else 0.0,
        market_pct=round((market_count / total_active) * 100, 2) if total_active > 0 else 0.0,
        hours_in_circulation=hours_in_circulation,
        hours_own_portfolio=hours_own_portfolio,
        emitting_continuously=emitting_continuously,
    )

    return EmitterProfileResponse(
        issuer_id=issuer_id,
        honor_score=honor_score,
        total_liability=round(total_liability, 2),
        composition=composition,
        yield_curve=curve_points,
    )
