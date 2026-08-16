from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

SYMBOLS = {"EUR": "€", "GBP": "£", "USD": "$"}


@dataclass(frozen=True)
class Money:
    amount: int
    currency: str

    @classmethod
    def from_major(cls, value, currency: str) -> "Money":
        return cls(int(round(float(value) * 100)), currency)

    @property
    def major(self) -> float:
        return self.amount / 100

    def __str__(self) -> str:
        symbol = SYMBOLS.get(self.currency, self.currency + " ")
        whole, cents = divmod(self.amount, 100)
        return f"{symbol}{whole}" if cents == 0 else f"{symbol}{whole}.{cents:02d}"


def epoch_ms(value) -> datetime | None:
    if value is None:
        return None
    return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)


def iso(value) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


@dataclass(frozen=True)
class Specification:
    name: str
    value: str
    specification_id: int | None = None
    value_id: int | None = None


@dataclass(frozen=True)
class Seller:
    id: int | None = None
    name: str | None = None
    country: str | None = None
    score: float | None = None
    review_count: int | None = None


@dataclass(frozen=True)
class Auction:
    id: int | None
    title: str | None = None
    url: str | None = None
    status: str | None = None


@dataclass(frozen=True)
class Bid:
    id: int | None
    amount: Money
    created_at: datetime | None
    bidder_token: str | None
    bidder_name: str | None
    bidder_country: str | None
    bid_type: str | None
    bidder_total_bids: int | None


@dataclass(frozen=True)
class Lot:
    id: int
    title: str
    subtitle: str | None = None
    url: str | None = None
    image_url: str | None = None
    auction_id: int | None = None
    bidding_start: datetime | None = None
    bidding_end: datetime | None = None
    reserve_price_set: bool | None = None
    free_shipping: bool | None = None
    favorite_count: int | None = None


@dataclass(frozen=True)
class LotDetail:
    id: int
    title: str
    subtitle: str | None = None
    description: str | None = None
    url: str | None = None
    auction: Auction | None = None
    seller: Seller | None = None
    category: str | None = None
    category_id: int | None = None
    group_category_id: int | None = None
    category_path: tuple[tuple[int, str], ...] = ()
    specifications: tuple[Specification, ...] = ()
    current_bid: Money | None = None
    min_bid: Money | None = None
    start_bid: Money | None = None
    bidding_start: datetime | None = None
    bidding_end: datetime | None = None
    is_closed: bool = False
    sold: bool = False
    reserve_price_set: bool | None = None
    reserve_met: bool | None = None
    favorite_count: int | None = None
    bids: tuple[Bid, ...] = ()
    raw: dict = field(default_factory=dict, compare=False, repr=False)


@dataclass(frozen=True)
class Facet:
    key: str
    name: str
    options: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class SearchPage:
    total: int
    lots: tuple[Lot, ...]
    facets: tuple[Facet, ...] = ()
