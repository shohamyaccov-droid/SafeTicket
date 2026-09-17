#!/usr/bin/env python3
"""Read-only report: Eyal Golan ticket files from the critical JSON backup.

Does not touch the database. Prints row/seat, stored file path, and seller.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKUP = (
    Path(__file__).resolve().parents[1]
    / "backend"
    / "critical_backups"
    / "latest_critical_backup.json"
)

NAME_HINTS = ("אייל גולן", "אייל  גולן", "eyal golan", "eyal goland")


def _norm(value) -> str:
    return str(value or "").strip().lower()


def _looks_like_eyal(text) -> bool:
    n = _norm(text)
    if not n:
        return False
    return any(_norm(h) in n for h in NAME_HINTS) or ("גולן" in n and "אייל" in n)


def _file_path(*values) -> str:
    for raw in values:
        s = str(raw or "").strip()
        if s:
            return s
    return "(no file on record)"


def _seat_label(fields: dict) -> tuple[str, str]:
    row = (
        str(fields.get("row") or "").strip()
        or str(fields.get("row_number") or "").strip()
        or str(fields.get("seat_row") or "").strip()
        or "?"
    )
    seat = (
        str(fields.get("seat_number") or "").strip()
        or str(fields.get("seat_numbers") or "").strip()
        or "?"
    )
    return row, seat


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    if not BACKUP.is_file():
        print(f"Backup not found: {BACKUP}")
        return 1

    with BACKUP.open(encoding="utf-8") as fh:
        dump = json.load(fh)

    users = {row["pk"]: row["fields"] for row in dump if row.get("model") == "users.user"}
    artists = {row["pk"]: row["fields"] for row in dump if row.get("model") == "users.artist"}
    events = {row["pk"]: row["fields"] for row in dump if row.get("model") == "users.event"}
    tickets = [row for row in dump if row.get("model") == "users.ticket"]

    eyal_artist_ids = {
        pk for pk, fields in artists.items() if _looks_like_eyal(fields.get("name"))
    }
    eyal_event_ids = {
        pk
        for pk, fields in events.items()
        if fields.get("artist") in eyal_artist_ids or _looks_like_eyal(fields.get("name"))
    }

    print("=" * 72)
    print("Eyal Golan ticket file recovery report (JSON backup only)")
    print(f"Source: {BACKUP}")
    print("=" * 72)
    print()
    print("Artists matched:")
    if not eyal_artist_ids:
        print("  (none)")
    for pk in sorted(eyal_artist_ids):
        print(f"  id={pk}  name={artists[pk].get('name')}")
    print()
    print("Event IDs matched:")
    if not eyal_event_ids:
        print("  (none)")
    for pk in sorted(eyal_event_ids):
        ev = events[pk]
        print(f"  id={pk}  artist={ev.get('artist')}  {ev.get('date')}  {ev.get('name')}")
    print()

    matched = []
    for row in tickets:
        fields = row.get("fields") or {}
        event_id = fields.get("event")
        suspected_orphan = event_id in (None, "") and (
            _looks_like_eyal(fields.get("event_name")) or _looks_like_eyal(fields.get("venue"))
        )
        if event_id in eyal_event_ids or _looks_like_eyal(fields.get("event_name")) or suspected_orphan:
            matched.append((row.get("pk"), fields, suspected_orphan))

    print(f"Tickets matched: {len(matched)}")
    print("-" * 72)

    if not matched:
        print("No matching tickets in this backup.")
        return 0

    for ticket_id, fields, orphan in matched:
        row_n, seat_n = _seat_label(fields)
        seller_id = fields.get("seller")
        seller = users.get(seller_id) or {}
        seller_email = seller.get("email") or seller.get("username") or "(unknown)"
        event_id = fields.get("event")
        ev = events.get(event_id) or {}
        event_label = ev.get("name") or fields.get("event_name") or "(event missing)"
        pdf = _file_path(fields.get("pdf_file"), fields.get("image"))
        receipt = str(fields.get("receipt_file") or "").strip()

        print(f"Ticket #{ticket_id}  status={fields.get('status')}  event={event_id} ({event_label})")
        if orphan:
            print("  NOTE: event FK missing — included because name/venue looks like Eyal Golan")
        print(f"  Row {row_n}, Seat {seat_n}")
        print(f"  File Path / URL: {pdf}")
        if receipt:
            print(f"  Receipt: {receipt}")
        print(f"  Seller ID: {seller_id}  Email: {seller_email}")
        print()

    print("-" * 72)
    print("Done. Database was not modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
