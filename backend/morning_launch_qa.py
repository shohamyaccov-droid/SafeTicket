#!/usr/bin/env python3
"""
Morning Launch QA — extended production checks (human-emulation flows).

Environment (same as qa_production_render_cycle.py):
  QA_PASSWORD (required for qa_bot / admin approve path)
  API_BASE (default https://safeticket-api.onrender.com/api)
  RENDER_API_KEY, RENDER_SERVICE_ID (optional deploy trigger)

Additional:
  QA_USERNAME (default qa_bot) — used for admin approve after new-seller upload
  USE_NEW_SELLER=1 — register a fresh seller, upload PDFs, then approve with QA_USERNAME

Outputs JSON report to stdout; use > morning_report.json to save.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from io import BytesIO

import requests
from pypdf import PdfWriter

# Reuse CSRF + helpers from production cycle
from qa_production_render_cycle import (
    DEFAULT_API,
    TRUSTED_WEB_ORIGIN,
    _fetch_csrf_token,
    _csrf_headers,
    build_csrf_headers,
    session_login,
    session_register_buyer,
    trigger_deploy,
    poll_deploy,
    _one_page_pdf_bytes,
)


def session_register_seller(api_base: str, username: str, email: str, password: str) -> requests.Session | None:
    s = requests.Session()
    s.headers.setdefault("User-Agent", "SafeTicket-MorningQA/1.0")
    csrf = _fetch_csrf_token(s, api_base)
    if not csrf:
        return None
    payload = {
        "username": username,
        "email": email,
        "password": password,
        "password2": password,
        "role": "seller",
    }
    r = s.post(
        f"{api_base}/users/register/",
        json=payload,
        headers=_csrf_headers(s, api_base, csrf),
        timeout=60,
    )
    if r.status_code not in (200, 201):
        return None
    return s


def main() -> int:
    api_base = os.environ.get("API_BASE", DEFAULT_API).rstrip("/")
    qa_user = os.environ.get("QA_USERNAME", "qa_bot")
    qa_pass = os.environ.get("QA_PASSWORD", "")
    render_key = os.environ.get("RENDER_API_KEY", "")
    service_id = os.environ.get("RENDER_SERVICE_ID", "srv-d6u14msr85hc73acc900")
    use_new_seller = os.environ.get("USE_NEW_SELLER", "").lower() in ("1", "true", "yes")

    report: dict = {
        "api_base": api_base,
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "steps": [],
        "errors": [],
        "security": {},
        "cloudinary_pdf_urls": [],
        "pdf_integrity": [],
    }

    if not qa_pass:
        report["errors"].append("QA_PASSWORD not set")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 1

    # Health: events
    try:
        r = requests.get(f"{api_base}/users/events/?format=json", timeout=60)
        ok = r.status_code == 200
        report["steps"].append({"name": "GET /users/events/", "ok": ok, "status": r.status_code})
        if not ok:
            report["errors"].append(f"events: HTTP {r.status_code}")
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 1
        ev = r.json()
        results = ev.get("results") or ev
        if not results:
            report["errors"].append("No events in DB — seed production first")
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 1
        event_id = results[0]["id"]
    except Exception as e:
        report["errors"].append(f"events: {e}")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 1

    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    pdf_bytes = _one_page_pdf_bytes()
    pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()
    report["pdf_integrity"].append({"label": "upload_source_sha256", "sha256": pdf_hash})

    # --- Seller session: new seller or qa_bot ---
    if use_new_seller:
        seller_name = f"morning_seller_{ts}"
        seller_email = f"{seller_name}@example.invalid"
        seller_pw = f"SellerQA{ts[-6:]}!aA1"
        seller = session_register_seller(api_base, seller_name, seller_email, seller_pw)
        if not seller:
            report["errors"].append("New seller registration failed")
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 1
        report["steps"].append({"name": "register new seller", "ok": True, "username": seller_name})
    else:
        seller, login_err = session_login(api_base, qa_user, qa_pass)
        if not seller:
            report["errors"].append(f"Seller login failed: {login_err}")
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 1
        report["steps"].append({"name": "seller login (qa_bot)", "ok": True})

    f1 = f"qa_a_{ts}.pdf"
    f2 = f"qa_b_{ts}.pdf"
    form = {
        "event_id": str(event_id),
        "original_price": "100.00",
        "available_quantity": "2",
        "pdf_files_count": "2",
        "is_together": "true",
        "row_number_0": "QA",
        "seat_number_0": f"S1{ts[-4:]}",
        "row_number_1": "QA",
        "seat_number_1": f"S2{ts[-4:]}",
    }
    files = [
        ("pdf_file_0", (f1, BytesIO(pdf_bytes), "application/pdf")),
        ("pdf_file_1", (f2, BytesIO(pdf_bytes), "application/pdf")),
    ]
    r_up = seller.post(
        f"{api_base}/users/tickets/",
        data=form,
        files=files,
        headers=build_csrf_headers(seller, api_base),
        timeout=120,
    )
    if r_up.status_code != 201:
        report["errors"].append(f"upload: {r_up.status_code} {r_up.text[:800]}")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 1
    t0 = r_up.json()
    tid_first = t0.get("id")
    listing_group_id = t0.get("listing_group_id")
    pdf_url_0 = t0.get("pdf_file_url")
    report["cloudinary_pdf_urls"].append(pdf_url_0)
    report["steps"].append({"name": "upload 2 tickets", "ok": True, "first_ticket_id": tid_first})

    # Reject non-PDF (expect 400, not 500)
    bad = BytesIO(b"not a pdf")
    r_bad = seller.post(
        f"{api_base}/users/tickets/",
        data={
            "event_id": str(event_id),
            "original_price": "10.00",
            "available_quantity": "1",
            "pdf_files_count": "1",
            "row_number_0": "X",
            "seat_number_0": "Y",
        },
        files=[("pdf_file_0", ("fake.pdf", bad, "application/pdf"))],
        headers=build_csrf_headers(seller, api_base),
        timeout=60,
    )
    bad_ok = r_bad.status_code == 400 and "500" not in (r_bad.text or "")
    report["steps"].append(
        {"name": "reject fake PDF (400)", "ok": bad_ok, "status": r_bad.status_code}
    )
    if not bad_ok:
        report["errors"].append(f"non-PDF upload: expected 400, got {r_bad.status_code} {r_bad.text[:200]}")

    # Resolve both ticket ids
    r_list = seller.get(f"{api_base}/users/tickets/", timeout=60)
    ids_in_group = []
    if r_list.status_code == 200:
        data = r_list.json()
        arr = data.get("results") if isinstance(data, dict) else data
        for row in arr or []:
            if str(row.get("listing_group_id")) == str(listing_group_id):
                ids_in_group.append(row.get("id"))
    ids_in_group = sorted(set(ids_in_group))
    if len(ids_in_group) < 2:
        report["errors"].append(f"Could not resolve 2 ticket ids in group; got {ids_in_group}")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 1
    tid_a, tid_b = ids_in_group[0], ids_in_group[1]

    # Approve with qa_bot (admin)
    admin, aerr = session_login(api_base, qa_user, qa_pass)
    if not admin:
        report["errors"].append(f"Admin login for approve failed: {aerr}")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 1
    for tid in (tid_a, tid_b):
        r_ap = admin.post(
            f"{api_base}/users/admin/tickets/{tid}/approve/",
            json={},
            headers=build_csrf_headers(admin, api_base),
            timeout=60,
        )
        if r_ap.status_code != 200:
            report["errors"].append(f"approve {tid}: {r_ap.status_code} {r_ap.text[:300]}")
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 1
    report["steps"].append({"name": "admin approve x2", "ok": True, "ticket_ids": [tid_a, tid_b]})

    # Anonymous ticket detail (tickets are active now): no raw Cloudinary URL; has_pdf_file true
    try:
        r_pub = requests.get(f"{api_base}/users/tickets/{tid_first}/", timeout=30)
        body = r_pub.json() if r_pub.status_code == 200 else {}
        report["security"]["anonymous_ticket_detail"] = {
            "status": r_pub.status_code,
            "pdf_file_url": body.get("pdf_file_url"),
            "has_pdf_file": body.get("has_pdf_file"),
        }
        u = body.get("pdf_file_url") or ""
        if u and ("cloudinary.com" in u or "res.cloudinary.com" in u):
            report["errors"].append("Security: anonymous ticket detail leaked raw Cloudinary URL")
    except Exception as e:
        report["security"]["anonymous_ticket_detail_error"] = str(e)

    r_d = admin.get(f"{api_base}/users/tickets/{tid_b}/", timeout=60)
    if r_d.status_code == 200:
        pdf1 = r_d.json().get("pdf_file_url")
        if pdf1 and pdf1 not in report["cloudinary_pdf_urls"]:
            report["cloudinary_pdf_urls"].append(pdf1)

    # Buyer flow
    buyer_name = f"morning_buyer_{ts}"
    buyer_email = f"{buyer_name}@example.invalid"
    buyer_pw = f"BuyerQA{ts[-6:]}!aA1"
    buyer = session_register_buyer(api_base, buyer_name, buyer_email, buyer_pw)
    if not buyer:
        report["errors"].append("Buyer register failed")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 1
    report["steps"].append({"name": "buyer register", "ok": True, "username": buyer_name})

    ref_id = tid_a
    unit = 100.0
    expected_unit = math.ceil(unit * 1.10)
    total_amount = expected_unit * 2

    r_res = buyer.post(
        f"{api_base}/users/tickets/{ref_id}/reserve/",
        json={},
        headers=build_csrf_headers(buyer, api_base),
        timeout=60,
    )
    if r_res.status_code not in (200, 201):
        report["errors"].append(f"reserve: {r_res.status_code} {r_res.text[:300]}")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 1

    r_pay = buyer.post(
        f"{api_base}/users/payments/simulate/",
        json={
            "ticket_id": ref_id,
            "amount": float(total_amount),
            "quantity": 2,
            "listing_group_id": listing_group_id,
            "timestamp": int(time.time() * 1000),
        },
        headers=build_csrf_headers(buyer, api_base),
        timeout=60,
    )
    if r_pay.status_code != 200:
        report["errors"].append(f"payment: {r_pay.status_code} {r_pay.text[:400]}")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 1

    r_ord = buyer.post(
        f"{api_base}/users/orders/",
        json={
            "ticket": ref_id,
            "total_amount": total_amount,
            "quantity": 2,
            "event_name": t0.get("event_name") or "QA",
            "listing_group_id": listing_group_id,
        },
        headers=build_csrf_headers(buyer, api_base),
        timeout=60,
    )
    if r_ord.status_code != 201:
        report["errors"].append(f"order: {r_ord.status_code} {r_ord.text[:400]}")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 1
    report["steps"].append({"name": "checkout", "ok": True, "order_id": r_ord.json().get("id")})

    # Profile / orders (My Tickets API)
    r_prof = buyer.get(f"{api_base}/users/profile/", timeout=60)
    report["steps"].append(
        {
            "name": "GET profile (orders)",
            "ok": r_prof.status_code == 200,
            "status": r_prof.status_code,
            "order_count": len((r_prof.json() or {}).get("orders") or []) if r_prof.status_code == 200 else 0,
        }
    )

    # Downloads + integrity
    for tid in (tid_a, tid_b):
        r_pdf = buyer.get(f"{api_base}/users/tickets/{tid}/download_pdf/", timeout=60)
        ok_dl = r_pdf.status_code == 200 and r_pdf.content.startswith(b"%PDF")
        h2 = hashlib.sha256(r_pdf.content).hexdigest() if ok_dl else None
        report["pdf_integrity"].append({"ticket_id": tid, "download_ok": ok_dl, "sha256": h2})
        if ok_dl and h2 != pdf_hash:
            report["errors"].append(f"PDF byte mismatch ticket {tid}")
        if not ok_dl:
            detail = (r_pdf.text or "")[:500]
            report.setdefault("download_failures", []).append(
                {"ticket_id": tid, "status": r_pdf.status_code, "body_preview": detail}
            )
            report["errors"].append(f"download {tid}: HTTP {r_pdf.status_code}")

    # Optional: unauthenticated HEAD to any raw https URL that looks like Cloudinary (informational)
    for u in list(report["cloudinary_pdf_urls"]):
        if u and isinstance(u, str) and "cloudinary" in u.lower():
            try:
                h = requests.head(u, timeout=20, allow_redirects=True)
                report.setdefault("cloudinary_head_unauth", []).append(
                    {"url": u[:120], "status": h.status_code}
                )
            except Exception as e:
                report.setdefault("cloudinary_head_unauth", []).append({"url": u[:120], "error": str(e)})

    # Render deploy (optional)
    if render_key:
        try:
            dep = trigger_deploy(render_key, service_id)
            did = dep.get("id")
            report["deploy"] = {"triggered": True, "id": did, "initial_status": dep.get("status")}
            final = poll_deploy(render_key, service_id, did, timeout_sec=1200)
            report["deploy"]["final_status"] = final
            report["steps"].append({"name": "render deploy", "ok": final == "live", "status": final})
        except Exception as e:
            report["errors"].append(f"render deploy: {e}")
    else:
        report["steps"].append({"name": "render deploy", "skipped": True, "reason": "RENDER_API_KEY not set"})

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if not report["errors"] else 1


if __name__ == "__main__":
    sys.exit(main())
