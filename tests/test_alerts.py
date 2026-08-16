from datetime import datetime, timedelta, timezone

from cata.alerts import evaluate
from cata.parse.lot import parse_lot


class Row(dict):
    def __getitem__(self, key):
        return self.get(key)


def test_closing_soon_fires(lot_open_props):
    detail = parse_lot(lot_open_props)
    now = detail.bidding_end - timedelta(minutes=10)
    alerts = evaluate(detail, Row(lot_id=detail.id, max_bid=None, alert_state=""), now=now)
    assert any(alert.kind == "closing" for alert in alerts)


def test_closing_does_not_refire_when_already_alerted(lot_open_props):
    detail = parse_lot(lot_open_props)
    now = detail.bidding_end - timedelta(minutes=10)
    alerts = evaluate(detail, Row(lot_id=detail.id, max_bid=None, alert_state="closing"), now=now)
    assert not any(alert.kind == "closing" for alert in alerts)


def test_outbid_fires_when_bid_passes_max(lot_open_props):
    detail = parse_lot(lot_open_props)
    below = detail.current_bid.amount - 100
    alerts = evaluate(
        detail, Row(lot_id=detail.id, max_bid=below, alert_state=""), now=detail.bidding_start
    )
    assert any(alert.kind == "outbid" for alert in alerts)


def test_no_outbid_when_bid_below_max(lot_open_props):
    detail = parse_lot(lot_open_props)
    above = detail.current_bid.amount + 100000
    alerts = evaluate(
        detail, Row(lot_id=detail.id, max_bid=above, alert_state=""), now=detail.bidding_start
    )
    assert not any(alert.kind == "outbid" for alert in alerts)


def test_sold_fires_for_closed_lot(lot_closed_props):
    detail = parse_lot(lot_closed_props)
    alerts = evaluate(
        detail,
        Row(lot_id=detail.id, max_bid=None, alert_state=""),
        now=datetime.now(timezone.utc),
    )
    assert any(alert.kind == "sold" for alert in alerts)
