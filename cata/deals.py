from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .comps import comparables, spec_value
from .models import Money


@dataclass(frozen=True)
class Deal:
    lot_id: int
    title: str
    url: str | None
    current_bid: Money
    comp_median: Money
    discount: float
    sample_size: int
    basis: str
    bidding_end: datetime | None


def _latest_bid(store, lot_id: int) -> int | None:
    row = store.connect().execute(
        "select current_bid from bid_snapshots where lot_id=? order by observed_at desc limit 1",
        (lot_id,),
    ).fetchone()
    return row["current_bid"] if row else None


def scan(store, *, ending_within_hours: int = 12, min_discount: float = 0.3, now=None) -> list[Deal]:
    now = now or datetime.now(timezone.utc)
    horizon = now + timedelta(hours=ending_within_hours)
    rows = store.connect().execute(
        """
        select * from lots
        where coalesce(is_closed, 0) = 0
          and bidding_end is not null
          and bidding_end between ? and ?
        order by bidding_end
        """,
        (now.isoformat(), horizon.isoformat()),
    ).fetchall()

    deals: list[Deal] = []
    for row in rows:
        current = _latest_bid(store, row["id"])
        if current is None:
            continue
        result = comparables(
            store,
            category_id=row["group_category_id"] or row["category_id"],
            brand=spec_value(row, "Brand"),
            model=spec_value(row, "Model"),
            title=row["title"],
        )
        if not result.sufficient or not result.median or result.median.amount <= 0:
            continue
        discount = 1 - (current / result.median.amount)
        if discount < min_discount:
            continue
        deals.append(
            Deal(
                lot_id=row["id"],
                title=row["title"] or "",
                url=row["url"],
                current_bid=Money(current, row["currency"] or "EUR"),
                comp_median=result.median,
                discount=discount,
                sample_size=result.sample_size,
                basis=result.basis,
                bidding_end=datetime.fromisoformat(row["bidding_end"]),
            )
        )
    return sorted(deals, key=lambda deal: deal.discount, reverse=True)
