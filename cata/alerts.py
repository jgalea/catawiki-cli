from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone

SINKS = ("terminal", "macos", "telegram", "whatsapp")

TELEGRAM_CLI = "telegram"
WHATSAPP_CLI = "pigeon"


@dataclass(frozen=True)
class Alert:
    lot_id: int
    kind: str
    title: str
    message: str


def evaluate(detail, watch, *, now=None, closing_within_minutes: int = 30) -> list[Alert]:
    now = now or datetime.now(timezone.utc)
    fired = set((watch["alert_state"] or "").split(","))
    alerts: list[Alert] = []

    def add(kind: str, message: str) -> None:
        if kind not in fired:
            alerts.append(Alert(lot_id=detail.id, kind=kind, title=detail.title, message=message))

    if detail.is_closed:
        if detail.sold:
            add("sold", f"sold for {detail.current_bid}" if detail.current_bid else "sold")
        else:
            add("sold", "closed unsold")
        return alerts

    max_bid = watch["max_bid"]
    if max_bid and detail.current_bid and detail.current_bid.amount > max_bid:
        add("outbid", f"bid is {detail.current_bid}, above your max")

    if detail.reserve_met:
        add("reserve_met", "reserve price met")

    if detail.bidding_end:
        minutes_left = (detail.bidding_end - now).total_seconds() / 60
        if 0 < minutes_left <= closing_within_minutes:
            bid = str(detail.current_bid) if detail.current_bid else "no bids"
            add("closing", f"closes in {int(minutes_left)}m at {bid}")

    return alerts


def _notify_macos(alert: Alert) -> None:
    if shutil.which("terminal-notifier"):
        subprocess.run(
            [
                "terminal-notifier",
                "-title",
                "Catawiki",
                "-subtitle",
                alert.title,
                "-message",
                alert.message,
            ],
            check=False,
        )
        return
    script = (
        f"display notification {alert.message!r} with title \"Catawiki\" subtitle {alert.title!r}"
    )
    subprocess.run(["osascript", "-e", script], check=False)


def _notify_cli(command: str, alert: Alert, target: str | None) -> str | None:
    """Send through an external messaging CLI. Returns a reason string if it couldn't."""
    if not shutil.which(command):
        return f"{command} is not on PATH, so that alert was not sent"
    if not target:
        return f"no target configured for {command}, so that alert was not sent"
    subprocess.run([command, "send", target, f"{alert.title}: {alert.message}"], check=False)
    return None


def deliver(
    alerts,
    sinks,
    *,
    telegram_target: str | None = None,
    whatsapp_target: str | None = None,
    console=None,
) -> None:
    problems: set[str] = set()
    for alert in alerts:
        if "terminal" in sinks and console is not None:
            console.print(f"[bold yellow]{alert.kind}[/bold yellow] {alert.title}: {alert.message}")
        if "macos" in sinks:
            _notify_macos(alert)
        if "telegram" in sinks:
            problem = _notify_cli(TELEGRAM_CLI, alert, telegram_target)
            if problem:
                problems.add(problem)
        if "whatsapp" in sinks:
            problem = _notify_cli(WHATSAPP_CLI, alert, whatsapp_target)
            if problem:
                problems.add(problem)

    # A sink that quietly does nothing is worse than no sink, so say so.
    for problem in sorted(problems):
        if console is not None:
            console.print(f"[red]{problem}[/red]")
        else:
            print(problem)
