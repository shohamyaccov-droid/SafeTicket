#!/usr/bin/env python3
"""
Live E2E against production API (seller upload + CSRF, buyer offer, seller accept, checkout confirm).
Requires: requests (pip install requests)
Env: LIVE_API_BASE (default https://safeticket-api.onrender.com/api)
     LIVE_QA_ADMIN_USER / LIVE_QA_ADMIN_PASSWORD (default qa_bot / SafeTicketQA2026!)
"""
from __future__ import annotations

import json
import math
import os
import random
import string
import sys
import time

import requests

API = os.environ.get("LIVE_API_BASE", "https://safeticket-api.onrender.com/api").rstrip("/")
ORIGIN = os.environ.get("LIVE_ORIGIN", "https://safeticket-api.onrender.com").rstrip("/")
ADMIN_USER = os.environ.get("LIVE_QA_ADMIN_USER", "qa_bot")
ADMIN_PASS = os.environ.get("LIVE_QA_ADMIN_PASSWORD", "SafeTicketQA2026!")


def log(msg: str) -> None:
    print(msg, flush=True)


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": "SafeTicket-live-qa/1.0"})
    return s


def csrf_token(s: requests.Session) -> str:
    r = s.get(f"{API}/users/csrf/", timeout=90)
    r.raise_for_status()
    j = r.json()
    t = (j.get("csrfToken") or "").strip()
    if not t:
        for c in s.cookies:
            if c.name == "csrftoken":
                t = c.value
                break
    if not t:
        raise RuntimeError("No CSRF token from /users/csrf/ or cookies")
    return t


def csrf_headers(token: str) -> dict:
    return {
        "X-CSRFToken": token,
        "Referer": f"{ORIGIN}/",
        "Origin": ORIGIN,
    }


def register_user(s: requests.Session, username: str, email: str, password: str, role: str) -> requests.Response:
    tok = csrf_token(s)
    h = csrf_headers(tok)
    h["Content-Type"] = "application/json"
    return s.post(
        f"{API}/users/register/",
        json={
            "username": username,
            "email": email,
            "password": password,
            "password2": password,
            "role": role,
        },
        headers=h,
        timeout=120,
    )


def login_user(s: requests.Session, username: str, password: str) -> requests.Response:
    tok = csrf_token(s)
    h = csrf_headers(tok)
    h["Content-Type"] = "application/json"
    return s.post(
        f"{API}/users/login/",
        json={"username": username, "password": password},
        headers=h,
        timeout=120,
    )


