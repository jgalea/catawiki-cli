from __future__ import annotations

from ..models import Facet, Lot, SearchPage, epoch_ms, iso


def _when(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return epoch_ms(value)
    return iso(value)


def _lot(raw: dict) -> Lot:
    return Lot(
        id=raw["id"],
        title=raw.get("title") or "",
        subtitle=raw.get("subtitle"),
        url=raw.get("url"),
        image_url=raw.get("thumbImageUrl") or raw.get("originalImageUrl"),
        auction_id=raw.get("auctionId"),
        bidding_start=_when(raw.get("biddingStartTime")),
        bidding_end=_when(raw.get("biddingEndTime")),
        reserve_price_set=raw.get("reservePriceSet"),
        free_shipping=raw.get("hasFreeShipping"),
        favorite_count=raw.get("favoriteCount"),
        is_vector_result=bool(raw.get("isVectorSearchResult")),
    )


def _facet(raw: dict) -> Facet:
    options = tuple(
        (str(option.get("id") or option.get("value") or ""), option.get("name") or "")
        for option in (raw.get("options") or [])
    )
    return Facet(
        key=str(raw.get("key") or raw.get("id") or ""),
        name=raw.get("name") or "",
        options=options,
    )


def parse_search(props: dict) -> SearchPage:
    block = props.get("searchLots") or {}
    meta = block.get("meta") or {}
    return SearchPage(
        total=block.get("total") or 0,
        lots=tuple(_lot(raw) for raw in (block.get("lots") or []) if raw.get("id") is not None),
        facets=tuple(_facet(raw) for raw in (block.get("filters") or [])),
        extended=bool(meta.get("extended_search_result")),
    )
