import pytest

from cata.errors import ParseError
from cata.models import Money
from cata.parse.next_data import extract

HTML = (
    '<html><body><script id="__NEXT_DATA__" type="application/json">'
    '{"props":{"pageProps":{"lotId":42}}}</script></body></html>'
)


def test_extract_returns_page_props():
    assert extract(HTML, "https://x") == {"lotId": 42}


def test_missing_blob_raises_parse_error():
    with pytest.raises(ParseError):
        extract("<html></html>", "https://x")


def test_money_from_major():
    assert Money.from_major(850, "EUR") == Money(85000, "EUR")


def test_money_renders_with_symbol():
    assert str(Money(85000, "EUR")) == "€850"


def test_money_renders_cents_when_present():
    assert str(Money(85050, "EUR")) == "€850.50"
