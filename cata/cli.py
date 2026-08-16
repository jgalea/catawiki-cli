from __future__ import annotations

import csv
import dataclasses
import json
import re
import sys
import time
from datetime import datetime

import typer
from rich.console import Console
from rich.table import Table

from . import alerts as alerts_mod
from . import comps as comps_mod
from . import deals as deals_mod
from . import harvest as harvest_mod
from . import render
from .client import Client
from .errors import CataError
from .store import Store

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Search Catawiki auctions, track lots, and price them against comparable sold lots.",
)
track_app = typer.Typer(no_args_is_help=True, help="Saved searches and watched lots.")
app.add_typer(track_app, name="track")

console = Console()

_LOT_ID = re.compile(r"/l/(\d+)")


def lot_id(value: str) -> int:
    if value.isdigit():
        return int(value)
    match = _LOT_ID.search(value)
    if not match:
        raise typer.BadParameter(f"could not find a lot id in {value!r}")
    return int(match.group(1))


def dump(payload) -> None:
    def default(obj):
        if dataclasses.is_dataclass(obj):
            return {
                key: value
                for key, value in dataclasses.asdict(obj).items()
                if key != "raw"
            }
        if isinstance(obj, datetime):
            return obj.isoformat()
        return str(obj)

    console.print_json(json.dumps(payload, default=default))


@app.command("search")
def search_cmd(
    query: str = typer.Argument(..., help="What to search for"),
    limit: int = typer.Option(24, "--limit", "-n", help="How many lots to return"),
    category: int = typer.Option(None, "--category", "-c", help="Category id to restrict to"),
    max_price: int = typer.Option(None, "--max-price", help="Highest current bid, in whole euros"),
    ending_in: int = typer.Option(None, "--ending-in", help="Only lots closing within this many days"),
    no_reserve: bool = typer.Option(False, "--no-reserve", help="Only lots without a reserve price"),
    sort: str = typer.Option(None, "--sort", help="Catawiki sort key, for example closing_soon"),
    with_bids: bool = typer.Option(
        False,
        "--with-bids",
        "-b",
        help="Also fetch each lot page for its current bid and closing time. Slower.",
    ),
    as_json: bool = typer.Option(False, "--json", help="Emit JSON instead of a table"),
) -> None:
    """Search open lots."""
    client = Client()
    lots = client.search_all(
        query,
        limit=limit,
        category=category,
        max_price=max_price,
        ending_in_days=ending_in,
        no_reserve=no_reserve,
        sort=sort,
    )
    if not lots:
        console.print("[yellow]no lots found[/yellow]")
        return

    details = None
    if with_bids:
        with console.status(f"fetching {len(lots)} lot pages"):
            details = client.details([lot.id for lot in lots])

    if as_json:
        dump([details.get(lot.id, lot) if details else lot for lot in lots])
        return

    console.print(render.lots_table(lots, details))
    console.print(f"[dim]{len(lots)} lots[/dim]")


@app.command("lot")
def lot_cmd(
    target: str = typer.Argument(..., help="Lot id or Catawiki lot URL"),
    bids: bool = typer.Option(False, "--bids", help="Show the full bid history"),
    as_json: bool = typer.Option(False, "--json", help="Emit JSON instead of a table"),
) -> None:
    """Show everything known about one lot."""
    detail = Client().lot(lot_id(target))
    if as_json:
        dump(detail)
        return
    console.print(render.detail_table(detail))
    if detail.specifications:
        console.print()
        console.print(render.specs_table(detail.specifications))
    if bids and detail.bids:
        console.print()
        console.print(render.bids_table(detail.bids))


@track_app.command("add")
def track_add(
    target: str = typer.Argument(..., help="A search query, or a lot id or URL to watch"),
    name: str = typer.Option(None, "--name", help="Name for a saved search"),
    max_bid: int = typer.Option(None, "--max-bid", help="Alert once the bid passes this, in whole euros"),
    note: str = typer.Option(None, "--note", help="Free-text note on a watched lot"),
    max_price: int = typer.Option(None, "--max-price", help="Saved-search filter: highest bid in whole euros"),
    category: int = typer.Option(None, "--category", help="Saved-search filter: category id"),
    no_reserve: bool = typer.Option(False, "--no-reserve", help="Saved-search filter: no-reserve lots only"),
) -> None:
    """Track a lot, or save a search for the harvester to sweep."""
    store = Store()
    if target.isdigit() or "/l/" in target:
        identifier = lot_id(target)
        detail = Client().lot(identifier)
        store.upsert_lot(detail)
        store.record_snapshot(detail)
        store.add_watch(identifier, max_bid=max_bid * 100 if max_bid else None, note=note)
        console.print(f"watching [bold]{detail.title}[/bold] ({identifier})")
        return

    filters = {}
    if max_price is not None:
        filters["max_price"] = max_price
    if category is not None:
        filters["category"] = category
    if no_reserve:
        filters["no_reserve"] = True
    store.add_search(name or target, target, filters)
    console.print(f"saved search [bold]{name or target}[/bold]")


