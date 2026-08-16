from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode

from .errors import CataError
from .fetch import BASE, Fetcher
from .models import Lot, LotDetail, SearchPage
from .parse.categories import parse_categories
from .parse.lot import parse_lot
from .parse.next_data import extract
from .parse.search import parse_search

PER_PAGE = 24


class Client:
    def __init__(self, fetcher: Fetcher | None = None, locale: str = "en"):
        self.fetcher = fetcher or Fetcher()
        self.locale = locale

    def search_url(
        self,
        query: str,
        *,
        page: int = 1,
        category: int | None = None,
        sort: str | None = None,
        max_price: int | None = None,
        ending_in_days: int | None = None,
        no_reserve: bool = False,
    ) -> str:
        params: list[tuple[str, str]] = [("q", query)]
        if page > 1:
            params.append(("page", str(page)))
        if sort:
            params.append(("sort", sort))
        filters = []
        if max_price is not None:
            filters.append(f"budget[]=0-{max_price}")
        if ending_in_days is not None:
            filters.append(f"bidding_end_days[]={ending_in_days}")
        if no_reserve:
            filters.append("reserve_price[]=no_reserve")
        if category is not None:
            filters.append(f"l2_categories[]={category}")
        if filters:
            params.append(("filters", "&".join(filters)))
        return f"{BASE}/{self.locale}/s?{urlencode(params)}"

    def lot_url(self, lot_id: int) -> str:
        return f"{BASE}/{self.locale}/l/{lot_id}"

    def search(self, query: str, **kwargs) -> SearchPage:
        url = self.search_url(query, **kwargs)
        return parse_search(extract(self.fetcher.get(url), url))

    def search_all(self, query: str, *, limit: int = 48, fuzzy: bool = False, **kwargs) -> list[Lot]:
        """Page through a search.

        Catawiki never returns an empty result set: when nothing matches it falls back to
        semantic neighbours, and it mixes those into genuine result pages too. They are
        dropped unless fuzzy is set, so an unmatched query returns nothing rather than junk.
        """
        collected: list[Lot] = []
        seen = 0
        page = 1
        while len(collected) < limit:
            result = self.search(query, page=page, **kwargs)
            if not result.lots:
                break
            collected.extend(result.lots if fuzzy else result.matches)
            seen += len(result.lots)
            if seen >= result.total or len(result.lots) < PER_PAGE:
                break
            page += 1
        return collected[:limit]

    def lot(self, lot_id: int) -> LotDetail:
        url = self.lot_url(lot_id)
        return parse_lot(extract(self.fetcher.get(url, ttl=300), url))

    def details(self, lot_ids, *, concurrency: int = 4) -> dict[int, LotDetail]:
        def one(lot_id):
            try:
                return lot_id, self.lot(lot_id)
            except CataError:
                return lot_id, None

        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            return {
                lot_id: detail for lot_id, detail in pool.map(one, lot_ids) if detail is not None
            }

    def categories(self, category_id: int | None = None) -> list[dict]:
        url = f"{BASE}/{self.locale}" + (f"/c/{category_id}" if category_id else "")
        return parse_categories(extract(self.fetcher.get(url, ttl=86400), url))
