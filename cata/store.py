from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCHEMA_VERSION = 1

DEFAULT_DB = Path.home() / ".cata" / "cata.db"

SCHEMA = """
create table if not exists lots (
    id integer primary key,
    title text,
    subtitle text,
    url text,
    auction_id integer,
    category text,
    category_id integer,
    group_category_id integer,
    category_path_json text,
    seller_name text,
    seller_country text,
    specs_json text,
    first_seen text,
    bidding_start text,
    bidding_end text,
    reserve_price_set integer,
    is_closed integer default 0,
    sold integer,
    final_price integer,
    currency text,
    bid_count integer,
    detail_fetched_at text,
    outcome_recorded_at text,
    raw_json text
);

create table if not exists bid_snapshots (
    lot_id integer,
    observed_at text,
    current_bid integer,
    min_bid integer,
    reserve_met integer
);
create index if not exists idx_snapshots_lot on bid_snapshots(lot_id);

create table if not exists bids (
    lot_id integer,
    bid_id integer primary key,
    created_at text,
    amount integer,
    bidder_token text,
    bidder_name text,
    bidder_country text,
    bid_type text,
    bidder_total_bids integer
);
create index if not exists idx_bids_lot on bids(lot_id);

create table if not exists searches (
    id integer primary key autoincrement,
    name text unique,
    query text,
    filters_json text,
    created_at text,
    last_swept_at text
);

create table if not exists watches (
    lot_id integer primary key,
    max_bid integer,
    note text,
    alert_state text default '',
    created_at text
);

create table if not exists meta (
    key text primary key,
    value text
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iso(value) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None


class Store:
    def __init__(self, path: Path | str | None = None):
        self.path = Path(path or os.environ.get("CATA_DB") or DEFAULT_DB)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._migrate()

    def connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.path)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _migrate(self) -> None:
        conn = self.connect()
        conn.executescript(SCHEMA)
        conn.execute(
            "insert or replace into meta(key, value) values('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
        conn.commit()

    def upsert_lot(self, lot, *, detailed: bool = False) -> None:
        conn = self.connect()
        specs = getattr(lot, "specifications", ()) or ()
        seller = getattr(lot, "seller", None)
        auction = getattr(lot, "auction", None)
        reserve = getattr(lot, "reserve_price_set", None)
        raw = getattr(lot, "raw", None)
        conn.execute(
            """
            insert into lots (
                id, title, subtitle, url, auction_id, category, category_id,
                group_category_id, category_path_json,
                seller_name, seller_country, specs_json, first_seen,
                bidding_start, bidding_end, reserve_price_set, is_closed, currency,
                detail_fetched_at, raw_json
            ) values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            on conflict(id) do update set
                title=excluded.title,
                subtitle=coalesce(excluded.subtitle, lots.subtitle),
                url=coalesce(excluded.url, lots.url),
                auction_id=coalesce(excluded.auction_id, lots.auction_id),
                category=coalesce(excluded.category, lots.category),
                category_id=coalesce(excluded.category_id, lots.category_id),
                group_category_id=coalesce(excluded.group_category_id, lots.group_category_id),
                category_path_json=coalesce(excluded.category_path_json, lots.category_path_json),
                seller_name=coalesce(excluded.seller_name, lots.seller_name),
                seller_country=coalesce(excluded.seller_country, lots.seller_country),
                specs_json=coalesce(excluded.specs_json, lots.specs_json),
                bidding_start=coalesce(excluded.bidding_start, lots.bidding_start),
                bidding_end=coalesce(excluded.bidding_end, lots.bidding_end),
                reserve_price_set=coalesce(excluded.reserve_price_set, lots.reserve_price_set),
                is_closed=max(coalesce(excluded.is_closed, 0), coalesce(lots.is_closed, 0)),
                currency=coalesce(excluded.currency, lots.currency),
                detail_fetched_at=coalesce(excluded.detail_fetched_at, lots.detail_fetched_at),
                raw_json=coalesce(excluded.raw_json, lots.raw_json)
            """,
            (
                lot.id,
                lot.title,
                getattr(lot, "subtitle", None),
                getattr(lot, "url", None),
                getattr(lot, "auction_id", None) or (auction.id if auction else None),
                getattr(lot, "category", None),
                getattr(lot, "category_id", None),
                getattr(lot, "group_category_id", None),
                json.dumps([list(step) for step in getattr(lot, "category_path", ()) or ()]) or None
                if getattr(lot, "category_path", ())
                else None,
                seller.name if seller else None,
                seller.country if seller else None,
                json.dumps(
                    [
                        {
                            "name": spec.name,
                            "value": spec.value,
                            "sid": spec.specification_id,
                            "vid": spec.value_id,
                        }
                        for spec in specs
                    ]
                )
                if specs
                else None,
                _now(),
                _iso(getattr(lot, "bidding_start", None)),
                _iso(getattr(lot, "bidding_end", None)),
                int(reserve) if reserve is not None else None,
                int(bool(getattr(lot, "is_closed", False))),
                getattr(getattr(lot, "current_bid", None), "currency", None) or "EUR",
                _now() if detailed else None,
                json.dumps(raw) if raw else None,
            ),
        )
        conn.commit()

    def record_snapshot(self, detail) -> None:
        conn = self.connect()
        conn.execute(
            "insert into bid_snapshots (lot_id, observed_at, current_bid, min_bid, reserve_met)"
            " values (?,?,?,?,?)",
            (
                detail.id,
                _now(),
                detail.current_bid.amount if detail.current_bid else None,
                detail.min_bid.amount if detail.min_bid else None,
                None if detail.reserve_met is None else int(detail.reserve_met),
            ),
        )
        conn.commit()

    def record_bids(self, detail) -> None:
        conn = self.connect()
        conn.executemany(
            """
            insert into bids (lot_id, bid_id, created_at, amount, bidder_token, bidder_name,
                              bidder_country, bid_type, bidder_total_bids)
            values (?,?,?,?,?,?,?,?,?)
            on conflict(bid_id) do nothing
            """,
            [
                (
                    detail.id,
                    bid.id,
                    _iso(bid.created_at),
                    bid.amount.amount,
                    bid.bidder_token,
                    bid.bidder_name,
                    bid.bidder_country,
                    bid.bid_type,
                    bid.bidder_total_bids,
                )
                for bid in detail.bids
                if bid.id is not None
            ],
        )
        conn.commit()

    def record_outcome(self, detail) -> None:
        conn = self.connect()
        conn.execute(
            """
            update lots set is_closed=1, sold=?, final_price=?, currency=?, bid_count=?,
                            outcome_recorded_at=?, raw_json=coalesce(?, raw_json)
            where id=?
            """,
            (
                int(detail.sold),
                detail.current_bid.amount if (detail.sold and detail.current_bid) else None,
                detail.current_bid.currency if detail.current_bid else "EUR",
                len(detail.bids),
                _now(),
                json.dumps(detail.raw) if detail.raw else None,
                detail.id,
            ),
        )
        conn.commit()
        self.record_bids(detail)

    def lots_awaiting_outcome(self, now: datetime) -> list[int]:
        rows = self.connect().execute(
            """
            select id from lots
            where bidding_end is not null
              and bidding_end < ?
              and outcome_recorded_at is null
            order by bidding_end
            """,
            (now.isoformat(),),
        ).fetchall()
        return [row["id"] for row in rows]

    def lots_needing_detail(self, limit: int = 200) -> list[int]:
        rows = self.connect().execute(
            "select id from lots where detail_fetched_at is null"
            " and outcome_recorded_at is null order by first_seen desc limit ?",
            (limit,),
        ).fetchall()
        return [row["id"] for row in rows]

    def lots_needing_refresh(self, now: datetime, within_hours: int, limit: int = 100) -> list[int]:
        horizon = now.replace(microsecond=0) + timedelta(hours=within_hours)
        rows = self.connect().execute(
            """
            select id from lots
            where coalesce(is_closed, 0) = 0
              and detail_fetched_at is not null
              and bidding_end is not null
              and bidding_end between ? and ?
            order by bidding_end
            limit ?
            """,
            (now.isoformat(), horizon.isoformat(), limit),
        ).fetchall()
        return [row["id"] for row in rows]

    def add_search(self, name: str, query: str, filters: dict) -> int:
        conn = self.connect()
        conn.execute(
            """
            insert into searches (name, query, filters_json, created_at) values (?,?,?,?)
            on conflict(name) do update set query=excluded.query, filters_json=excluded.filters_json
            """,
            (name, query, json.dumps(filters or {}), _now()),
        )
        conn.commit()
        return conn.execute("select id from searches where name=?", (name,)).fetchone()["id"]

    def searches(self) -> list[sqlite3.Row]:
        return self.connect().execute("select * from searches order by id").fetchall()

    def remove_search(self, target) -> None:
        conn = self.connect()
        conn.execute("delete from searches where id=? or name=?", (target, str(target)))
        conn.commit()

    def touch_search(self, search_id: int, when: datetime) -> None:
        conn = self.connect()
        conn.execute(
            "update searches set last_swept_at=? where id=?", (when.isoformat(), search_id)
        )
        conn.commit()

    def add_watch(self, lot_id: int, max_bid: int | None = None, note: str | None = None) -> None:
        conn = self.connect()
        conn.execute(
            """
            insert into watches (lot_id, max_bid, note, created_at) values (?,?,?,?)
            on conflict(lot_id) do update set max_bid=excluded.max_bid, note=excluded.note
            """,
            (lot_id, max_bid, note, _now()),
        )
        conn.commit()

    def watches(self) -> list[sqlite3.Row]:
        return self.connect().execute(
            "select w.*, l.title, l.url, l.bidding_end from watches w"
            " left join lots l on l.id = w.lot_id order by l.bidding_end"
        ).fetchall()

    def remove_watch(self, lot_id: int) -> None:
        conn = self.connect()
        conn.execute("delete from watches where lot_id=?", (lot_id,))
        conn.commit()

    def set_alert_state(self, lot_id: int, state: str) -> None:
        conn = self.connect()
        conn.execute("update watches set alert_state=? where lot_id=?", (state, lot_id))
        conn.commit()

    def sold_lots(self, category_id: int | None = None) -> list[sqlite3.Row]:
        sql = "select * from lots where sold=1 and final_price is not null"
        params: tuple = ()
        if category_id is not None:
            sql += " and category_id=?"
            params = (category_id,)
        return self.connect().execute(sql, params).fetchall()
