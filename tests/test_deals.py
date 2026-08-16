import json
from datetime import datetime, timedelta, timezone

from cata.comps import MIN_SAMPLE
from cata.deals import scan
from cata.store import Store

SPECS = json.dumps([{"name": "Brand", "value": "Omega", "sid": 909, "vid": 1}])


def _sold(store, lot_id, price):
    store.connect().execute(
        """
        insert into lots (id, title, category_id, specs_json, sold, final_price, currency,
                          is_closed, outcome_recorded_at)
        values (?,?,333,?,1,?, 'EUR', 1, '2026-08-01T00:00:00+00:00')
        """,
        (lot_id, f"Omega lot {lot_id}", SPECS, price),
    )
    store.connect().commit()


def _open(store, lot_id, ends_in_hours, current_bid=20000):
    end = datetime.now(timezone.utc) + timedelta(hours=ends_in_hours)
    store.connect().execute(
        """
        insert into lots (id, title, category_id, specs_json, is_closed, bidding_end, currency)
        values (?,?,333,?,0,?, 'EUR')
        """,
        (lot_id, f"Omega lot {lot_id}", SPECS, end.isoformat()),
    )
    store.connect().execute(
        "insert into bid_snapshots (lot_id, observed_at, current_bid) values (?,?,?)",
        (lot_id, datetime.now(timezone.utc).isoformat(), current_bid),
    )
    store.connect().commit()


def test_finds_lot_well_below_comps(tmp_path):
    store = Store(tmp_path / "t.db")
    for i in range(MIN_SAMPLE):
        _sold(store, i + 1, 100000)
    _open(store, 500, ends_in_hours=6)
    deals = scan(store, ending_within_hours=12, min_discount=0.3)
    assert len(deals) == 1
    assert deals[0].lot_id == 500
    assert deals[0].discount > 0.7


def test_ignores_lots_ending_outside_the_window(tmp_path):
    store = Store(tmp_path / "t.db")
    for i in range(MIN_SAMPLE):
        _sold(store, i + 1, 100000)
    _open(store, 500, ends_in_hours=48)
    assert scan(store, ending_within_hours=12) == []


def test_ignores_lots_without_enough_comps(tmp_path):
    store = Store(tmp_path / "t.db")
    _sold(store, 1, 100000)
    _open(store, 500, ends_in_hours=6)
    assert scan(store, ending_within_hours=12) == []


def test_respects_min_discount(tmp_path):
    store = Store(tmp_path / "t.db")
    for i in range(MIN_SAMPLE):
        _sold(store, i + 1, 22000)
    _open(store, 500, ends_in_hours=6)
    assert scan(store, ending_within_hours=12, min_discount=0.5) == []
