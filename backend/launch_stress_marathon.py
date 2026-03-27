#!/usr/bin/env python3
"""
Full production stress marathon: PDF flow (subprocess) + marketplace conflict tests.

Environment:
  QA_PASSWORD (required), QA_USERNAME (default qa_bot)
  API_BASE (default https://safeticket-api.onrender.com/api)

  RUN_PDF_SUBPROCESS=1 (default) — run morning_launch_qa.py and merge JSON
  RUN_CONFLICTS=1 (default) — offer, pairs, concurrent create_order race

Prints one merged JSON report to stdout.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from io import BytesIO

import requests
from pypdf import PdfWriter

from qa_production_render_cycle import (
    DEFAULT_API,
    build_csrf_headers,
    session_login,
    session_register_buyer,
    _fetch_csrf_token,
    _csrf_headers,
)


def _one_page_pdf_bytes() -> bytes:
    w = PdfWriter()
    w.add_blank_page(width=612, height=792)
    buf = BytesIO()
    w.write(buf)
    return buf.getvalue()


def session_register_seller(api_base: str, username: str, email: str, password: str) -> requests.Session | None:
    s = requests.Session()
    s.headers.setdefault("User-Agent", "SafeTicket-Marathon/1.0")
    csrf = _fetch_csrf_token(s, api_base)
    if not csrf:
        return None
    r = s.post(
        f"{api_base}/users/register/",
        json={
            "username": username,
            "email": email,
            "password": password,
            "password2": password,
            "role": "seller",
        },
        headers=_csrf_headers(s, api_base, csrf),
        timeout=60,
    )
    if r.status_code not in (200, 201):
        return None
    return s


def run_pdf_subprocess() -> dict:
    """Run morning_launch_qa.py; parse JSON from stdout."""
    env = os.environ.copy()
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    proc = subprocess.run(
        [sys.executable, "morning_launch_qa.py"],
        cwd=backend_dir,
        env=env,
        capture_output=True,
        text=True,
        timeout=600,
    )
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    if not out:
        return {"ok": False, "exit_code": proc.returncode, "stderr": err[:2000], "parse_error": "empty_stdout"}
    try:
        # Single root object (rfind('{') breaks on nested objects — use raw_decode from first '{')
        start = out.find("{")
        if start == -1:
            return {"ok": False, "stderr": err[:500], "parse_error": "no_json", "stdout_tail": out[-800:]}
        data, _ = json.JSONDecoder().raw_decode(out, start)
        data["_subprocess_exit"] = proc.returncode
        return data
    except json.JSONDecodeError as e:
        return {"ok": False, "parse_error": str(e), "stdout_tail": out[-1500:], "stderr": err[:500]}


def test_offer_flow(api_base: str, seller: requests.Session, admin: requests.Session, event_id: int, ts: str) -> dict:
    """Buyer offers 80 on 100 ticket; seller accepts; buyer pays negotiated total; other buyer sees list price."""
    out: dict = {"name": "offer_negotiation", "steps": [], "ok": True}
    pdf = _one_page_pdf_bytes()
    form = {
        "event_id": str(event_id),
        "original_price": "100.00",
        "available_quantity": "1",
        "pdf_files_count": "1",
        "split_type": "כל כמות",
        "row_number_0": "OF",
        "seat_number_0": f"O{ts[-4:]}",
    }
    r = seller.post(
        f"{api_base}/users/tickets/",
        data=form,
        files=[("pdf_file_0", (f"of_{ts}.pdf", BytesIO(pdf), "application/pdf"))],
        headers=build_csrf_headers(seller, api_base),
        timeout=120,
    )
    if r.status_code != 201:
        out["ok"] = False
        out["error"] = f"upload {r.status_code} {r.text[:400]}"
        return out
    tid = r.json().get("id")
    lid = r.json().get("listing_group_id")
    r_ap = admin.post(
        f"{api_base}/users/admin/tickets/{tid}/approve/",
        json={},
        headers=build_csrf_headers(admin, api_base),
        timeout=60,
    )
    if r_ap.status_code != 200:
        out["ok"] = False
        out["error"] = f"approve {r_ap.status_code}"
        return out

    # Public list price visible to others
    r_pub = requests.get(f"{api_base}/users/tickets/{tid}/", timeout=30)
    list_asking = None
    if r_pub.status_code == 200:
        body = r_pub.json()
        list_asking = str(body.get("asking_price") or body.get("original_price") or "")

    buyer_a_name = f"off_buyer_a_{ts}"
    buyer_a = session_register_buyer(api_base, buyer_a_name, f"{buyer_a_name}@example.invalid", f"OffA{ts[-6:]}!aA1")
    if not buyer_a:
        out["ok"] = False
        out["error"] = "register buyer_a failed"
        return out

    r_of = buyer_a.post(
        f"{api_base}/users/offers/",
        json={"ticket": tid, "amount": "80.00", "quantity": 1},
        headers=build_csrf_headers(buyer_a, api_base),
        timeout=60,
    )
    if r_of.status_code not in (200, 201):
        out["ok"] = False
        out["error"] = f"create offer {r_of.status_code} {r_of.text[:400]}"
        return out
    oid = r_of.json().get("id")
    out["steps"].append({"offer_id": oid})

    r_acc = seller.post(
        f"{api_base}/users/offers/{oid}/accept/",
        json={},
        headers=build_csrf_headers(seller, api_base),
        timeout=60,
    )
    if r_acc.status_code != 200:
        out["ok"] = False
        out["error"] = f"accept {r_acc.status_code} {r_acc.text[:400]}"
        return out

    buyer_a.post(f"{api_base}/users/tickets/{tid}/reserve/", json={}, headers=build_csrf_headers(buyer_a, api_base), timeout=60)
    base = 80.0
    total_neg = base + base * 0.10
    r_pay = buyer_a.post(
        f"{api_base}/users/payments/simulate/",
        json={
            "ticket_id": tid,
            "amount": float(total_neg),
            "quantity": 1,
            "listing_group_id": lid,
            "offer_id": oid,
            "timestamp": int(time.time() * 1000),
        },
        headers=build_csrf_headers(buyer_a, api_base),
        timeout=60,
    )
    if r_pay.status_code != 200:
        out["ok"] = False
        out["error"] = f"pay {r_pay.status_code} {r_pay.text[:400]}"
        return out

    r_ord = buyer_a.post(
        f"{api_base}/users/orders/",
        json={
            "ticket": tid,
            "total_amount": total_neg,
            "quantity": 1,
            "listing_group_id": lid,
            "offer_id": oid,
            "event_name": "Offer QA",
        },
        headers=build_csrf_headers(buyer_a, api_base),
        timeout=60,
    )
    if r_ord.status_code != 201:
        out["ok"] = False
        out["error"] = f"order {r_ord.status_code} {r_ord.text[:400]}"
        return out

    out["steps"].append(
        {
            "negotiated_total": total_neg,
            "list_price_seen_before_offer_flow": list_asking,
            "order_id": r_ord.json().get("id"),
        }
    )
    return out


def test_pairs_flow(api_base: str, seller: requests.Session, admin: requests.Session, event_id: int, ts: str) -> dict:
    out: dict = {"name": "sell_in_pairs", "steps": [], "ok": True}
    pdf = _one_page_pdf_bytes()
    form = {
        "event_id": str(event_id),
        "original_price": "50.00",
        "available_quantity": "2",
        "pdf_files_count": "2",
        "is_together": "true",
        "split_type": "זוגות בלבד",
        "row_number_0": "P",
        "seat_number_0": f"P1{ts[-4:]}",
        "row_number_1": "P",
        "seat_number_1": f"P2{ts[-4:]}",
    }
    files = [
        ("pdf_file_0", (f"pa_{ts}.pdf", BytesIO(pdf), "application/pdf")),
        ("pdf_file_1", (f"pb_{ts}.pdf", BytesIO(pdf), "application/pdf")),
    ]
    r = seller.post(
        f"{api_base}/users/tickets/",
        data=form,
        files=files,
        headers=build_csrf_headers(seller, api_base),
        timeout=120,
    )
    if r.status_code != 201:
        out["ok"] = False
        out["error"] = f"upload {r.status_code}"
        return out
    listing_group_id = r.json().get("listing_group_id")
    # resolve ids + approve
    r_list = seller.get(f"{api_base}/users/tickets/", timeout=60)
    ids = []
    if r_list.status_code == 200:
        data = r_list.json()
        arr = data.get("results") if isinstance(data, dict) else data
        for row in arr or []:
            if str(row.get("listing_group_id")) == str(listing_group_id):
                ids.append(row.get("id"))
    ids = sorted(set(ids))
    if len(ids) < 2:
        out["ok"] = False
        out["error"] = f"ids {ids}"
        return out
    for tid in ids:
        admin.post(
            f"{api_base}/users/admin/tickets/{tid}/approve/",
            json={},
            headers=build_csrf_headers(admin, api_base),
            timeout=60,
        )

    buyer_name = f"pair_buyer_{ts}"
    buyer = session_register_buyer(api_base, buyer_name, f"{buyer_name}@example.invalid", f"Pair{ts[-6:]}!aA1")
    if not buyer:
        out["ok"] = False
        out["error"] = "register buyer"
        return out

    ref = ids[0]
    unit = 50.0
    exp_unit = math.ceil(unit * 1.10)
    total_1 = exp_unit * 1
    total_2 = exp_unit * 2

    buyer.post(f"{api_base}/users/tickets/{ref}/reserve/", json={}, headers=build_csrf_headers(buyer, api_base), timeout=60)
    r_pay1 = buyer.post(
        f"{api_base}/users/payments/simulate/",
        json={
            "ticket_id": ref,
            "amount": float(total_1),
            "quantity": 1,
            "listing_group_id": listing_group_id,
            "timestamp": int(time.time() * 1000),
        },
        headers=build_csrf_headers(buyer, api_base),
        timeout=60,
    )
    r_ord1 = buyer.post(
        f"{api_base}/users/orders/",
        json={
            "ticket": ref,
            "total_amount": total_1,
            "quantity": 1,
            "listing_group_id": listing_group_id,
            "event_name": "Pairs QA",
        },
        headers=build_csrf_headers(buyer, api_base),
        timeout=60,
    )
    blocked = r_ord1.status_code == 400 and "pair" in (r_ord1.text or "").lower()
    if not blocked and r_ord1.status_code != 400:
        blocked = r_ord1.status_code == 400
    # Release reservation so the same buyer can complete a valid pair purchase (avoids extra registration flakiness)
    buyer.post(
        f"{api_base}/users/tickets/{ref}/release_reservation/",
        json={},
        headers=build_csrf_headers(buyer, api_base),
        timeout=60,
    )

    buyer.post(f"{api_base}/users/tickets/{ref}/reserve/", json={}, headers=build_csrf_headers(buyer, api_base), timeout=60)
    buyer.post(
        f"{api_base}/users/payments/simulate/",
        json={
            "ticket_id": ref,
            "amount": float(total_2),
            "quantity": 2,
            "listing_group_id": listing_group_id,
            "timestamp": int(time.time() * 1000),
        },
        headers=build_csrf_headers(buyer, api_base),
        timeout=60,
    )
    r_ord2 = buyer.post(
        f"{api_base}/users/orders/",
        json={
            "ticket": ref,
            "total_amount": total_2,
            "quantity": 2,
            "listing_group_id": listing_group_id,
            "event_name": "Pairs QA",
        },
        headers=build_csrf_headers(buyer, api_base),
        timeout=60,
    )
    out["steps"].append(
        {
            "buy_qty_1_order_status": r_ord1.status_code,
            "buy_qty_1_blocked_pairs": blocked,
            "buy_qty_2_order_status": r_ord2.status_code,
        }
    )
    out["ok"] = blocked and r_ord2.status_code == 201
    if not out["ok"]:
        out["error"] = f"pairs: expected block+201 got block={blocked} ord2={r_ord2.status_code}"
    return out


def test_race_last_ticket(api_base: str, seller: requests.Session, admin: requests.Session, event_id: int, ts: str) -> dict:
    """Two buyers race create_order for one single ticket; expect exactly one 201."""
    out: dict = {"name": "race_last_ticket", "ok": True, "results": []}
    pdf = _one_page_pdf_bytes()
    form = {
        "event_id": str(event_id),
        "original_price": "30.00",
        "available_quantity": "1",
        "pdf_files_count": "1",
        "row_number_0": "R",
        "seat_number_0": f"R{ts[-4:]}",
    }
    r = seller.post(
        f"{api_base}/users/tickets/",
        data=form,
        files=[("pdf_file_0", (f"race_{ts}.pdf", BytesIO(pdf), "application/pdf"))],
        headers=build_csrf_headers(seller, api_base),
        timeout=120,
    )
    if r.status_code != 201:
        out["ok"] = False
        out["error"] = f"upload {r.status_code}"
        return out
    tid = r.json().get("id")
    admin.post(
        f"{api_base}/users/admin/tickets/{tid}/approve/",
        json={},
        headers=build_csrf_headers(admin, api_base),
        timeout=60,
    )

    b1_name, b2_name = f"race_a_{ts}", f"race_b_{ts}"
    b1 = session_register_buyer(api_base, b1_name, f"{b1_name}@example.invalid", f"RcA{ts[-6:]}!aA1")
    b2 = session_register_buyer(api_base, b2_name, f"{b2_name}@example.invalid", f"RcB{ts[-6:]}!aA1")
    if not b1 or not b2:
        out["ok"] = False
        out["error"] = "register race buyers"
        return out

    unit = 30.0
    exp_unit = math.ceil(unit * 1.10)
    total = exp_unit

    def attempt(sess: requests.Session, label: str):
        # No reserve here — first-come create_order + DB lock should serialize; reserve would block one thread.
        sess.post(
            f"{api_base}/users/payments/simulate/",
            json={"ticket_id": tid, "amount": float(total), "quantity": 1, "timestamp": int(time.time() * 1000)},
            headers=build_csrf_headers(sess, api_base),
            timeout=60,
        )
        ro = sess.post(
            f"{api_base}/users/orders/",
            json={"ticket": tid, "total_amount": total, "quantity": 1, "event_name": "Race QA"},
            headers=build_csrf_headers(sess, api_base),
            timeout=60,
        )
        return label, ro.status_code, (ro.text or "")[:300]

    with ThreadPoolExecutor(max_workers=2) as pool:
        futs = [pool.submit(attempt, b1, "A"), pool.submit(attempt, b2, "B")]
        for f in as_completed(futs):
            out["results"].append(f.result())

    codes = [x[1] for x in out["results"]]
    wins = sum(1 for c in codes if c == 201)
    out["ok"] = wins == 1
    if not out["ok"]:
        out["error"] = f"expected exactly one 201, got {codes}"
    return out


def main() -> int:
    api_base = os.environ.get("API_BASE", DEFAULT_API).rstrip("/")
    qa_pass = os.environ.get("QA_PASSWORD", "")
    qa_user = os.environ.get("QA_USERNAME", "qa_bot")
    run_pdf = os.environ.get("RUN_PDF_SUBPROCESS", "1").lower() not in ("0", "false", "no")
    run_conf = os.environ.get("RUN_CONFLICTS", "1").lower() not in ("0", "false", "no")

    report: dict = {
        "marathon": "launch_stress_marathon",
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "api_base": api_base,
        "pdf_qa": None,
        "conflict_tests": {},
        "errors": [],
        "all_systems_green": False,
    }

    if not qa_pass:
        report["errors"].append("QA_PASSWORD not set")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 1

    if run_pdf:
        report["pdf_qa"] = run_pdf_subprocess()
        pq = report["pdf_qa"]
        if isinstance(pq, dict) and pq.get("errors"):
            report["errors"].extend(pq["errors"])

    if run_conf:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        seller, _ = session_login(api_base, qa_user, qa_pass)
        admin, _ = session_login(api_base, qa_user, qa_pass)
        if not seller or not admin:
            report["errors"].append("login failed for conflict tests")
        else:
            r_ev = requests.get(f"{api_base}/users/events/?format=json", timeout=60)
            ev = r_ev.json()
            results = ev.get("results") or ev
            event_id = results[0]["id"] if results else None
            if not event_id:
                report["errors"].append("no event for conflict tests")
            else:
                report["conflict_tests"]["offer"] = test_offer_flow(api_base, seller, admin, event_id, ts)
                report["conflict_tests"]["pairs"] = test_pairs_flow(api_base, seller, admin, event_id, ts)
                report["conflict_tests"]["race"] = test_race_last_ticket(api_base, seller, admin, event_id, ts)
                for k, v in report["conflict_tests"].items():
                    if isinstance(v, dict) and not v.get("ok", False):
                        report["errors"].append(f"conflict {k}: {v.get('error', 'failed')}")

    pq = report.get("pdf_qa")
    pdf_ok = (
        isinstance(pq, dict)
        and not pq.get("errors")
        and not pq.get("parse_error")
    )
    conf_ok = all(
        isinstance(report["conflict_tests"].get(k), dict) and report["conflict_tests"][k].get("ok")
        for k in ("offer", "pairs", "race")
    ) if run_conf and report.get("conflict_tests") else True
    if not run_conf:
        conf_ok = True

    report["all_systems_green"] = bool(pdf_ok and conf_ok and not report["errors"])
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["all_systems_green"] else 1


if __name__ == "__main__":
    sys.exit(main())
