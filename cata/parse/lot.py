from __future__ import annotations

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


def _seller(raw) -> Seller | None:
    if not raw:
        return None
    return Seller(
        id=raw.get("id") or raw.get("sellerId"),
        name=raw.get("shopName") or raw.get("name"),
        country=_country(raw.get("country")),
        score=raw.get("score"),
        review_count=raw.get("reviewCount") or raw.get("feedbackCount"),
    )


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
    slug = details.get("slug")
    return f"https://www.catawiki.com/en/l/{lot_id}" + (f"-{slug}" if slug else "")


def parse_lot(props: dict, currency: str = "EUR") -> LotDetail:
    details = props.get("lotDetailsData") or {}
    bidding = props.get("biddingBlockResponse") or {}
    category = details.get("category") if isinstance(details.get("category"), dict) else {}
    history = (bidding.get("biddingHistory") or {}).get("bids") or []

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
        category=category.get("title"),
        category_id=category.get("id"),
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
