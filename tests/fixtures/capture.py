"""Re-capture parser fixtures from the live site. Run manually, not in CI."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from cata.fetch import Fetcher
from cata.parse.next_data import extract

HERE = Path(__file__).parent

DROP = {
    "_nextI18Next",
    "_sentryTraceData",
    "_sentryBaggage",
    "runtimeConfig",
    "initialTrackingData",
    "initialTrackingEvents",
    "dataLayerBase",
    "experiments",
    "userSegments",
    "scriptLoader",
    "rawGallery",
    "trustpilot",
    "feedbacks",
}

TARGETS = {
    "search_watches.json": "https://www.catawiki.com/en/s?q=omega+speedmaster",
    "lot_open.json": "https://www.catawiki.com/en/l/105781311",
    "lot_closed.json": "https://www.catawiki.com/en/l/104500000",
}


def main() -> None:
    fetcher = Fetcher(rate_per_second=0.5, cache_ttl=0)
    for name, url in TARGETS.items():
        props = extract(fetcher.get(url), url)
        for key in DROP:
            props.pop(key, None)
        (HERE / name).write_text(json.dumps(props, indent=1, ensure_ascii=False))
        print(f"wrote {name} from {url}")


if __name__ == "__main__":
    main()
