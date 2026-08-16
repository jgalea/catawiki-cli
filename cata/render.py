from __future__ import annotations

from datetime import datetime, timezone

from rich.table import Table


def humanize_delta(when) -> str:
    if when is None:
        return "-"
    seconds = (when - datetime.now(timezone.utc)).total_seconds()
    if seconds <= 0:
        return "ended"
    days, rest = divmod(int(seconds), 86400)
    hours, rest = divmod(rest, 3600)
    minutes = rest // 60
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def lots_table(lots, details=None) -> Table:
    table = Table(header_style="bold")
    table.add_column("id", style="dim", no_wrap=True)
    table.add_column("lot")
    table.add_column("reserve", no_wrap=True)
    if details is not None:
        table.add_column("bid", justify="right", no_wrap=True)
        table.add_column("closes", justify="right", no_wrap=True)

    for lot in lots:
        title = lot.title if not lot.subtitle else f"{lot.title}\n[dim]{lot.subtitle}[/dim]"
        reserve = "no reserve" if lot.reserve_price_set is False else "reserve"
        row = [str(lot.id), title, reserve]
        if details is not None:
            detail = details.get(lot.id)
            bid = str(detail.current_bid) if detail and detail.current_bid else "no bids"
            row += [bid, humanize_delta(detail.bidding_end) if detail else "-"]
        table.add_row(*row)
    return table


def detail_table(detail) -> Table:
    table = Table.grid(padding=(0, 2))
    table.add_column(style="dim")
    table.add_column()
    rows = [
        ("lot", str(detail.id)),
        ("title", detail.title),
        ("subtitle", detail.subtitle or "-"),
        ("category", " / ".join(title for _, title in detail.category_path) or detail.category or "-"),
        ("current bid", str(detail.current_bid) if detail.current_bid else "no bids"),
        ("min next bid", str(detail.min_bid) if detail.min_bid else "-"),
        ("closes", humanize_delta(detail.bidding_end)),
        ("status", "sold" if detail.sold else ("closed" if detail.is_closed else "open")),
        ("bids", str(len(detail.bids))),
        ("seller", detail.seller.name if detail.seller and detail.seller.name else "-"),
        ("url", detail.url or "-"),
    ]
    for label, value in rows:
        table.add_row(label, value)
    return table


def specs_table(specs) -> Table:
    table = Table.grid(padding=(0, 2))
    table.add_column(style="dim")
    table.add_column()
    for spec in specs:
        table.add_row(spec.name, spec.value)
    return table


def bids_table(bids) -> Table:
    table = Table(header_style="bold")
    table.add_column("when", no_wrap=True)
    table.add_column("amount", justify="right", no_wrap=True)
    table.add_column("bidder", no_wrap=True)
    table.add_column("from", no_wrap=True)
    table.add_column("type", no_wrap=True)
    for bid in bids:
        when = bid.created_at.strftime("%Y-%m-%d %H:%M") if bid.created_at else "-"
        table.add_row(
            when,
            str(bid.amount),
            bid.bidder_name or (bid.bidder_token or "")[:8],
            (bid.bidder_country or "-").upper(),
            bid.bid_type or "bid",
        )
    return table
