#!/usr/bin/env python3
"""
Production QA + Render deploy verification.
Reads secrets from environment (never hardcode):
  RENDER_API_KEY, RENDER_SERVICE_ID (optional, default below)
  QA_USERNAME (default qa_bot), QA_PASSWORD
  API_BASE (default https://safeticket-api.onrender.com/api)

Run (PowerShell):
  $env:RENDER_API_KEY="..."; $env:QA_PASSWORD="..."; python qa_production_render_cycle.py
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from io import BytesIO

import requests
from pypdf import PdfWriter

# Defaults for public endpoints / seed user username
DEFAULT_API = "https://safeticket-api.onrender.com/api"
DEFAULT_SERVICE = "srv-d6u14msr85hc73acc900"
# Must match backend CSRF_TRUSTED_ORIGINS for API POSTs (browser sends these; we mimic for server-side QA).
TRUSTED_WEB_ORIGIN = "https://safeticket-web.onrender.com"


def _one_page_pdf_bytes() -> bytes:
    """Valid single-page PDF (matches upload validation / PyPDF reads on server)."""
    w = PdfWriter()
    w.add_blank_page(width=612, height=792)
    buf = BytesIO()
    w.write(buf)
    return buf.getvalue()


def _fetch_csrf_token(session: requests.Session, api_base: str) -> str | None:
    r = session.get(f"{api_base}/users/csrf/", timeout=60)
    if r.status_code != 200:
        return None
    try:
        return (r.json() or {}).get("csrfToken") or session.cookies.get("csrftoken")
    except Exception:
        return session.cookies.get("csrftoken")


def _csrf_headers(session: requests.Session, api_base: str, csrf_token: str | None) -> dict:
    token = csrf_token or session.cookies.get("csrftoken") or ""
    return {
        "Referer": f"{TRUSTED_WEB_ORIGIN}/",
        "Origin": TRUSTED_WEB_ORIGIN,
        "X-CSRFToken": token,
    }


def build_csrf_headers(session: requests.Session, api_base: str) -> dict:
    tok = _fetch_csrf_token(session, api_base)
    return _csrf_headers(session, api_base, tok)


def confirm_pending_order_payment(
    session: requests.Session, api_base: str, create_order_body: dict
) -> tuple[int, object]:
    """
    Finalize POST /users/orders/ (pending_payment) using mock PSP ack + payment_confirm_token.
    Required for buyer PDF download and profile orders (paid/completed only).
    """
    oid = create_order_body.get("id")
    tok = (create_order_body.get("payment_confirm_token") or "").strip()
    if oid is None or not tok:
        return 0, {"error": "missing order id or payment_confirm_token in create-order response"}
    r = session.post(
        f"{api_base.rstrip('/')}/users/orders/{int(oid)}/confirm-payment/",
        json={"mock_payment_ack": True, "payment_confirm_token": tok},
        headers=build_csrf_headers(session, api_base),
        timeout=120,
    )
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, r.text[:2000] if r.text else None


def session_login(api_base: str, username: str, password: str) -> tuple[requests.Session | None, str | None]:
    """Returns (session, error_detail). On failure session is None."""
    s = requests.Session()
    s.headers.setdefault("User-Agent", "TradeTix-QA/1.0")
    csrf = _fetch_csrf_token(s, api_base)
    if not csrf:
        return None, "csrf_fetch_failed"
    r = s.post(
        f"{api_base}/users/login/",
        json={"username": username, "password": password},
        headers=_csrf_headers(s, api_base, csrf),
        timeout=60,
    )
    if r.status_code != 200:
        try:
            detail = (r.json() or {}).get("detail", r.text[:200])
        except Exception:
            detail = r.text[:200]
        return None, f"HTTP {r.status_code}: {detail}"
    return s, None


def session_register_buyer(api_base: str, username: str, email: str, password: str) -> requests.Session | None:
    s = requests.Session()
    s.headers.setdefault("User-Agent", "TradeTix-QA/1.0")
    csrf = _fetch_csrf_token(s, api_base)
    if not csrf:
        return None
    payload = {
        "username": username,
        "email": email,
        "password": password,
        "password2": password,
        "role": "buyer",
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


def session_register_seller(api_base: str, username: str, email: str, password: str) -> requests.Session | None:
    s = requests.Session()
    s.headers.setdefault("User-Agent", "TradeTix-QA/1.0")
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


def trigger_deploy(api_key: str, service_id: str) -> dict:
    r = requests.post(
        f"https://api.render.com/v1/services/{service_id}/deploys",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        json={"clearCache": "do_not_clear"},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()


def poll_deploy(api_key: str, service_id: str, deploy_id: str, timeout_sec: int = 1200) -> str:
    url = f"https://api.render.com/v1/services/{service_id}/deploys/{deploy_id}"
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    deadline = time.time() + timeout_sec
    last = ""
    while time.time() < deadline:
        r = requests.get(url, headers=headers, timeout=60)
        r.raise_for_status()
        data = r.json()
        last = data.get("status") or ""
        if last in ("live", "deactivated", "canceled", "build_failed", "update_failed"):
            return last
        time.sleep(10)
    return last or "timeout"


def main() -> int:
    api_base = os.environ.get("API_BASE", DEFAULT_API).rstrip("/")
    qa_user = os.environ.get("QA_USERNAME", "qa_bot")
    qa_pass = os.environ.get("QA_PASSWORD", "")
    render_key = os.environ.get("RENDER_API_KEY", "")
    service_id = os.environ.get("RENDER_SERVICE_ID", DEFAULT_SERVICE)

    report: dict = {
        "api_base": api_base,
        "steps": [],
        "errors": [],
        "cloudinary_pdf_urls": [],
        "deploy": None,
    }

    if not qa_pass:
        report["errors"].append("QA_PASSWORD not set")
        print(json.dumps(report, indent=2))
        return 1

    # --- Health: events (public) ---
    try:
        r = requests.get(f"{api_base}/users/events/?format=json", timeout=60)
        ok = r.status_code == 200
        report["steps"].append({"name": "GET /users/events/", "ok": ok, "status": r.status_code})
        if not ok:
            report["errors"].append(f"events: HTTP {r.status_code}")
            print(json.dumps(report, indent=2))
            return 1
        ev = r.json()
        results = ev if isinstance(ev, list) else (ev.get("results") or [])
        if not results:
            report["errors"].append("No events in DB — seed production first")
            print(json.dumps(report, indent=2))
            return 1
        event_id = results[0]["id"]
    except Exception as e:
        report["errors"].append(f"events: {e}")
        print(json.dumps(report, indent=2))
        return 1

    # --- Seller: login (qa_bot must exist — run seed_production.py on the Render DB first) ---
    seller, login_err = session_login(api_base, qa_user, qa_pass)
    if not seller:
        report["errors"].append(
            f"Seller login failed: {login_err}. "
            "Provision qa_bot with seed_production.py (see backend/seed_production.py) on production, then re-run."
        )
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 1
    report["steps"].append({"name": "seller login", "ok": True})

    # --- Upload 2 PDFs (one listing group, qty 2) ---
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    f1 = f"qa_a_{ts}.pdf"
    f2 = f"qa_b_{ts}.pdf"
    pdf_bytes = _one_page_pdf_bytes()
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
        report["errors"].append(f"upload: {r_up.status_code} {r_up.text[:500]}")
        print(json.dumps(report, indent=2))
        return 1
    t0 = r_up.json()
    tid_first = t0.get("id")
    listing_group_id = t0.get("listing_group_id")
    pdf_url_0 = t0.get("pdf_file_url")
    report["cloudinary_pdf_urls"].append(pdf_url_0)
    report["steps"].append({"name": "upload 2 tickets", "ok": True, "first_ticket_id": tid_first})

    # Second ticket id: list seller tickets, same group
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
        print(json.dumps(report, indent=2))
        return 1
    tid_a, tid_b = ids_in_group[0], ids_in_group[1]

    # Approve both (superuser)
    for tid in (tid_a, tid_b):
        r_ap = seller.post(
            f"{api_base}/users/admin/tickets/{tid}/approve/",
            json={},
            headers=build_csrf_headers(seller, api_base),
            timeout=60,
        )
        if r_ap.status_code != 200:
            report["errors"].append(f"approve {tid}: {r_ap.status_code} {r_ap.text[:300]}")
            print(json.dumps(report, indent=2))
            return 1
    report["steps"].append({"name": "admin approve x2", "ok": True, "ticket_ids": [tid_a, tid_b]})

    # Fetch second pdf URL
    r_d = seller.get(f"{api_base}/users/tickets/{tid_b}/", timeout=60)
    if r_d.status_code == 200:
        pdf1 = r_d.json().get("pdf_file_url")
        if pdf1 and pdf1 not in report["cloudinary_pdf_urls"]:
            report["cloudinary_pdf_urls"].append(pdf1)

    # --- Buyer: register + purchase ---
    buyer_name = f"qa_buyer_{ts}"
    buyer_email = f"{buyer_name}@example.invalid"
    buyer_pw = f"BuyerQA{ts[-6:]}!aA1"
    buyer = session_register_buyer(api_base, buyer_name, buyer_email, buyer_pw)
    if not buyer:
        report["errors"].append("Buyer register failed")
        print(json.dumps(report, indent=2))
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
        print(json.dumps(report, indent=2))
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
        print(json.dumps(report, indent=2))
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
        print(json.dumps(report, indent=2))
        return 1
    ord_body = r_ord.json()
    cf_status, cf_body = confirm_pending_order_payment(buyer, api_base, ord_body)
    cf_ok = cf_status == 200 and isinstance(cf_body, dict) and cf_body.get("status") == "paid"
    report["steps"].append(
        {
            "name": "checkout (simulate + order + confirm)",
            "ok": cf_ok,
            "order_id": ord_body.get("id"),
            "confirm_http": cf_status,
        }
    )
    if not cf_ok:
        report["errors"].append(
            f"confirm-payment: HTTP {cf_status} {cf_body!s}"[:800]
        )
        print(json.dumps(report, indent=2))
        return 1

    # Verify sold
    r_chk = seller.get(f"{api_base}/users/tickets/{tid_a}/", timeout=60)
    st_a = r_chk.json().get("status") if r_chk.status_code == 200 else None
    r_chk2 = seller.get(f"{api_base}/users/tickets/{tid_b}/", timeout=60)
    st_b = r_chk2.json().get("status") if r_chk2.status_code == 200 else None
    sold_ok = st_a == "sold" and st_b == "sold"
    report["steps"].append({"name": "tickets marked sold", "ok": sold_ok, "statuses": [st_a, st_b]})

    # Download PDFs as buyer (blob GET)
    for tid in (tid_a, tid_b):
        r_pdf = buyer.get(
            f"{api_base}/users/tickets/{tid}/download_pdf/",
            timeout=60,
        )
        if r_pdf.status_code != 200 or not r_pdf.content.startswith(b"%PDF"):
            report["errors"].append(f"download {tid}: HTTP {r_pdf.status_code}")
        else:
            report["steps"].append({"name": f"download_pdf ticket {tid}", "ok": True, "bytes": len(r_pdf.content)})

    # --- Render: manual deploy (after QA) ---
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

    # Post-deploy: re-hit events + PDF HEAD if we have URLs
    try:
        r2 = requests.get(f"{api_base}/users/events/?format=json", timeout=60)
        report["post_deploy_events_ok"] = r2.status_code == 200
    except Exception as e:
        report["post_deploy_events_ok"] = False
        report["errors"].append(f"post_deploy events: {e}")

    for u in report["cloudinary_pdf_urls"]:
        if u and u.startswith("http"):
            try:
                h = requests.head(u, timeout=30, allow_redirects=True)
                report.setdefault("pdf_head", []).append({"url": u[:80], "status": h.status_code})
            except Exception as e:
                report.setdefault("pdf_head", []).append({"url": u[:80], "error": str(e)})

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if not report["errors"] else 1


if __name__ == "__main__":
    sys.exit(main())
