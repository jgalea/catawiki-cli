from datetime import datetime, timedelta, timezone

from cata.errors import NotFound
from cata.harvest import close_out, sweep
from cata.models import Lot
from cata.parse.lot import parse_lot
from cata.store import Store


class FakeClient:
    def __init__(self, lots, details=None):
        self._lots = lots
        self._details = details or {}
        self.searched = []

    def search_all(self, query, **kwargs):
        self.searched.append(query)
        return self._lots

    def lot(self, lot_id):
        if lot_id not in self._details:
            raise NotFound(f"https://www.catawiki.com/en/l/{lot_id}")
        return self._details[lot_id]


def _lot(lot_id):
    return Lot(id=lot_id, title=f"lot {lot_id}", url=f"https://www.catawiki.com/en/l/{lot_id}")


def test_sweep_stores_lots_from_saved_searches(tmp_path, lot_open_props):
    detail = parse_lot(lot_open_props)
    store = Store(tmp_path / "t.db")
    store.add_search("watches", "omega", {})
    client = FakeClient([_lot(detail.id), _lot(2)], {detail.id: detail})
    report = sweep(client, store)
    assert report.searches == 1
    assert report.lots_seen == 2
    assert report.lots_new == 2
    assert client.searched == ["omega"]


def test_sweep_counts_new_versus_seen(tmp_path, lot_open_props):
    detail = parse_lot(lot_open_props)
    store = Store(tmp_path / "t.db")
    store.add_search("watches", "omega", {})
    client = FakeClient([_lot(detail.id)], {detail.id: detail})
    sweep(client, store)
    assert sweep(client, store).lots_new == 0


def test_sweep_enriches_new_lots_with_detail_fields(tmp_path, lot_open_props):
    detail = parse_lot(lot_open_props)
    store = Store(tmp_path / "t.db")
    store.add_search("watches", "omega", {})
    client = FakeClient([_lot(detail.id)], {detail.id: detail})
    report = sweep(client, store)
    assert report.enriched == 1
    row = store.connect().execute("select * from lots where id=?", (detail.id,)).fetchone()
    assert row["bidding_end"] is not None
    assert row["specs_json"] is not None
    assert row["group_category_id"] is not None
    assert row["detail_fetched_at"] is not None


def test_sweep_does_not_re_enrich_on_the_next_run(tmp_path, lot_open_props):
    detail = parse_lot(lot_open_props)
    store = Store(tmp_path / "t.db")
    store.add_search("watches", "omega", {})
    client = FakeClient([_lot(detail.id)], {detail.id: detail})
    sweep(client, store)
    assert sweep(client, store).enriched == 0


def test_sweep_survives_a_failed_detail_fetch(tmp_path):
    store = Store(tmp_path / "t.db")
    store.add_search("watches", "omega", {})
    client = FakeClient([_lot(1)])
    report = sweep(client, store)
    assert report.lots_new == 1
    assert report.failed == 1
    assert report.enriched == 0


def test_close_out_records_sold_price(tmp_path, lot_closed_props):
    closed = parse_lot(lot_closed_props)
    store = Store(tmp_path / "t.db")
    store.upsert_lot(closed)
    ended = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    store.connect().execute(
        "update lots set outcome_recorded_at=null, is_closed=0, bidding_end=? where id=?",
        (ended, closed.id),
    )
    store.connect().commit()
    client = FakeClient([], {closed.id: closed})
    report = close_out(client, store)
    assert report.checked == 1
    assert report.sold == 1
    row = store.connect().execute("select * from lots where id=?", (closed.id,)).fetchone()
    assert row["final_price"] == closed.current_bid.amount


def test_close_out_skips_lots_still_open(tmp_path, lot_open_props):
    detail = parse_lot(lot_open_props)
    store = Store(tmp_path / "t.db")
    store.upsert_lot(detail)
    client = FakeClient([], {detail.id: detail})
    report = close_out(client, store, now=detail.bidding_end - timedelta(days=1))
    assert report.checked == 0
