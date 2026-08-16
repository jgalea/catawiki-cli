from __future__ import annotations

import re

from ..models import (
    Auction,
    Bid,
    LotDetail,
    Money,
    Seller,
    Specification,
    epoch_ms,
    iso,
)


def _money(value, currency: str) -> Money | None:
    return None if value is None else Money.from_major(value, currency)


def _specs(raw_list) -> tuple[Specification, ...]:
    return tuple(
        Specification(
            name=raw.get("name") or "",
            value=str(raw.get("value") or ""),
            specification_id=raw.get("specificationId"),
            value_id=raw.get("valueId"),
        )
        for raw in (raw_list or [])
        if raw.get("name")
    )


def _country(value):
    if isinstance(value, dict):
        return value.get("code")
    return value


def _seller_name(raw) -> str | None:
    for key in ("shopName", "name", "displayName"):
        if raw.get(key):
            return raw[key]
    match = re.search(r"/u/\d+-(.+)$", str(raw.get("url") or ""))
    return match.group(1) if match else None


def _seller(raw) -> Seller | None:
    if not raw:
        return None
    address = raw.get("address") or {}
    country = address.get("country") if isinstance(address, dict) else None
    score = raw.get("score") if isinstance(raw.get("score"), dict) else {}
    return Seller(
        id=raw.get("id") or raw.get("sellerId"),
        name=_seller_name(raw),
        country=(country or {}).get("shortCode") if isinstance(country, dict) else _country(raw.get("country")),
        score=score.get("score"),
        review_count=score.get("lifetimeCount") or raw.get("reviewCount"),
    )


def _category_path(auction_raw, leaf_raw) -> tuple[tuple[int, str], ...]:
    path = [
        (category["id"], category.get("title") or "")
        for category in ((auction_raw or {}).get("categories") or [])
        if isinstance(category.get("id"), int)
    ]
    if path:
        return tuple(path)
    leaf_id = (leaf_raw or {}).get("id")
    if not isinstance(leaf_id, int):
        return ()
    match = re.search(r"/c/\d+-(.+)$", str((leaf_raw or {}).get("url") or ""))
    title = match.group(1).replace("-", " ").title() if match else ""
    return ((leaf_id, title),)


def _auction(raw) -> Auction | None:
    if not raw:
        return None
    return Auction(
        id=raw.get("id"),
        title=raw.get("title"),
        url=raw.get("url"),
        status=raw.get("status"),
    )


def _bid(raw, currency: str) -> Bid:
    return Bid(
        id=raw.get("id"),
        amount=Money.from_major(raw.get("localizedBidAmount") or 0, currency),
        created_at=iso(raw.get("createdAt")),
        bidder_token=raw.get("bidderToken"),
        bidder_name=raw.get("bidderName"),
        bidder_country=_country(raw.get("country")),
        bid_type=raw.get("bidType") or None,
        bidder_total_bids=raw.get("totalBids"),
    )


def _url(props: dict, details: dict) -> str | None:
    lot_id = props.get("lotId") or details.get("lotId")
    if not lot_id:
        return None
    slug = str(details.get("slug") or "")
    if slug.startswith(f"{lot_id}-"):
        return f"https://www.catawiki.com/en/l/{slug}"
    return f"https://www.catawiki.com/en/l/{lot_id}" + (f"-{slug}" if slug else "")


def parse_lot(props: dict, currency: str = "EUR") -> LotDetail:
    details = props.get("lotDetailsData") or {}
    bidding = props.get("biddingBlockResponse") or {}
    leaf = details.get("category") if isinstance(details.get("category"), dict) else {}
    path = _category_path(props.get("auction"), leaf)
    history = (bidding.get("biddingHistory") or {}).get("bids") or []

    category_id = leaf.get("id") or (path[-1][0] if path else None)
    group_category_id = path[1][0] if len(path) > 1 else (path[0][0] if path else category_id)
    category_title = next((title for cid, title in path if cid == category_id), None)
    if not category_title and path:
        category_title = path[-1][1]

    bids = sorted(
        (_bid(raw, currency) for raw in history),
        key=lambda bid: (bid.created_at is not None, bid.created_at),
        reverse=True,
    )

    return LotDetail(
        id=props.get("lotId") or details.get("lotId"),
        title=details.get("lotTitle") or "",
        subtitle=details.get("lotSubtitle"),
        description=details.get("description"),
        url=(details.get("seo") or {}).get("canonicalUrl") or _url(props, details),
        auction=_auction(props.get("auction")),
        seller=_seller(details.get("sellerInfo")),
        category=category_title,
        category_id=category_id,
        group_category_id=group_category_id,
        category_path=path,
        specifications=_specs(details.get("specifications")),
        current_bid=_money(bidding.get("localizedCurrentBidAmount"), currency),
        min_bid=_money(bidding.get("localizedMinBidAmount"), currency),
        start_bid=_money(bidding.get("localizedStartBidAmount"), currency),
        bidding_start=epoch_ms(bidding.get("biddingStartTime")),
        bidding_end=epoch_ms(bidding.get("biddingEndTime")),
        is_closed=bool(details.get("isClosed") or bidding.get("closed")),
        sold=bool(bidding.get("sold")),
        reserve_price_set=details.get("reservePriceSet"),
        reserve_met=bidding.get("reservePriceMet"),
        favorite_count=details.get("favoriteCount"),
        bids=tuple(bids),
        raw={"lotDetailsData": details, "biddingBlockResponse": bidding},
    )
