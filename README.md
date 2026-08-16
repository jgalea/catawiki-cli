<div align="center">

# cata

[![License](https://img.shields.io/badge/LICENSE-MIT-5C9E31?style=for-the-badge)](LICENSE)
[![Python](https://img.shields.io/badge/PYTHON-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org)
[![Built by](https://img.shields.io/badge/BUILT%20BY-JGALEA-8A2BE2?style=for-the-badge&logo=github&logoColor=white)](https://github.com/jgalea)

**Search Catawiki auctions, track lots, and price them against what comparable lots actually sold for.**

</div>

Catawiki tells you what a lot is bid at right now. It won't tell you what the last twenty of the same thing sold for, which is the number that decides whether the current bid is cheap. `cata` builds that number locally, by watching lots while they're live and recording what they fetched once they closed.

## What it can actually see

Every Catawiki page ships its data as a JSON blob in the HTML, so this reads structured records rather than scraping markup.

Search pages give 24 lots at a time with id, title, subtitle, images, auction, reserve flag and shipping, plus the full facet tree. Lot pages give the current bid, minimum next bid, closing time, reserve status, sold status, category breadcrumb, specifications, seller, and the complete bid history: every bid with its amount, timestamp, anonymized bidder token, bidder country and that bidder's lifetime bid count.

Two limits are worth knowing before you start.

Search only indexes open lots. There's no sold filter and no archive, so a sold-price database can't be backfilled. It has to be grown: `cata harvest` records lots while they're live, then re-fetches each one after it closes to capture the hammer price. Comps are empty on day one and get useful after a few weeks of harvesting. The tool says "not enough data" rather than inventing a median from four samples.

Search results carry no closing time and no specifications. Both live only on lot pages, so the harvester spends one lot-page fetch per new lot before that lot can be closed out or used as a comparable.

## Catawiki's search never returns nothing

Ask Catawiki for something it doesn't have and it answers with semantically similar lots instead of an empty result. Searching "herman miller aeron" returns toy helicopters, a teddy bear and a Zeppelin stamp, because "aeron" is near "aero" and "Herman" is near "Hermann".

Every lot carries an `isVectorSearchResult` flag marking those, and the page carries `meta.extended_search_result`. `cata` drops flagged lots and tells you nothing matched. `--fuzzy` keeps them.

This matters more than it sounds. Genuine result pages are salted with fallback lots too: "herman miller" returns 9 real hits and 15 semantic neighbours on the same page, so the filter is applied per lot rather than per page.

## Install

```
uv venv && uv pip install -e .
```

## Use

```
cata search "omega speedmaster" --limit 10        # open lots
cata search "rolex" --max-price 2000 --with-bids  # slower, adds current bid and countdown
cata lot 105781311 --bids                         # one lot, in full
cata track add "omega speedmaster" --name watches # save a search for the harvester
cata track add 105781311 --max-bid 900            # watch one lot
cata track add "herman miller" --name aeron \
  --match aeron --notify macos                    # notify when a matching lot appears
cata watch                                        # live table of watched lots
cata harvest                                      # sweep, enrich, close out
cata comps 105781311                              # what comparable lots sold for
cata deals --ending-in 12 --min-discount 30       # open lots bid below comps
cata categories --parent 333                      # category ids for filtering
cata export --table bids --format csv             # the raw local data
```

`--json` works on every read command, so an agent can consume this as easily as a person.

## How comps work

`cata comps` looks for closed, sold lots in the same category group and reports median, interquartile range, full range, sample size and sell-through rate.

Comparability is tried in tiers, and the answer always states which tier it used: category plus brand plus model first, then category plus brand, then title overlap within the category, then the category alone. Grouping happens on the middle rung of Catawiki's category breadcrumb, because a lot's own category is often an auction theme like "Essential Watches below €1,500" that fragments the sample.

Below eight sold comparables, `comps` returns the count and no median. `deals` skips any lot whose comps didn't clear that bar, so a discount percentage is never computed against a handful of lots.

## Alerts on new lots

A saved search with `--match` fires once per lot the first time one matches, and never again for that lot. The match runs locally over the title, subtitle and specifications, which is the reliable way to watch for a model name Catawiki's own search can't find.

Sinks are `terminal`, `macos`, `telegram` and `whatsapp`, comma-separated, or `none` to record hits silently. The last two shell out to a `telegram` or `pigeon` command; if that binary isn't on your PATH, the run says so rather than silently dropping the alert.

`macos` posts through `osascript`. terminal-notifier is deliberately not used even when installed: its 2.x builds exit 0 on current macOS while the notification never appears, so it reports success for an alert you never got.

## Scheduling

`cata harvest` is designed to run hourly. The sweep pages your saved searches, fetches detail for lots it hasn't seen before, refreshes anything closing within 48 hours, and records the outcome of everything that has ended. `scripts/harvest.sh` is a launchd-friendly wrapper.

## Where data lives

SQLite at `~/.cata/cata.db`, or wherever `CATA_DB` points. Tables: `lots` (with the raw JSON kept so a Catawiki schema change can be re-parsed without re-fetching), `bid_snapshots` (bid trajectory over time), `bids` (full history per lot), `searches`, `watches`. Plain SQL works fine when the CLI doesn't have the view you want.

HTTP responses are cached on disk under `~/.cata/cache`.

## Notes

This is an unofficial tool with no affiliation to Catawiki. It only reads. It has no login, places no bids, and sends nothing to the site beyond GET requests.

Catawiki's `robots.txt` sits behind the same bot protection as the rest of the site and returns 403, so its crawl directives could not be read. Rate limiting is conservative by default for that reason: one request per second, four concurrent at most.
