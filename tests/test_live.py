import pytest

from cata.client import Client
from cata.fetch import Fetcher


def live_client():
    return Client(fetcher=Fetcher(cache_ttl=0))


@pytest.mark.network
def test_search_still_returns_parseable_data():
    page = live_client().search("omega speedmaster")
    assert page.total > 0
    assert page.lots
    assert page.lots[0].id


@pytest.mark.network
def test_lot_page_still_carries_bidding_block():
    client = live_client()
    page = client.search("omega speedmaster")
    detail = client.lot(page.lots[0].id)
    assert detail.title
    assert detail.bidding_end is not None
    assert detail.category_path


@pytest.mark.network
def test_categories_still_resolve():
    found = live_client().categories()
    assert len(found) > 10
    assert all(category["id"] and category["title"] for category in found)
