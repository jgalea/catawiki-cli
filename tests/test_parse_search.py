from cata.models import SearchPage
from cata.parse.search import parse_search


def test_parses_totals_and_lots(search_props):
    page = parse_search(search_props)
    assert isinstance(page, SearchPage)
    assert page.total > 0
    assert len(page.lots) > 0


def test_lot_fields_are_populated(search_props):
    lot = parse_search(search_props).lots[0]
    assert isinstance(lot.id, int)
    assert lot.title
    assert lot.url.startswith("https://www.catawiki.com/")
    assert lot.auction_id is not None


def test_facets_include_named_keys(search_props):
    keys = {f.key for f in parse_search(search_props).facets}
    assert "budget" in keys
    assert "bidding_end_days" in keys


def test_tolerates_missing_search_lots():
    page = parse_search({})
    assert page.total == 0
    assert page.lots == ()