@track_app.command("list")
def track_list() -> None:
    """List saved searches and watched lots."""
    store = Store()
    searches = store.searches()
    watches = store.watches()

    if searches:
        table = Table(title="saved searches", header_style="bold")
        table.add_column("id", no_wrap=True)
        table.add_column("name")
        table.add_column("query")
        table.add_column("last swept", no_wrap=True)
        for row in searches:
            table.add_row(
                str(row["id"]), row["name"], row["query"], (row["last_swept_at"] or "never")[:16]
            )
        console.print(table)

    if watches:
        table = Table(title="watched lots", header_style="bold")
        table.add_column("lot", no_wrap=True)
        table.add_column("title")
        table.add_column("max bid", justify="right", no_wrap=True)
        table.add_column("closes", justify="right", no_wrap=True)
        for row in watches:
            end = row["bidding_end"]
            table.add_row(
                str(row["lot_id"]),
                row["title"] or "-",
                f"€{row['max_bid'] // 100}" if row["max_bid"] else "-",
                render.humanize_delta(datetime.fromisoformat(end)) if end else "-",
            )
        console.print(table)

    if not searches and not watches:
        console.print("[yellow]nothing tracked yet[/yellow]")


@track_app.command("rm")
def track_rm(
    target: str = typer.Argument(..., help="Saved-search id or name, or a watched lot id"),
) -> None:
    """Stop tracking a search or a lot."""
    store = Store()
    if target.isdigit():
        store.remove_watch(int(target))
        store.remove_search(int(target))
    else:
        store.remove_search(target)
    console.print(f"stopped tracking {target}")


@app.command("harvest")
def harvest_cmd(
    sweep_only: bool = typer.Option(False, "--sweep-only", help="Only sweep saved searches"),
    close_out_only: bool = typer.Option(False, "--close-out-only", help="Only record outcomes of ended lots"),
) -> None:
    """Sweep saved searches and record the outcome of lots that have ended."""
    client = Client()
    store = Store()
    if not close_out_only:
        with console.status("sweeping saved searches"):
            report = harvest_mod.sweep(client, store)
        console.print(
            f"swept {report.searches} searches: {report.lots_seen} lots seen, {report.lots_new} new, "
            f"{report.enriched} enriched, {report.refreshed} refreshed, {report.failed} failed"
        )
    if not sweep_only:
        with console.status("closing out ended lots"):
            report = harvest_mod.close_out(client, store)
        console.print(
            f"closed out {report.checked} lots: {report.sold} sold, {report.unsold} unsold, "
            f"{report.still_open} still open, {report.failed} failed"
        )


@app.command("comps")
def comps_cmd(
    target: str = typer.Argument(..., help="Lot id or Catawiki lot URL"),
    as_json: bool = typer.Option(False, "--json", help="Emit JSON instead of a table"),
) -> None:
    """What comparable lots actually sold for."""
    store = Store()
    detail = Client().lot(lot_id(target))
    result = comps_mod.for_lot(store, detail)
    if as_json:
        dump(result)
        return
    if not result.sufficient:
        console.print(
            f"[yellow]not enough data: {result.sample_size} comparable sold lots "
            f"(need {comps_mod.MIN_SAMPLE}).[/yellow]"
        )
        console.print("[dim]Run `cata harvest` for a few weeks to build the sample.[/dim]")
        return
    table = Table.grid(padding=(0, 2))
    table.add_column(style="dim")
    table.add_column()
    table.add_row("basis", result.basis)
    table.add_row("sample", f"{result.sample_size} sold lots")
    table.add_row("median", str(result.median))
    table.add_row("middle half", f"{result.p25} to {result.p75}")
    table.add_row("range", f"{result.low} to {result.high}")
    table.add_row(
        "sell-through",
        f"{result.sell_through:.0%}" if result.sell_through is not None else "-",
    )
    if detail.current_bid:
        table.add_row("this lot", f"{detail.current_bid} now")
    console.print(table)


