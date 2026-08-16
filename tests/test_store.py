from datetime import timedelta

from cata.parse.lot import parse_lot
from cata.store import Store


def test_upsert_is_idempotent(tmp_path, lot_open_props):
    detail = parse_lot(lot_open_props)
    store = Store(tmp_path / "t.db")
    store.upsert_lot(detail)
    store.upsert_lot(detail)
    assert store.connect().execute("select count(*) c from lots").fetchone()["c"] == 1


def test_snapshots_accumulate(tmp_path, lot_open_props):
    detail = parse_lot(lot_open_props)
    store = Store(tmp_path / "t.db")
    store.upsert_lot(detail)
    store.record_snapshot(detail)
    store.record_snapshot(detail)
    assert store.connect().execute("select count(*) c from bid_snapshots").fetchone()["c"] == 2


def test_bids_are_deduplicated(tmp_path, lot_open_props):
    detail = parse_lot(lot_open_props)
    store = Store(tmp_path / "t.db")
    store.upsert_lot(detail)
    store.record_bids(detail)
    store.record_bids(detail)
    count = store.connect().execute("select count(*) c from bids").fetchone()["c"]
    assert count == len(detail.bids)


def test_outcome_marks_sold_with_price(tmp_path, lot_closed_props):
    detail = parse_lot(lot_closed_props)
    store = Store(tmp_path / "t.db")
    store.upsert_lot(detail)
    store.record_outcome(detail)
    row = store.connect().execute("select * from lots").fetchone()
    assert row["sold"] == 1
    assert row["final_price"] == detail.current_bid.amount


def test_lots_awaiting_outcome_only_returns_ended_open_lots(tmp_path, lot_open_props):
    detail = parse_lot(lot_open_props)
    store = Store(tmp_path / "t.db")
    store.upsert_lot(detail)
    assert store.lots_awaiting_outcome(detail.bidding_end - timedelta(days=1)) == []
    assert store.lots_awaiting_outcome(detail.bidding_end + timedelta(days=1)) == [detail.id]


def test_searches_round_trip(tmp_path):
    store = Store(tmp_path / "t.db")
    search_id = store.add_search("watches", "omega speedmaster", {"max_price": 2000})
    rows = store.searches()
    assert rows[0]["name"] == "watches"
    assert rows[0]["query"] == "omega speedmaster"
    store.remove_search(search_id)
    assert store.searches() == []


def test_watches_round_trip(tmp_path, lot_open_props):
    detail = parse_lot(lot_open_props)
    store = Store(tmp_path / "t.db")
    store.upsert_lot(detail)
    store.add_watch(detail.id, max_bid=90000, note="birthday")
    row = store.watches()[0]
    assert row["lot_id"] == detail.id
    assert row["max_bid"] == 90000
    store.remove_watch(detail.id)
    assert store.watches() == []
