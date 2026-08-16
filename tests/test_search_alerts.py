from cata.errors import NotFound
from cata.harvest import pending_alerts, sweep
from cata.models import Lot
from cata.store import Store


class FakeClient:
    def __init__(self, lots):
        self._lots = lots

    def search_all(self, query, **kwargs):
        return self._lots

    def lot(self, lot_id):
        # These tests exercise search matching, not enrichment; sweep tolerates a
        # failed detail fetch and moves on.
        raise NotFound(f"https://www.catawiki.com/en/l/{lot_id}")


def _lot(lot_id, title):
    return Lot(id=lot_id, title=title, url=f"https://www.catawiki.com/en/l/{lot_id}")


AERON = _lot(1, "Herman Miller - Aeron - Office chair - Size B")
CELLE = _lot(2, "Herman Miller - Celle - Office chair")


def test_match_pattern_limits_hits(tmp_path):
    store = Store(tmp_path / "t.db")
    store.add_search("aeron", "herman miller", {}, match_pattern="aeron", notify="macos")
    report = sweep(FakeClient([AERON, CELLE]), store)
    assert report.lots_seen == 2
    assert report.matched == 1


def test_search_without_a_pattern_matches_everything(tmp_path):
    store = Store(tmp_path / "t.db")
    store.add_search("all", "herman miller", {})
    assert sweep(FakeClient([AERON, CELLE]), store).matched == 2


def test_alert_is_owed_once_then_never_again(tmp_path):
    store = Store(tmp_path / "t.db")
    store.add_search("aeron", "herman miller", {}, match_pattern="aeron", notify="macos")
    sweep(FakeClient([AERON, CELLE]), store)

    batches = pending_alerts(store)
    assert len(batches) == 1
    assert [alert.lot_id for alert in batches[0].alerts] == [1]
    assert batches[0].sinks == ["macos"]
    assert batches[0].alerts[0].kind == "new_lot"

    for alert in batches[0].alerts:
        store.mark_alerted(batches[0].search_id, alert.lot_id)

    assert pending_alerts(store) == []
    sweep(FakeClient([AERON, CELLE]), store)
    assert pending_alerts(store) == []


def test_a_second_matching_lot_fires_its_own_alert(tmp_path):
    store = Store(tmp_path / "t.db")
    store.add_search("aeron", "herman miller", {}, match_pattern="aeron", notify="macos")
    sweep(FakeClient([AERON]), store)
    for batch in pending_alerts(store):
        for alert in batch.alerts:
            store.mark_alerted(batch.search_id, alert.lot_id)

    later = _lot(3, "Herman Miller - Aeron Remastered - Office chair")
    sweep(FakeClient([AERON, later]), store)
    batches = pending_alerts(store)
    assert [alert.lot_id for alert in batches[0].alerts] == [3]


def test_notify_none_suppresses_alerts(tmp_path):
    store = Store(tmp_path / "t.db")
    store.add_search("aeron", "herman miller", {}, match_pattern="aeron", notify="none")
    sweep(FakeClient([AERON]), store)
    assert pending_alerts(store) == []


def test_alert_message_carries_the_lot_url(tmp_path):
    store = Store(tmp_path / "t.db")
    store.add_search("aeron", "herman miller", {}, match_pattern="aeron")
    sweep(FakeClient([AERON]), store)
    assert "catawiki.com/en/l/1" in pending_alerts(store)[0].alerts[0].message


def test_migration_adds_columns_to_an_older_database(tmp_path):
    import sqlite3

    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        "create table searches (id integer primary key autoincrement, name text unique,"
        " query text, filters_json text, created_at text, last_swept_at text);"
        "create table lots (id integer primary key, title text);"
    )
    conn.execute("insert into searches (name, query) values ('old', 'omega')")
    conn.commit()
    conn.close()

    store = Store(path)
    columns = {row["name"] for row in store.connect().execute("pragma table_info(searches)")}
    assert {"match_pattern", "notify"} <= columns
    assert store.searches()[0]["name"] == "old"
