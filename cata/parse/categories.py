from __future__ import annotations

import re

_CATEGORY_URL = re.compile(r"/c/(\d+)-")


SCOPES = ("subCategories", "categoriesOrderedNameAsc")


def parse_categories(props: dict) -> list[dict]:
    found: dict[int, dict] = {}

    for scope in SCOPES:
        if props.get(scope):
            props = {scope: props[scope]}
            break

    def walk(node) -> None:
        if isinstance(node, dict):
            url = str(node.get("url") or "")
            title = node.get("title") or node.get("name")
            if isinstance(node.get("id"), int) and title and _CATEGORY_URL.search(url):
                found[node["id"]] = {
                    "id": node["id"],
                    "title": title,
                    "url": url,
                    "parent_id": node.get("parent_id"),
                }
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(props)
    return sorted(found.values(), key=lambda category: category["title"])
