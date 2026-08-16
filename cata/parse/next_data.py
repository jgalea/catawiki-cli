from __future__ import annotations

import json
import re

from ..errors import ParseError

_BLOB = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S
)


def extract(html: str, url: str) -> dict:
    match = _BLOB.search(html)
    if not match:
        raise ParseError(url, "__NEXT_DATA__")
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise ParseError(url, f"valid __NEXT_DATA__ JSON ({exc})") from exc
    props = data.get("props", {}).get("pageProps")
    if props is None:
        raise ParseError(url, "props.pageProps")
    return props