def main() -> None:
    stamp = str(int(time.time()))
    suf = "".join(random.choices(string.ascii_lowercase, k=4))
    seller_u = f"live_sel_{stamp}_{suf}"
    buyer_u = f"live_buy_{stamp}_{suf}"
    seller_e = f"{seller_u}@liveqa.test"
    buyer_e = f"{buyer_u}@liveqa.test"
    pw = "LiveQA2026!Test"

    log("=== SafeTicket LIVE QA ===")
    log(f"API={API}")

    for attempt in range(1, 31):
        try:
            r0 = requests.get(f"{API}/users/events/", timeout=45)
            if r0.status_code == 200:
                log(f"API ready: GET /users/events/ -> {r0.status_code}")
                break
        except Exception as e:
            log(f"waiting for API (attempt {attempt}): {e}")
        time.sleep(15)
    else:
        log("FATAL: API not reachable")
        sys.exit(1)

    data = r0.json()
    evlist = data.get("results", data) if isinstance(data, dict) else data
    if not evlist:
        log("FATAL: no events")
        sys.exit(1)
    event_id = evlist[0]["id"]
    log(f"event_id={event_id}")

    s_sell = session()
    s_buy = session()
    s_adm = session()

    r = register_user(s_sell, seller_u, seller_e, pw, "seller")
    log(f"register seller: {r.status_code}")
    if r.status_code not in (200, 201):
        log(r.text[:800])
        sys.exit(1)

    r = register_user(s_buy, buyer_u, buyer_e, pw, "buyer")
    log(f"register buyer: {r.status_code}")
    if r.status_code not in (200, 201):
        log(r.text[:800])
        sys.exit(1)

    r = login_user(s_adm, ADMIN_USER, ADMIN_PASS)
    log(f"login admin ({ADMIN_USER}): {r.status_code}")
    if r.status_code != 200:
        log(r.text[:600])
        sys.exit(1)

    r = login_user(s_sell, seller_u, pw)
    log(f"login seller: {r.status_code}")
    if r.status_code != 200:
        log(r.text[:600])
        sys.exit(1)

    pdf_bytes = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
    tok = csrf_token(s_sell)
    h = csrf_headers(tok)
    files = {"pdf_file_0": ("live_ticket.pdf", pdf_bytes, "application/pdf")}
    form = {
        "event_id": str(event_id),
        "original_price": "100",
        "available_quantity": "1",
        "pdf_files_count": "1",
        "ticket_type": "כרטיס אלקטרוני / PDF",
        "split_type": "כל כמות",
        "is_obstructed_view": "false",
        "row_number_0": "",
        "seat_number_0": "",
        "section": "",
        "row": "",
        "is_together": "true",
    }
    r = s_sell.post(f"{API}/users/tickets/", data=form, files=files, headers=h, timeout=180)
    log(f"POST /users/tickets/ (multipart + CSRF): {r.status_code}")
    if r.status_code == 403:
        log("FATAL: CSRF 403 on ticket upload")
        log(r.text[:800])
        sys.exit(1)
    if r.status_code != 201:
        log(r.text[:1200])
        sys.exit(1)
    body = r.json()
    tid = body.get("id")
    log(f"ticket_id={tid}")

    tok = csrf_token(s_adm)
    h = csrf_headers(tok)
    r = s_adm.post(f"{API}/users/admin/tickets/{tid}/approve/", data={}, headers=h, timeout=120)
    log(f"POST admin approve: {r.status_code}")
    if r.status_code != 200:
        log(r.text[:800])
        sys.exit(1)

    r = login_user(s_buy, buyer_u, pw)
    log(f"login buyer: {r.status_code}")
    if r.status_code != 200:
        log(r.text[:600])
        sys.exit(1)

    tok = csrf_token(s_buy)
    h = csrf_headers(tok)
    h["Content-Type"] = "application/json"
    r = s_buy.post(
        f"{API}/users/offers/",
        json={"ticket": tid, "amount": 100, "quantity": 1},
        headers=h,
        timeout=120,
    )
    log(f"POST /users/offers/: {r.status_code}")
    if r.status_code not in (200, 201):
        log(r.text[:1000])
        sys.exit(1)
    offer_id = r.json().get("id")
    log(f"offer_id={offer_id}")

    tok = csrf_token(s_sell)
    h = csrf_headers(tok)
    r = s_sell.post(f"{API}/users/offers/{offer_id}/accept/", data={}, headers=h, timeout=120)
    log(f"POST offer accept: {r.status_code}")
    if r.status_code != 200:
        log(r.text[:1000])
        sys.exit(1)

    total = float(math.ceil(100 * 1.10))
    tok = csrf_token(s_buy)
    h = csrf_headers(tok)
    h["Content-Type"] = "application/json"
    r = s_buy.post(
        f"{API}/users/orders/",
        json={
            "ticket": tid,
            "quantity": 1,
            "total_amount": total,
            "offer_id": offer_id,
        },
        headers=h,
        timeout=120,
    )
    log(f"POST /users/orders/: {r.status_code}")
    if r.status_code not in (200, 201):
        log(r.text[:1200])
        sys.exit(1)
    od = r.json()
    oid = od.get("id")
    ptok = (od.get("payment_confirm_token") or "").strip()
    log(f"order_id={oid}")

    tok = csrf_token(s_buy)
    h = csrf_headers(tok)
    h["Content-Type"] = "application/json"
    r = s_buy.post(
        f"{API}/users/orders/{oid}/confirm-payment/",
        json={"mock_payment_ack": True, "payment_confirm_token": ptok},
        headers=h,
        timeout=120,
    )
    log(f"POST confirm-payment: {r.status_code}")
    if r.status_code != 200:
        log(r.text[:800])
        sys.exit(1)

    log("=== LIVE QA PASSED ===")
    log(json.dumps({"ticket_id": tid, "offer_id": offer_id, "order_id": oid}, indent=2))


if __name__ == "__main__":
    main()
