from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .errors import CataError
from .matching import matches_pattern

REFRESH_WINDOW_HOURS = 48


@dataclass
class SweepReport:
    searches: int = 0
    lots_seen: int = 0
    lots_new: int = 0
    enriched: int = 0
    refreshed: int = 0
    matched: int = 0
    failed: int = 0


@dataclass
class CloseOutReport:
    checked: int = 0
    sold: int = 0
    unsold: int = 0
    still_open: int = 0
    failed: int = 0


def _known(store, lot_id: int) -> bool:
    return store.connect().execute("select 1 from lots where id=?", (lot_id,)).fetchone() is not None


def _pull_detail(client, store, lot_id: int):
    detail = client.lot(lot_id)
    store.upsert_lot(detail, detailed=True)
    store.record_snapshot(detail)
    store.record_bids(detail)
    if detail.is_closed:
        store.record_outcome(detail)
    return detail


def sweep(
    client,
    store,
    *,
    now: datetime | None = None,
    limit: int = 96,
    enrich_limit: int = 200,
    refresh_limit: int = 100,
) -> SweepReport:
    """Page saved searches, then fill in the detail-only fields the search payload lacks.

    Search results carry neither a closing time nor specifications, so every lot needs one
    lot-page fetch before it can be closed out or used as a comparable.
    """
    now = now or datetime.now(timezone.utc)
    report = SweepReport()

    for search in store.searches():
        filters = json.loads(search["filters_json"] or "{}")
        try:
            lots = client.search_all(search["query"], limit=limit, **filters)
        except CataError:
            report.failed += 1
            continue
        report.searches += 1
        pattern = search["match_pattern"]
        for lot in lots:
            report.lots_seen += 1
            if not _known(store, lot.id):
                report.lots_new += 1
            store.upsert_lot(lot)
            if matches_pattern(lot, pattern) and store.record_hit(search["id"], lot.id):
                report.matched += 1
        store.touch_search(search["id"], now)

    for lot_id in store.lots_needing_detail(enrich_limit):
        try:
            _pull_detail(client, store, lot_id)
            report.enriched += 1
        except CataError:
            report.failed += 1

    for lot_id in store.lots_needing_refresh(now, REFRESH_WINDOW_HOURS, refresh_limit):
        try:
            _pull_detail(client, store, lot_id)
            report.refreshed += 1
        except CataError:
            report.failed += 1

    return report


@dataclass
class AlertBatch:
    search_id: int
    search_name: str
    sinks: list[str]
    alerts: list


def pending_alerts(store, default_sinks: str = "macos") -> list[AlertBatch]:
    """New-lot alerts owed per saved search. Hits are marked only after a successful send."""
    from .alerts import Alert

    batches: list[AlertBatch] = []
    for search in store.searches():
        lot_ids = store.unalerted_hits(search["id"])
        if not lot_ids:
            continue
        sinks = [s.strip() for s in (search["notify"] or default_sinks).split(",") if s.strip()]
        if not sinks or "none" in sinks:
            continue

        alerts = []
        for lot_id in lot_ids:
            row = store.connect().execute("select title, url from lots where id=?", (lot_id,)).fetchone()
            bid_row = store.connect().execute(
                "select current_bid from bid_snapshots where lot_id=? order by observed_at desc limit 1",
                (lot_id,),
            ).fetchone()
            message = f'new match on "{search["name"]}"'
            if bid_row and bid_row["current_bid"]:
                message += f", bid €{bid_row['current_bid'] // 100}"
            if row and row["url"]:
                message += f" — {row['url']}"
            alerts.append(
                Alert(
                    lot_id=lot_id,
                    kind="new_lot",
                    title=(row["title"] if row else None) or f"lot {lot_id}",
                    message=message,
                )
            )
        batches.append(AlertBatch(search["id"], search["name"], sinks, alerts))
    return batches


def close_out(client, store, *, now: datetime | None = None, limit: int = 200) -> CloseOutReport:
    now = now or datetime.now(timezone.utc)
    report = CloseOutReport()
    for lot_id in store.lots_awaiting_outcome(now)[:limit]:
        try:
            detail = client.lot(lot_id)
        except CataError:
            report.failed += 1
            continue
        report.checked += 1
        store.upsert_lot(detail, detailed=True)
        if not detail.is_closed:
            report.still_open += 1
            store.record_snapshot(detail)
            continue
        store.record_outcome(detail)
        if detail.sold:
            report.sold += 1
        else:
            report.unsold += 1
    return report
