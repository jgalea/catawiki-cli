from __future__ import annotations


def matches_pattern(lot, pattern: str | None, specs=None) -> bool:
    """Test a lot against a saved search's local match filter.

    Catawiki's own search can't find some model names at all, so a broad query plus a
    local match on the title and specifications is more reliable than trusting the site.
    """
    if not pattern:
        return True

    needles = [word for word in pattern.lower().split() if word]
    haystack = " ".join(
        part.lower()
        for part in (
            lot.title or "",
            getattr(lot, "subtitle", "") or "",
            " ".join(f"{spec.name} {spec.value}" for spec in (specs or getattr(lot, "specifications", ()) or ())),
        )
        if part
    )
    return all(needle in haystack for needle in needles)
