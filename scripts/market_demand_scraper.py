#!/usr/bin/env python3
"""
Scan public Israeli primary-ticketing listing pages for sold-out / fast-selling demand.

TradeTix uses the CSV to decide which events to feature on the resale marketplace.
This script reads publicly visible listing/event pages only. It does not log in,
does not touch checkout, and does not solve CAPTCHAs.

Usage (from the scripts/ directory):

    pip install -r requirements-market-demand.txt
    playwright install chromium
    python market_demand_scraper.py
    python market_demand_scraper.py --sports-only --output hot_events_report.csv
    python test_market_demand_scraper.py
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import random
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

LOGGER = logging.getLogger("market_demand")

CSV_COLUMNS = (
    "Event Name",
    "Date",
    "Venue",
    "Category",
    "Demand Level",
    "Source",
    "URL",
)

SOLD_OUT_KEYWORDS = (
    "סולד אאוט",
    "סולד-אאוט",
    "sold out",
    "sold-out",
    "אזל המלאי",
    "אזלו הכרטיסים",
    "אין כרטיסים",
    "נגמרו הכרטיסים",
    "המכירה הסתיימה",
    "the sale has ended",
    "no tickets",
)

FAST_SELLING_KEYWORDS = (
    "כרטיסים אחרונים",
    "כרטיסים אחרונים נותרו",
    "נשארו כרטיסים בודדים",
    "מלאי אחרון",
    "last tickets",
    "last few tickets",
    "almost sold out",
    "selling fast",
    "limited tickets",
    "few tickets left",
)

USER_AGENTS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0",
)

SPORTS_WATCHLIST = (
    {
        "id": "maccabi_haifa_football",
        "category": "Sports",
        "needles": ("מכבי חיפה", "maccabi haifa"),
        "league": "Ligat Ha'Al",
    },
    {
        "id": "maccabi_ta_football",
        "category": "Sports",
        "needles": ("מכבי תל אביב", "maccabi tel aviv", "maccabi tel-aviv"),
        "league": "Ligat Ha'Al",
        "exclude": ("כדורסל", "euroleague", "יורוליג", "basketball"),
    },
    {
        "id": "beitar_jerusalem",
        "category": "Sports",
        "needles": ("ביתר ירושלים", "בית״ר ירושלים", 'בית"ר ירושלים', "beitar jerusalem"),
        "league": "Ligat Ha'Al",
    },
    {
        "id": "maccabi_ta_euroleague",
        "category": "Sports",
        "needles": ("יורוליג", "euroleague", "מכבי תל אביב כדורסל", "maccabi playtika"),
        "league": "EuroLeague",
    },
)

# Listing pages only. Selectors are best-effort; full-page keyword scan is the fallback.
SITE_CONFIGS: tuple[dict[str, Any], ...] = (
    {
        "name": "Leaan",
        "list_urls": (
            "https://www.leaan.co.il/",
            "https://www.leaan.co.il/category/%D7%94%D7%95%D7%A4%D7%A2%D7%95%D7%AA",
            "https://www.leaan.co.il/category/%D7%91%D7%99%D7%93%D7%95%D7%A8-%D7%95%D7%A1%D7%98%D7%A0%D7%93%D7%90%D7%A4",
            "https://www.leaan.co.il/search?q=%D7%9E%D7%9B%D7%91%D7%99+%D7%97%D7%99%D7%A4%D7%94",
            "https://www.leaan.co.il/search?q=%D7%99%D7%95%D7%A8%D7%95%D7%9C%D7%99%D7%92",
        ),
        "link_contains": ("/events/", "/event/", "/category/"),
        "card_selectors": (
            "a[href*='/events/']",
            "article a[href]",
            ".event-card a",
            "[class*='event'] a[href]",
        ),
    },
    {
        "name": "Zappa",
        "list_urls": (
            "https://www.zappa-club.co.il/",
            "https://www.zappa-club.co.il/shows",
        ),
        "link_contains": ("/show", "/event", "/shows/"),
        "card_selectors": (
            "a[href*='/show']",
            "a[href*='/event']",
            "article a[href]",
        ),
    },
    {
        "name": "Eventim IL",
        "list_urls": (
            "https://www.eventim.co.il/",
            "https://www.eventim.co.il/event/search/?search=maccabi",
            "https://www.eventim.co.il/event/search/?search=euroleague",
        ),
        "link_contains": ("/event/", "/artist/", "/attraction/"),
        "card_selectors": (
            "a[href*='/event/']",
            "a[href*='/attraction/']",
            ".listing-item a",
        ),
    },
    {
        "name": "Ticketmaster IL",
        "list_urls": (
            "https://www.ticketmaster.co.il/",
        ),
        "link_contains": ("/event/", "/artist/"),
        "card_selectors": (
            "a[href*='/event/']",
            "a[data-testid='event-list-link']",
            "a[href*='/artist/']",
        ),
    },
)


@dataclass
class HotEvent:
    event_name: str
    date: str
    venue: str
    category: str
    demand_level: str
    source: str
    url: str

    def as_csv_row(self) -> dict[str, str]:
        return {
            "Event Name": self.event_name,
            "Date": self.date,
            "Venue": self.venue,
            "Category": self.category,
            "Demand Level": self.demand_level,
            "Source": self.source,
            "URL": self.url,
        }


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "")).strip()


def _haystack(value: str) -> str:
    return _normalize_text(value).lower().replace("״", '"').replace("׳", "'")


def classify_demand(text: str) -> str | None:
    hay = _haystack(text)
    if any(keyword.lower() in hay for keyword in SOLD_OUT_KEYWORDS):
        return "Sold Out"
    if any(keyword.lower() in hay for keyword in FAST_SELLING_KEYWORDS):
        return "Fast Selling"
    return None


def infer_sports_hit(text: str) -> dict[str, str] | None:
    hay = _haystack(text)
    for club in SPORTS_WATCHLIST:
        if not any(needle.lower() in hay for needle in club["needles"]):
            continue
        excluded = club.get("exclude") or ()
        if any(token.lower() in hay for token in excluded):
            continue
        return club
    return None


def classify_category(text: str, sports_hit: bool = False) -> str:
    if sports_hit:
        return "Sports"
    hay = _haystack(text)
    comedy = ("סטנדאפ", "סטנד-אפ", "stand up", "stand-up", "comedy", "קומדי")
    if any(token in hay for token in comedy):
        return "Comedy"
    sports = ("כדורגל", "כדורסל", "football", "soccer", "basketball", "ליגת העל", "יורוליג")
    if any(token in hay for token in sports):
        return "Sports"
    return "Music"


def polite_delay(min_seconds: float, max_seconds: float) -> None:
    low = max(0.2, min(min_seconds, max_seconds))
    high = max(low, max(min_seconds, max_seconds))
    time.sleep(random.uniform(low, high))


def extract_json_ld_events(page) -> list[dict[str, str]]:
    blobs = page.evaluate(
        """() => Array.from(document.querySelectorAll('script[type="application/ld+json"]'))
            .map((node) => node.textContent || '')"""
    )
    events: list[dict[str, str]] = []
    for raw in blobs or []:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        nodes = data if isinstance(data, list) else [data]
        if isinstance(data, dict) and "@graph" in data:
            nodes = data["@graph"]
        for node in nodes:
            if not isinstance(node, dict):
                continue
            types = node.get("@type") or ""
            type_list = types if isinstance(types, list) else [types]
            if "Event" not in type_list:
                continue
            location = node.get("location") or {}
            if isinstance(location, list):
                location = location[0] if location else {}
            venue = ""
            if isinstance(location, dict):
                venue = location.get("name") or ""
                address = location.get("address") or {}
                if isinstance(address, dict):
                    venue = venue or address.get("addressLocality") or ""
            events.append(
                {
                    "name": _normalize_text(str(node.get("name") or "")),
                    "date": _normalize_text(str(node.get("startDate") or node.get("endDate") or "")),
                    "venue": _normalize_text(str(venue)),
                }
            )
    return events


def collect_listing_links(page, site: dict[str, Any], max_links: int) -> list[str]:
    hrefs: list[str] = []
    for selector in site.get("card_selectors") or ():
        try:
            handles = page.locator(selector)
            count = min(handles.count(), max_links * 2)
        except Exception:
            continue
        for index in range(count):
            try:
                href = handles.nth(index).get_attribute("href") or ""
            except Exception:
                continue
            if not href or href.startswith("javascript:"):
                continue
            absolute = urljoin(page.url, href)
            if any(token in absolute for token in site.get("link_contains") or ()):
                hrefs.append(absolute)
    # Deduplicate while keeping order.
    seen: set[str] = set()
    unique: list[str] = []
    for href in hrefs:
        key = href.split("#", 1)[0].rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        unique.append(href)
        if len(unique) >= max_links:
            break
    return unique


def scrape_page_text(page) -> str:
    try:
        return _normalize_text(page.inner_text("body"))
    except Exception:
        return ""


def build_event(
    *,
    name: str,
    date: str,
    venue: str,
    source: str,
    url: str,
    demand: str,
    page_text: str,
) -> HotEvent | None:
    if not name or not demand:
        return None
    sports = infer_sports_hit(f"{name} {page_text}")
    return HotEvent(
        event_name=name[:240],
        date=date or "",
        venue=venue[:180],
        category=classify_category(f"{name} {page_text}", sports_hit=bool(sports)),
        demand_level=demand,
        source=source,
        url=url,
    )


def scrape_event_page(page, url: str, source: str) -> list[HotEvent]:
    page.goto(url, wait_until="domcontentloaded", timeout=45_000)
    try:
        page.wait_for_load_state("networkidle", timeout=8_000)
    except Exception:
        pass
    text = scrape_page_text(page)
    demand = classify_demand(text)
    if not demand:
        return []

    json_ld = extract_json_ld_events(page)
    if json_ld:
        rows = []
        for item in json_ld:
            event = build_event(
                name=item["name"] or page.title(),
                date=item["date"],
                venue=item["venue"],
                source=source,
                url=url,
                demand=demand,
                page_text=text,
            )
            if event:
                rows.append(event)
        if rows:
            return rows

    title = _normalize_text(page.title()).split("|")[0].split("-")[0]
    event = build_event(
        name=title,
        date="",
        venue="",
        source=source,
        url=url,
        demand=demand,
        page_text=text,
    )
    return [event] if event else []


def scrape_listing_page(page, url: str, source: str) -> list[HotEvent]:
    page.goto(url, wait_until="domcontentloaded", timeout=45_000)
    try:
        page.wait_for_load_state("networkidle", timeout=8_000)
    except Exception:
        pass
    text = scrape_page_text(page)
    demand = classify_demand(text)
    if not demand:
        return []
    title = _normalize_text(page.title()).split("|")[0]
    sports = infer_sports_hit(f"{title} {text}")
    if sports:
        name = title
    else:
        name = title
    event = build_event(
        name=name,
        date="",
        venue="",
        source=source,
        url=url,
        demand=demand,
        page_text=text,
    )
    return [event] if event else []


def write_csv(path: Path, events: list[HotEvent]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for event in events:
            writer.writerow(event.as_csv_row())


def dedupe_events(events: list[HotEvent]) -> list[HotEvent]:
    seen: set[tuple[str, str, str]] = set()
    unique: list[HotEvent] = []
    for event in events:
        key = (_haystack(event.event_name), _haystack(event.date), event.url.rstrip("/"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(event)
    return unique


def run_scrape(args: argparse.Namespace) -> list[HotEvent]:
    from playwright.sync_api import TimeoutError as PlaywrightTimeout
    from playwright.sync_api import sync_playwright

    collected: list[HotEvent] = []
    sites = SITE_CONFIGS
    if args.sports_only:
        sites = tuple(
            site
            for site in SITE_CONFIGS
            if any("search" in url or "maccabi" in url or "euroleague" in url for url in site["list_urls"])
            or site["name"] in {"Leaan", "Eventim IL"}
        )

    with sync_playwright() as playwright:
        # Several Israeli CDNs (Zappa, Eventim) fail HTTP/2 in headless Chromium.
        browser = playwright.chromium.launch(
            headless=not args.headed,
            args=["--disable-http2", "--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            locale="he-IL",
            timezone_id="Asia/Jerusalem",
            extra_http_headers={"Accept-Language": "he-IL,he;q=0.9,en;q=0.6"},
            viewport={"width": random.choice((390, 1280, 1440)), "height": random.choice((844, 800, 900))},
        )
        page = context.new_page()
        page.set_default_timeout(45_000)

        for site in sites:
            LOGGER.info("Scanning %s", site["name"])
            for list_url in site["list_urls"]:
                if args.sports_only and site["name"] in {"Zappa", "Ticketmaster IL"} and "search" not in list_url:
                    continue
                polite_delay(args.delay_min, args.delay_max)
                try:
                    listing_hits = scrape_listing_page(page, list_url, site["name"])
                    collected.extend(listing_hits)
                    links = collect_listing_links(page, site, args.max_event_pages)
                except PlaywrightTimeout:
                    LOGGER.warning("Timeout on listing %s", list_url)
                    continue
                except Exception as exc:
                    LOGGER.warning("Could not open listing %s: %s", list_url, exc)
                    continue

                for link in links:
                    if len(collected) >= args.max_events:
                        break
                    polite_delay(args.delay_min, args.delay_max)
                    try:
                        collected.extend(scrape_event_page(page, link, site["name"]))
                    except PlaywrightTimeout:
                        LOGGER.warning("Timeout on event %s", link)
                    except Exception as exc:
                        LOGGER.warning("Skip event %s: %s", link, exc)
                if len(collected) >= args.max_events:
                    break
            if len(collected) >= args.max_events:
                break

        context.close()
        browser.close()

    return dedupe_events(collected)[: args.max_events]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape Israeli ticketing sites for sold-out / fast-selling events.")
    parser.add_argument(
        "--output",
        default=str(Path(__file__).with_name("hot_events_report.csv")),
        help="CSV path (default: scripts/hot_events_report.csv)",
    )
    parser.add_argument("--headed", action="store_true", help="Show the Chromium window.")
    parser.add_argument("--sports-only", action="store_true", help="Prefer football / EuroLeague listing URLs.")
    parser.add_argument("--max-event-pages", type=int, default=12, help="Max event links followed per listing page.")
    parser.add_argument("--max-events", type=int, default=80, help="Stop after this many hot events.")
    parser.add_argument("--delay-min", type=float, default=1.8, help="Minimum pause between page loads (seconds).")
    parser.add_argument("--delay-max", type=float, default=4.2, help="Maximum pause between page loads (seconds).")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    LOGGER.info("Started %s", datetime.now(timezone.utc).isoformat())
    try:
        events = run_scrape(args)
    except KeyboardInterrupt:
        LOGGER.warning("Interrupted")
        return 130
    except Exception as exc:
        LOGGER.error("Scrape failed: %s", exc)
        return 1

    output = Path(args.output)
    write_csv(output, events)
    LOGGER.info("Wrote %s events to %s", len(events), output.resolve())
    if not events:
        LOGGER.info("No sold-out / fast-selling signals on this pass. Try again later or raise --max-event-pages.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
