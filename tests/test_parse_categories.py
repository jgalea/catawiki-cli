from cata.parse.categories import parse_categories


def test_finds_categories_by_name_key():
    props = {
        "categoriesOrderedNameAsc": [
            {"id": 85, "name": "Art", "url": "https://www.catawiki.com/en/c/85-art"},
            {"id": 333, "name": "Watches", "url": "https://www.catawiki.com/en/c/333-watches"},
        ]
    }
    found = parse_categories(props)
    assert [c["id"] for c in found] == [85, 333]
    assert found[0]["title"] == "Art"


def test_finds_categories_by_title_key():
    props = {"auction": {"categories": [{"id": 299, "title": "Watches, Pens & Lighters", "url": "https://www.catawiki.com/en/c/299-watches-pens-lighters"}]}}
    assert parse_categories(props)[0]["title"] == "Watches, Pens & Lighters"


def test_ignores_nodes_without_a_category_url():
    props = {"lot": {"id": 12, "name": "not a category", "url": "https://www.catawiki.com/en/l/12-thing"}}
    assert parse_categories(props) == []


def test_deduplicates_repeated_categories():
    entry = {"id": 85, "name": "Art", "url": "https://www.catawiki.com/en/c/85-art"}
    assert len(parse_categories({"a": [entry], "b": {"c": entry}})) == 1


def test_finds_categories_on_a_real_lot_page(lot_open_props):
    found = parse_categories(lot_open_props)
    assert any(category["id"] == 333 for category in found)
