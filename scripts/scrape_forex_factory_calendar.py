#!/usr/bin/env python3
"""
Scrape Forex Factory economic calendar history with Playwright.

Filters to USD currency and High Impact (red folder) events only.
Extracts Date, Time, Currency, Event Name, and Impact into a CSV file.

Usage:
    pip install -r requirements-forex-scraper.txt
    playwright install chromium
    python scrape_forex_factory_calendar.py
    python scrape_forex_factory_calendar.py --start 2019-01 --end 2026-05 --output usd_high_impact.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dateutil.relativedelta import relativedelta
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

BASE_URL = "https://www.forexfactory.com/calendar"
MONTH_SLUGS = (
    "jan",
    "feb",
    "mar",
    "apr",
    "may",
    "jun",
    "jul",
    "aug",
    "sep",
    "oct",
    "nov",
    "dec",
)
CSV_COLUMNS = ("Date", "Time", "Currency", "Event Name", "Impact")
OUTPUT_TIMEZONE = ZoneInfo("America/New_York")
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def parse_month(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m")
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid month {value!r}; expected YYYY-MM (e.g. 2019-01)."
        ) from exc


def iter_months(start: datetime, end: datetime):
    current = datetime(start.year, start.month, 1)
    last = datetime(end.year, end.month, 1)
    while current <= last:
        yield current
        current += relativedelta(months=1)


def month_url(month: datetime) -> str:
    slug = MONTH_SLUGS[month.month - 1]
    return f"{BASE_URL}?month={slug}.{month.year}"


def normalize_date(raw_date: str) -> str:
    return datetime.strptime(raw_date.strip(), "%b %d, %Y").strftime("%Y-%m-%d")


def extract_calendar_state(page) -> dict | None:
    return page.evaluate(
        """() => {
            if (!window.calendarComponentStates) return null;
            const state = window.calendarComponentStates[1];
            return state || null;
        }"""
    )


def expand_month_if_needed(page) -> None:
    more = page.get_by_text("More", exact=True)
    if more.count() == 0:
        return
    try:
        more.first.click(timeout=5000)
        time.sleep(1.5)
    except PlaywrightError:
        pass


def format_event_datetime(dateline: int | float | str | None, fallback_date: str, fallback_time: str) -> tuple[str, str]:
    if dateline:
        dt = datetime.fromtimestamp(int(dateline), tz=OUTPUT_TIMEZONE)
        return dt.strftime("%Y-%m-%d"), dt.strftime("%I:%M%p").lstrip("0").lower()

    return normalize_date(fallback_date), fallback_time.strip()


def parse_events(state: dict, currency: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for day in state.get("days", []):
        for event in day.get("events", []):
            if event.get("currency") != currency:
                continue
            if event.get("impactName") != "high":
                continue

            event_date, event_time = format_event_datetime(
                event.get("dateline"),
                event.get("date", ""),
                event.get("timeLabel", ""),
            )

            rows.append(
                {
                    "Date": event_date,
                    "Time": event_time,
                    "Currency": event.get("currency", currency),
                    "Event Name": event.get("name", "").strip(),
                    "Impact": event.get("impactTitle", "High Impact Expected").strip(),
                    "_event_id": str(event.get("id", "")),
                    "_sort_key": str(event.get("dateline", "")),
                }
            )
    return rows


def wait_for_calendar_state(page, timeout_ms: int = 60_000) -> dict:
    page.wait_for_function(
        """() => {
            return window.calendarComponentStates
                && window.calendarComponentStates[1]
                && Array.isArray(window.calendarComponentStates[1].days);
        }""",
        timeout=timeout_ms,
    )
    state = extract_calendar_state(page)
    if state is None:
        raise RuntimeError("Calendar state disappeared after load.")
    return state


def scrape_month(
    page,
    month: datetime,
    currency: str,
    wait_seconds: float,
    max_attempts: int = 3,
) -> list[dict[str, str]]:
    label = month.strftime("%Y-%m")
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            page.goto(month_url(month), wait_until="domcontentloaded", timeout=120_000)
            time.sleep(wait_seconds)
            state = wait_for_calendar_state(page)
            expand_month_if_needed(page)
            state = extract_calendar_state(page) or state
            return parse_events(state, currency)
        except Exception as exc:
            last_error = exc
            if attempt < max_attempts:
                time.sleep(wait_seconds * attempt)
            continue

    raise RuntimeError(f"Calendar data not found for {label}.") from last_error


def dedupe_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for row in rows:
        event_id = row.get("_event_id")
        key = event_id or "|".join(row[col] for col in CSV_COLUMNS)
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def sort_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(
        rows,
        key=lambda row: (row["Date"], row["Time"], row["Event Name"]),
    )


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Scrape Forex Factory calendar history for USD high-impact events "
            "and save the results to CSV."
        )
    )
    parser.add_argument("--start", type=parse_month, default=parse_month("2019-01"))
    parser.add_argument("--end", type=parse_month, default=parse_month("2026-05"))
    parser.add_argument(
        "--currency",
        default="USD",
        help="Currency code to keep (default: USD).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("forex_factory_usd_high_impact.csv"),
        help="Output CSV path.",
    )
    parser.add_argument(
        "--wait-seconds",
        type=float,
        default=5.0,
        help="Seconds to wait after each page load (default: 5).",
    )
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=2.0,
        help="Pause between month requests (default: 2).",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run the browser with a visible window.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.start > args.end:
        print("Error: --start must be on or before --end.", file=sys.stderr)
        return 1

    months = list(iter_months(args.start, args.end))
    all_rows: list[dict[str, str]] = []

    print(
        f"Scraping {len(months)} month(s) "
        f"({args.start.strftime('%Y-%m')} to {args.end.strftime('%Y-%m')}) "
        f"for {args.currency} high-impact events...",
        flush=True,
    )

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=not args.headed,
            args=["--disable-blink-features=AutomationControlled"],
        )
        try:
            for index, month in enumerate(months, start=1):
                label = month.strftime("%Y-%m")
                context = browser.new_context(user_agent=USER_AGENT)
                page = context.new_page()
                try:
                    month_rows = scrape_month(
                        page,
                        month,
                        args.currency.upper(),
                        args.wait_seconds,
                    )
                except Exception as exc:
                    print(f"[{index}/{len(months)}] {label} FAILED: {exc}", file=sys.stderr)
                    raise
                finally:
                    context.close()

                all_rows.extend(month_rows)
                print(f"[{index}/{len(months)}] {label}: {len(month_rows)} events", flush=True)

                if index < len(months):
                    time.sleep(args.delay_seconds)
        finally:
            browser.close()

    cleaned = sort_rows(dedupe_rows(all_rows))
    write_csv(args.output, cleaned)

    print(f"\nSaved {len(cleaned)} rows to {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
