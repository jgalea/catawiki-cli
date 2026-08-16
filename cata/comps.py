from __future__ import annotations

import json
import statistics
from dataclasses import dataclass

from .models import Money

MIN_SAMPLE = 8


@dataclass(frozen=True)
class CompsResult:
    basis: str
    sample_size: int
    median: Money | None = None
    p25: Money | None = None
    p75: Money | None = None
    low: Money | None = None
    high: Money | None = None
    sell_through: float | None = None
    first_seen: str | None = None
    last_seen: str | None = None
    sufficient: bool = False


def spec_value(row, name: str) -> str | None:
    try:
        specs = json.loads(row["specs_json"] or "[]")
    except (TypeError, json.JSONDecodeError):
        return None
    for spec in specs:
        if (spec.get("name") or "").lower() == name.lower():
            return spec.get("value")
    return None


def _quantile(values: list[int], q: float) -> int:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * q
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    weight = position - low
    return int(round(ordered[low] * (1 - weight) + ordered[high] * weight))


def _summarize(basis: str, rows) -> CompsResult:
    sold = [row for row in rows if row["sold"] == 1 and row["final_price"]]
    prices = [row["final_price"] for row in sold]
    currency = sold[0]["currency"] if sold else "EUR"
    sell_through = (len(sold) / len(rows)) if rows else None
    stamps = sorted(row["outcome_recorded_at"] for row in rows if row["outcome_recorded_at"])

    if len(prices) < MIN_SAMPLE:
        return CompsResult(
            basis=basis,
            sample_size=len(prices),
            sell_through=sell_through,
            first_seen=stamps[0] if stamps else None,
            last_seen=stamps[-1] if stamps else None,
            sufficient=False,
        )

    return CompsResult(
        basis=basis,
        sample_size=len(prices),
        median=Money(int(statistics.median(prices)), currency),
        p25=Money(_quantile(prices, 0.25), currency),
        p75=Money(_quantile(prices, 0.75), currency),
        low=Money(min(prices), currency),
        high=Money(max(prices), currency),
        sell_through=sell_through,
        first_seen=stamps[0] if stamps else None,
        last_seen=stamps[-1] if stamps else None,
        sufficient=True,
    )


def comparables(store, *, category_id=None, brand=None, model=None, title=None) -> CompsResult:
    rows = store.connect().execute(
        "select * from lots where is_closed=1 and outcome_recorded_at is not null"
        + (" and coalesce(group_category_id, category_id)=?" if category_id is not None else ""),
        (category_id,) if category_id is not None else (),
    ).fetchall()

    tiers = []
    if brand and model:
        tiers.append(
            (
                "category+brand+model",
                [
                    row
                    for row in rows
                    if spec_value(row, "Brand") == brand and spec_value(row, "Model") == model
                ],
            )
        )
    if brand:
        tiers.append(("category+brand", [row for row in rows if spec_value(row, "Brand") == brand]))
    if title:
        words = {word for word in title.lower().split() if len(word) > 3}
        tiers.append(
            (
                "category+title",
                [
                    row
                    for row in rows
                    if words and len(words & set((row["title"] or "").lower().split())) >= 2
                ],
            )
        )
    tiers.append(("category", rows))

    best = None
    for basis, subset in tiers:
        result = _summarize(basis, subset)
        if result.sufficient:
            return result
        if best is None or result.sample_size > best.sample_size:
            best = result
    return best or CompsResult(basis="category", sample_size=0)


def for_lot(store, detail) -> CompsResult:
    specs = {spec.name.lower(): spec.value for spec in detail.specifications}
    return comparables(
        store,
        category_id=detail.group_category_id or detail.category_id,
        brand=specs.get("brand"),
        model=specs.get("model"),
        title=detail.title,
    )
