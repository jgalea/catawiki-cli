import json

from cata.client import Client


class StubFetcher:
    def __init__(self, body):
        self.body = body
        self.urls = []

    def get(self, url, **kwargs):
        self.urls.append(url)
        return self.body


def _html(props):
    payload = json.dumps({"props": {"pageProps": props}})
    return '<script id="__NEXT_DATA__" type="application/json">' + payload + "</script>"


def test_search_url_carries_query_and_page():
    client = Client(fetcher=StubFetcher(""))
    url = client.search_url("omega speedmaster", page=2)
    assert "q=omega+speedmaster" in url
    assert "page=2" in url


def test_search_url_applies_filters():
    client = Client(fetcher=StubFetcher(""))
    url = client.search_url("rolex", max_price=500, no_reserve=True, ending_in_days=1)
    assert "budget" in url
    assert "reserve_price" in url
    assert "bidding_end_days" in url


def test_lot_url_uses_lot_path():
    client = Client(fetcher=StubFetcher(""))
    assert client.lot_url(123) == "https://www.catawiki.com/en/l/123"


def test_search_parses_through_the_fetcher(search_props):
    fetcher = StubFetcher(_html(search_props))
    page = Client(fetcher=fetcher).search("omega")
    assert page.total > 0
    assert fetcher.urls


def test_search_all_stops_at_limit(search_props):
    fetcher = StubFetcher(_html(search_props))
    lots = Client(fetcher=fetcher).search_all("omega", limit=5)
    assert len(lots) == 5
