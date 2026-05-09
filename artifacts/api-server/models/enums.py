import enum


class RepurchaseType(str, enum.Enum):
    FIXED = "FIXED"
    MARKET = "MARKET"


class SeriesStatus(str, enum.Enum):
    OPEN = "OPEN"
    ACTIVE = "ACTIVE"
    LIQUIDATED = "LIQUIDATED"
    EXPIRED = "EXPIRED"


class OrderType(str, enum.Enum):
    BID = "BID"
    ASK = "ASK"


class OrderStatus(str, enum.Enum):
    OPEN = "OPEN"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"


class PaymentMode(str, enum.Enum):
    MONEY = "MONEY"
    CONTRACT = "CONTRACT"
    BOTH = "BOTH"


class PaymentPriceType(str, enum.Enum):
    FIXED = "FIXED"
    MARKET = "MARKET"


class TransactionType(str, enum.Enum):
    PRIMARY = "PRIMARY"
    SECONDARY = "SECONDARY"
    LIQUIDATION = "LIQUIDATION"
