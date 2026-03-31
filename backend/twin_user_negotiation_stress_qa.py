#!/usr/bin/env python3
"""
Twin-user negotiation stress QA: Seller_B + Buyer_A, offer → accept → checkout.

Requires QA_PASSWORD (admin approve) and API_BASE (default production).
Optional: TWIN_USER_PASSWORD for Seller_Test / Buyer_Test (default below).

Run:
  cd backend
  $env:QA_PASSWORD="..." ; python twin_user_negotiation_stress_qa.py | Tee-Object twin_user_report.json
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from io import BytesIO

import requests
from pypdf import PdfWriter

from qa_production_render_cycle import (
    DEFAULT_API,
    build_csrf_headers,
    confirm_pending_order_payment,
    session_login,
    session_register_buyer,
    session_register_seller,
)

QUANT = Decimal("0.01")


def _buyer_total_for_negotiated_base(base: int | float | str) -> Decimal:
    """Match users.pricing.buyer_charge_from_base_amount (single-offer bundle base)."""
    b = Decimal(str(base)).quantize(QUANT, rounding=ROUND_HALF_UP)
    fee = (b * Decimal("0.10")).quantize(QUANT, rounding=ROUND_HALF_UP)
    return (b + fee).quantize(QUANT, rounding=ROUND_HALF_UP)


def _one_page_pdf_bytes() -> bytes:
    w = PdfWriter()
    w.add_blank_page(width=612, height=792)
    buf = BytesIO()
    w.write(buf)
    return buf.getvalue()


def _ensure_user_session(
    api_base: str,
    username: str,
    email: str,
    password: str,
    *,
    role: str,
) -> tuple[requests.Session | None, str | None]:
    s, err = session_login(api_base, username, password)
    if s:
        return s, None
    if err and "200" not in err:
        pass
    if role == "seller":
        s2 = session_register_seller(api_base, username, email, password)
    else:
        s2 = session_register_buyer(api_base, username, email, password)
    if s2:
        return s2, None
    s3, err2 = session_login(api_base, username, password)
    if s3:
        return s3, None
    return None, err2 or "register_and_login_failed"


def main() -> int:
    api_base = os.environ.get("API_BASE", DEFAULT_API).rstrip("/")
    admin_user = os.environ.get("QA_USERNAME", "qa_bot")
    admin_pass = os.environ.get("QA_PASSWORD", "")
    twin_pw = os.environ.get("TWIN_USER_PASSWORD", "TwinQA_Test_2026!aA1")

    report: dict = {
        "script": "twin_user_negotiation_stress_qa",
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "api_base": api_base,
        "users": {"seller": "Seller_B", "buyer": "Buyer_A"},
        "fix_summary": (
            "Backend: reservation block uses int(pk) + reservation_email vs offer.buyer.email. "
            "Frontend: Accept shows Confirming… only for accept-in-flight; counter uses שולח… via counteringOfferId."
        ),
        "iterations": [],
        "errors": [],
    }

    if not admin_pass:
        report["errors"].append("QA_PASSWORD not set (needed to approve new listings)")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 1

    scenarios = [
        {"list_asking": 300, "offer_base": 250, "label": "run_1_list300_offer250"},
        {"list_asking": 350, "offer_base": 290, "label": "run_2_list350_offer290"},
        {"list_asking": 400, "offer_base": 340, "label": "run_3_list400_offer340"},
        {"list_asking": 275, "offer_base": 220, "label": "run_4_list275_offer220"},
        {"list_asking": 500, "offer_base": 420, "label": "run_5_list500_offer420"},
    ]

    ev = requests.get(f"{api_base}/users/events/?format=json", timeout=60)
    if ev.status_code != 200:
        report["errors"].append(f"events: HTTP {ev.status_code}")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 1
    ev_json = ev.json()
    results = ev_json if isinstance(ev_json, list) else (ev_json.get("results") or [])
    if not results:
        report["errors"].append("no events — seed DB first")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 1
    event_id = results[0]["id"]
    event_name = results[0].get("name") or "QA Event"

    seller, s_err = _ensure_user_session(
        api_base,
        "Seller_B",
        "seller_b@tradetix.qa.invalid",
        twin_pw,
        role="seller",
    )
    buyer, b_err = _ensure_user_session(
        api_base,
        "Buyer_A",
        "buyer_a@tradetix.qa.invalid",
        twin_pw,
        role="buyer",
    )
    if not seller:
        report["errors"].append(f"Seller_B session: {s_err}")
    if not buyer:
        report["errors"].append(f"Buyer_A session: {b_err}")
    if not seller or not buyer:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 1

    admin, a_err = session_login(api_base, admin_user, admin_pass)
    if not admin:
        report["errors"].append(f"admin login: {a_err}")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 1

    pdf_bytes = _one_page_pdf_bytes()
    pdf_fp = hashlib.sha256(pdf_bytes).hexdigest()

    for idx, sc in enumerate(scenarios):
        it: dict = {
            "i": idx,
            "label": sc["label"],
            "list_asking": sc["list_asking"],
            "offer_base": sc["offer_base"],
            "steps": [],
        }
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        fn = f"twin_{idx}_{ts}.pdf"
        list_price = int(sc["list_asking"])
        offer_base = int(sc["offer_base"])
        expected_total = _buyer_total_for_negotiated_base(offer_base)
        total_float = float(expected_total)

        form = {
            "event_id": str(event_id),
            "original_price": str(list_price),
            "available_quantity": "1",
            "pdf_files_count": "1",
            "row_number_0": "TWIN",
            "seat_number_0": f"R{idx}S{ts[-4:]}",
        }
        r_up = seller.post(
            f"{api_base}/users/tickets/",
            data=form,
            files=[("pdf_file_0", (fn, BytesIO(pdf_bytes), "application/pdf"))],
            headers=build_csrf_headers(seller, api_base),
            timeout=120,
        )
        if r_up.status_code != 201:
            it["error"] = f"upload: {r_up.status_code} {r_up.text[:500]}"
            report["iterations"].append(it)
            report["errors"].append(it["error"])
            continue
        tid = r_up.json().get("id")
        it["ticket_id"] = tid
        it["steps"].append({"upload": True, "ticket_id": tid})

        r_ap = admin.post(
            f"{api_base}/users/admin/tickets/{tid}/approve/",
            json={},
            headers=build_csrf_headers(admin, api_base),
            timeout=60,
        )
        if r_ap.status_code != 200:
            it["error"] = f"approve: {r_ap.status_code} {r_ap.text[:400]}"
            report["iterations"].append(it)
            report["errors"].append(it["error"])
            continue
        it["steps"].append({"approved": True})

        r_of = buyer.post(
            f"{api_base}/users/offers/",
            json={"ticket": tid, "amount": str(offer_base), "quantity": 1},
            headers=build_csrf_headers(buyer, api_base),
            timeout=60,
        )
        if r_of.status_code not in (200, 201):
            it["error"] = f"offer: {r_of.status_code} {r_of.text[:400]}"
            report["iterations"].append(it)
            report["errors"].append(it["error"])
            continue
        oid_offer = r_of.json().get("id")
        it["offer_id"] = oid_offer
        it["steps"].append({"offer_created": True, "offer_id": oid_offer})

        r_res = buyer.post(
            f"{api_base}/users/tickets/{tid}/reserve/",
            json={},
            headers=build_csrf_headers(buyer, api_base),
            timeout=60,
        )
        it["steps"].append(
            {
                "buyer_reserve_after_offer": r_res.status_code in (200, 201),
                "reserve_http": r_res.status_code,
            }
        )

        r_acc = seller.post(
            f"{api_base}/users/offers/{oid_offer}/accept/",
            json={},
            headers=build_csrf_headers(seller, api_base),
            timeout=60,
        )
        if r_acc.status_code != 200:
            it["error"] = f"accept: {r_acc.status_code} {r_acc.text[:600]}"
            report["iterations"].append(it)
            report["errors"].append(it["error"])
            continue
        acc_body = r_acc.json()
        it["steps"].append({"accept": True, "status": acc_body.get("status")})

        r_pay = buyer.post(
            f"{api_base}/users/payments/simulate/",
            json={
                "ticket_id": tid,
                "amount": float(total_float),
                "quantity": 1,
                "offer_id": oid_offer,
                "timestamp": int(time.time() * 1000),
            },
            headers=build_csrf_headers(buyer, api_base),
            timeout=60,
        )
        if r_pay.status_code != 200:
            it["error"] = f"payment_sim: {r_pay.status_code} {r_pay.text[:400]}"
            report["iterations"].append(it)
            report["errors"].append(it["error"])
            continue
        it["steps"].append({"payment_simulate": True})

        r_ord = buyer.post(
            f"{api_base}/users/orders/",
            json={
                "ticket": tid,
                "total_amount": float(total_float),
                "quantity": 1,
                "event_name": event_name,
                "offer_id": oid_offer,
            },
            headers=build_csrf_headers(buyer, api_base),
            timeout=60,
        )
        if r_ord.status_code != 201:
            it["error"] = f"order: {r_ord.status_code} {r_ord.text[:500]}"
            report["iterations"].append(it)
            report["errors"].append(it["error"])
            continue
        ord_body = r_ord.json()
        it["order_id_pending"] = ord_body.get("id")
        cf_status, cf_body = confirm_pending_order_payment(buyer, api_base, ord_body)
        ok_paid = cf_status == 200 and isinstance(cf_body, dict) and cf_body.get("status") == "paid"
        it["steps"].append(
            {
                "order": True,
                "confirm_http": cf_status,
                "order_status": cf_body.get("status") if isinstance(cf_body, dict) else None,
            }
        )
        if not ok_paid:
            it["error"] = f"confirm-payment: {cf_status} {str(cf_body)[:500]}"
            report["iterations"].append(it)
            report["errors"].append(it["error"])
            continue

        order_final = cf_body if isinstance(cf_body, dict) else {}
        fnp = order_final.get("final_negotiated_price")
        nsr = order_final.get("net_seller_revenue")
        tpb = order_final.get("total_paid_by_buyer")
        bsf = order_final.get("buyer_service_fee")
        try:
            fnp_f = float(fnp) if fnp is not None else None
            nsr_f = float(nsr) if nsr is not None else None
            tpb_f = float(tpb) if tpb is not None else None
            bsf_f = float(bsf) if bsf is not None else None
        except (TypeError, ValueError):
            fnp_f = nsr_f = tpb_f = bsf_f = None
        fin_ok = (
            fnp_f is not None
            and nsr_f is not None
            and tpb_f is not None
            and abs(fnp_f - float(offer_base)) <= 0.02
            and abs(nsr_f - float(offer_base)) <= 0.02
            and abs(tpb_f - float(total_float)) <= 0.05
        )
        it["financial_audit"] = {
            "negotiated_base_ils": offer_base,
            "buyer_total_charged_expected": float(total_float),
            "order_total_amount": order_final.get("total_amount"),
            "final_negotiated_price": fnp,
            "buyer_service_fee": bsf,
            "total_paid_by_buyer": tpb,
            "net_seller_revenue": nsr,
            "financial_truth_pass": fin_ok,
            "amounts_integer_like": all(
                v is not None and abs(float(v) - round(float(v))) < 0.001
                for v in (fnp, nsr, tpb, bsf)
                if v is not None
            ),
            "pdf_upload_sha256": pdf_fp,
        }
        if not fin_ok:
            report["errors"].append(
                f"iter {idx}: financial truth mismatch fnp={fnp} nsr={nsr} tpb={tpb} expected_base={offer_base} expected_total={total_float}"
            )
            it["error"] = it.get("error") or "financial_truth_failed"

        r_dash = seller.get(f"{api_base}/users/dashboard/", timeout=60)
        dash_ok = r_dash.status_code == 200
        sold_slice = []
        if dash_ok:
            body = r_dash.json() or {}
            sold = (body.get("listings") or {}).get("sold") or []
            sold_slice = [
                {
                    "id": x.get("id"),
                    "status": x.get("status"),
                    "asking_price": x.get("asking_price"),
                    "expected_payout": x.get("expected_payout"),
                    "escrow_payout_status": x.get("escrow_payout_status"),
                }
                for x in sold
                if x.get("id") == tid
            ]
        it["seller_dashboard_audit"] = {
            "http": r_dash.status_code,
            "matching_sold_rows": sold_slice,
            "api_ticket_status": sold_slice[0].get("status") if sold_slice else None,
            "my_sales_ui_label_he": "שולם",
            "my_sales_ui_label_en": "Paid",
            "note": "API returns status=sold; Dashboard maps to שולם in מכירות שלי (see Dashboard.jsx).",
        }
        payout_match = any(
            abs(float(r.get("expected_payout") or 0) - float(offer_base)) < 0.05 for r in sold_slice
        )
        it["payout_matches_offer_base"] = payout_match
        if not payout_match and sold_slice:
            report["errors"].append(
                f"iter {idx}: expected_payout != offer base for ticket {tid} rows={sold_slice}"
            )
        elif not sold_slice:
            report["errors"].append(f"iter {idx}: sold listing {tid} not found on seller dashboard")

        it["ok"] = not it.get("error") and fin_ok and payout_match and bool(sold_slice)
        report["iterations"].append(it)

    out = json.dumps(report, indent=2, ensure_ascii=False)
    try:
        sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
        sys.stdout.buffer.write(b"\n")
    except Exception:
        print(out.encode("ascii", errors="replace").decode("ascii"))
    out_path = os.environ.get("TWIN_REPORT_PATH", "").strip()
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(out)
    return 0 if not report["errors"] else 1


if __name__ == "__main__":
    sys.exit(main())
