import json

from cata.client import Client
from cata.matching import matches_pattern
from cata.models import Lot, Specification
from cata.parse.search import parse_search


def _page(lots, total=24, extended=False):
    return {
        "searchLots": {
            "total": total,
            "lots": lots,
            "filters": [],
            "meta": {"extended_search_result": extended},
        }
    }


def test_parses_the_vector_flag():
    page = parse_search(
        _page(
            [
                {"id": 1, "title": "real hit", "isVectorSearchResult": False},
                {"id": 2, "title": "toy helicopter", "isVectorSearchResult": True},
            ]
        )
    )
    assert page.lots[0].is_vector_result is False
    assert page.lots[1].is_vector_result is True


def test_matches_drops_the_semantic_fallback():
    page = parse_search(
        _page(
            [
                {"id": 1, "title": "real hit", "isVectorSearchResult": False},
                {"id": 2, "title": "toy helicopter", "isVectorSearchResult": True},
            ]
        )
    )
    assert [lot.id for lot in page.matches] == [1]


def test_extended_flag_is_parsed():
    assert parse_search(_page([], extended=True)).extended is True
    assert parse_search(_page([])).extended is False


class StubFetcher:
    def __init__(self, props):
        self.body = (
            '<script id="__NEXT_DATA__" type="application/json">'
            + json.dumps({"props": {"pageProps": props}})
            + "</script>"
        )

    def get(self, url, **kwargs):
        return self.body


def test_search_all_returns_nothing_when_every_result_is_fallback():
    props = _page(
        [{"id": i, "title": "junk", "isVectorSearchResult": True} for i in range(24)],
        extended=True,
    )
    assert Client(fetcher=StubFetcher(props)).search_all("herman miller aeron", limit=24) == []


def test_search_all_keeps_fallback_when_asked():
    props = _page(
        [{"id": i, "title": "junk", "isVectorSearchResult": True} for i in range(24)],
        extended=True,
    )
    lots = Client(fetcher=StubFetcher(props)).search_all("aeron", limit=24, fuzzy=True)
    assert len(lots) == 24


def test_search_all_keeps_real_hits_mixed_into_a_fallback_page():
    lots = [{"id": i, "title": "junk", "isVectorSearchResult": True} for i in range(15)]
    lots += [{"id": 100 + i, "title": "Herman Miller chair", "isVectorSearchResult": False} for i in range(9)]
    result = Client(fetcher=StubFetcher(_page(lots))).search_all("herman miller", limit=24)
    assert len(result) == 9
    assert all(lot.id >= 100 for lot in result)


def test_pattern_matches_the_title():
    lot = Lot(id=1, title="Herman Miller - Aeron - Office chair")
    assert matches_pattern(lot, "aeron") is True


def test_pattern_is_case_insensitive():
    lot = Lot(id=1, title="HERMAN MILLER AERON")
    assert matches_pattern(lot, "aeron") is True


def test_pattern_rejects_a_non_match():
    lot = Lot(id=1, title="Herman Miller - Celle - Office chair")
    assert matches_pattern(lot, "aeron") is False


def test_pattern_matches_a_specification_value():
    detail = Lot(id=1, title="Office chair")
    assert matches_pattern(detail, "aeron", specs=(Specification(name="Model", value="Aeron"),)) is True


def test_empty_pattern_matches_everything():
    assert matches_pattern(Lot(id=1, title="anything"), None) is True
    assert matches_pattern(Lot(id=1, title="anything"), "") is True
