from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone

from .errors import CataError

REFRESH_WINDOW_HOURS = 48


@dataclass
class SweepReport:
    searches: int = 0
    lots_seen: int = 0
    lots_new: int = 0
    enriched: int = 0
    refreshed: int = 0
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
        for lot in lots:
            report.lots_seen += 1
            if not _known(store, lot.id):
                report.lots_new += 1
            store.upsert_lot(lot)
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