@app.command("deals")
def deals_cmd(
    ending_in: int = typer.Option(12, "--ending-in", help="Hours ahead to look"),
    min_discount: int = typer.Option(30, "--min-discount", help="Minimum discount against comps, in percent"),
    as_json: bool = typer.Option(False, "--json", help="Emit JSON instead of a table"),
) -> None:
    """Open lots bid well below what comparable lots sold for."""
    found = deals_mod.scan(
        Store(), ending_within_hours=ending_in, min_discount=min_discount / 100
    )
    if as_json:
        dump(found)
        return
    if not found:
        console.print("[yellow]no deals found[/yellow]")
        console.print(
            "[dim]Either nothing is underbid, or the comps database is still too thin. "
            "Check one lot with `cata comps <lot>`.[/dim]"
        )
        return
    table = Table(header_style="bold")
    table.add_column("lot", no_wrap=True)
    table.add_column("title")
    table.add_column("bid", justify="right", no_wrap=True)
    table.add_column("median", justify="right", no_wrap=True)
    table.add_column("off", justify="right", no_wrap=True)
    table.add_column("n", justify="right", no_wrap=True)
    table.add_column("closes", justify="right", no_wrap=True)
    for deal in found:
        table.add_row(
            str(deal.lot_id),
            deal.title,
            str(deal.current_bid),
            str(deal.comp_median),
            f"{deal.discount:.0%}",
            str(deal.sample_size),
            render.humanize_delta(deal.bidding_end),
        )
    console.print(table)


@app.command("watch")
def watch_cmd(
    once: bool = typer.Option(False, "--once", help="Print the current state and exit"),
    interval: int = typer.Option(60, "--interval", help="Seconds between refreshes"),
    notify: str = typer.Option(
        "terminal", "--notify", help="Comma-separated sinks: terminal,macos,telegram,whatsapp"
    ),
    telegram_to: str = typer.Option(None, "--telegram-to", help="Telegram chat for alerts"),
    whatsapp_to: str = typer.Option(None, "--whatsapp-to", help="WhatsApp contact for alerts"),
) -> None:
    """Follow your watched lots and alert as they move."""
    store = Store()
    client = Client()
    sinks = [sink.strip() for sink in notify.split(",") if sink.strip()]

    while True:
        watches = store.watches()
        if not watches:
            console.print("[yellow]nothing watched. Add one with `cata track add <lot-id>`[/yellow]")
            return

        table = Table(header_style="bold")
        table.add_column("lot", no_wrap=True)
        table.add_column("title")
        table.add_column("bid", justify="right", no_wrap=True)
        table.add_column("next", justify="right", no_wrap=True)
        table.add_column("max", justify="right", no_wrap=True)
        table.add_column("closes", justify="right", no_wrap=True)

        for row in watches:
            detail = client.lot(row["lot_id"])
            store.upsert_lot(detail)
            store.record_snapshot(detail)

            fired = alerts_mod.evaluate(detail, row)
            if fired:
                alerts_mod.deliver(
                    fired,
                    sinks,
                    telegram_target=telegram_to,
                    whatsapp_target=whatsapp_to,
                    console=console,
                )
                state = ",".join(
                    filter(None, [(row["alert_state"] or "")] + [alert.kind for alert in fired])
                )
                store.set_alert_state(row["lot_id"], state.strip(","))

            over = detail.current_bid and row["max_bid"] and detail.current_bid.amount > row["max_bid"]
            table.add_row(
                str(detail.id),
                detail.title,
                f"[red]{detail.current_bid}[/red]" if over else str(detail.current_bid or "-"),
                str(detail.min_bid or "-"),
                f"€{row['max_bid'] // 100}" if row["max_bid"] else "-",
                render.humanize_delta(detail.bidding_end),
            )

        if not once:
            console.clear()
        console.print(table)
        if once:
            return
        time.sleep(interval)


@app.command("categories")
def categories_cmd(
    parent: int = typer.Option(None, "--parent", help="Category id to list children of"),
    as_json: bool = typer.Option(False, "--json", help="Emit JSON instead of a table"),
) -> None:
    """List Catawiki categories and their ids."""
    found = Client().categories(parent)
    if as_json:
        dump(found)
        return
    table = Table(header_style="bold")
    table.add_column("id", no_wrap=True)
    table.add_column("category")
    for row in found:
        table.add_row(str(row["id"]), row["title"])
    console.print(table)


@app.command("export")
def export_cmd(
    table_name: str = typer.Option("lots", "--table", help="lots or bids"),
    fmt: str = typer.Option("csv", "--format", help="csv or json"),
) -> None:
    """Dump the local database to stdout."""
    if table_name not in {"lots", "bids"}:
        raise typer.BadParameter("table must be lots or bids")
    rows = Store().connect().execute(f"select * from {table_name}").fetchall()
    if fmt == "json":
        dump([dict(row) for row in rows])
        return
    if not rows:
        return
    writer = csv.DictWriter(sys.stdout, fieldnames=rows[0].keys())
    writer.writeheader()
    for row in rows:
        writer.writerow(dict(row))


def main() -> None:
    try:
        app()
    except CataError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    main()
