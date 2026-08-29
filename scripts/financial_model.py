#!/usr/bin/env python3
"""
TradeTix 12-month financial projection.

Default planning take-rate is 12% buyer fee / 0% seller fee (CLI-adjustable).
Live product default in code is 7% / 0% — pass --buyer-fee 0.07 to match production.

Usage (from scripts/):

    python financial_model.py
    python financial_model.py --buyer-fee 0.07 --output financial_projection_12m.csv
    python test_financial_model.py
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

Q = Decimal("0.01")


def money(value: Decimal | float | int | str) -> Decimal:
    return Decimal(str(value)).quantize(Q, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Assumptions:
    seller_fee_rate: Decimal = Decimal("0.00")
    buyer_fee_rate: Decimal = Decimal("0.12")
    avg_ticket_ils: Decimal = Decimal("300")
    payme_pct: Decimal = Decimal("0.015")
    payme_fixed_ils: Decimal = Decimal("1.20")
    sms_cost_ils: Decimal = Decimal("0.28")
    sms_per_signup: Decimal = Decimal("1.3")
    hosting_base_ils: Decimal = Decimal("180")
    db_base_ils: Decimal = Decimal("120")
    cloudinary_base_ils: Decimal = Decimal("45")
    domain_ils: Decimal = Decimal("8")
    listings_per_sold: Decimal = Decimal("2.4")
    signups_per_sold: Decimal = Decimal("1.8")
    seller_cac_ils: Decimal = Decimal("55")
    buyer_cac_ils: Decimal = Decimal("38")
    ads_floor_ils: Decimal = Decimal("2000")
    ads_cap_share_of_gmv: Decimal = Decimal("0.07")
    ads_seed_months: int = 3


# Conservative ramp from Aug-2026 reality (~1 tracked purchase, ~23 listings,
# ~₪1k ads) toward a working marketplace if inventory + checkout tracking hold.
TICKETS_SOLD_BY_MONTH: tuple[int, ...] = (
    12,
    20,
    32,
    48,
    70,
    100,
    135,
    175,
    220,
    270,
    330,
    400,
)


def payme_fee(charge_ils: Decimal, assumptions: Assumptions) -> Decimal:
    return money(charge_ils * assumptions.payme_pct + assumptions.payme_fixed_ils)


def unit_economics(assumptions: Assumptions) -> dict[str, Decimal]:
    face = assumptions.avg_ticket_ils
    buyer_fee = money(face * assumptions.buyer_fee_rate)
    seller_fee = money(face * assumptions.seller_fee_rate)
    charge = face + buyer_fee
    psp = payme_fee(charge, assumptions)
    take = buyer_fee + seller_fee
    contribution = take - psp
    return {
        "face": face,
        "buyer_fee": buyer_fee,
        "seller_fee": seller_fee,
        "charge": charge,
        "payme": psp,
        "take": take,
        "contribution": contribution,
        "payme_share_of_take": (psp / take) if take else Decimal("0"),
    }


def ads_budget(
    gmv: Decimal,
    tickets: int,
    listings: int,
    assumptions: Assumptions,
    *,
    month: int,
) -> Decimal:
    """Seed the flywheel for a few months, then cap ads under contribution (~7% of GMV)."""
    seller_ads = money(listings * assumptions.seller_cac_ils)
    buyer_ads = money(tickets * assumptions.buyer_cac_ils)
    raw = seller_ads + buyer_ads
    if month <= assumptions.ads_seed_months:
        return money(assumptions.ads_floor_ils)
    efficient_cap = money(gmv * assumptions.ads_cap_share_of_gmv) if gmv else assumptions.ads_floor_ils
    return money(min(raw, max(efficient_cap, Decimal("800"))))


def infra_costs(tickets: int, listings: int, assumptions: Assumptions) -> dict[str, Decimal]:
    hosting = assumptions.hosting_base_ils + (Decimal("90") if tickets >= 150 else Decimal("0"))
    hosting += Decimal("180") if tickets >= 300 else Decimal("0")
    db = assumptions.db_base_ils + (Decimal("80") if tickets >= 120 else Decimal("0"))
    db += Decimal("160") if tickets >= 280 else Decimal("0")
    cloudinary = assumptions.cloudinary_base_ils + money(Decimal("0.18") * listings)
    return {
        "hosting": money(hosting),
        "db": money(db),
        "cloudinary": money(cloudinary),
        "domain": money(assumptions.domain_ils),
    }


def project_month(month: int, tickets: int, assumptions: Assumptions) -> dict[str, object]:
    units = unit_economics(assumptions)
    listings = max(8, int(Decimal(tickets) * assumptions.listings_per_sold))
    signups = max(10, int(Decimal(tickets) * assumptions.signups_per_sold))
    gmv = money(Decimal(tickets) * assumptions.avg_ticket_ils)
    buyer_fee_rev = money(Decimal(tickets) * units["buyer_fee"])
    seller_fee_rev = money(Decimal(tickets) * units["seller_fee"])
    revenue = buyer_fee_rev + seller_fee_rev
    charge_volume = money(Decimal(tickets) * units["charge"])
    payme_cost = money(Decimal(tickets) * units["payme"])
    sms_cost = money(Decimal(signups) * assumptions.sms_cost_ils * assumptions.sms_per_signup)
    ads = ads_budget(gmv, tickets, listings, assumptions, month=month)
    infra = infra_costs(tickets, listings, assumptions)
    fixed = infra["hosting"] + infra["db"] + infra["cloudinary"] + infra["domain"]
    variable = payme_cost + sms_cost
    opex = fixed + variable + ads
    contribution = revenue - payme_cost
    ebitda = revenue - opex
    return {
        "month": month,
        "tickets_sold": tickets,
        "new_listings": listings,
        "new_signups": signups,
        "gmv_ils": gmv,
        "buyer_fee_revenue_ils": buyer_fee_rev,
        "seller_fee_revenue_ils": seller_fee_rev,
        "platform_revenue_ils": revenue,
        "charge_volume_ils": charge_volume,
        "payme_cost_ils": payme_cost,
        "sms_cost_ils": sms_cost,
        "hosting_ils": infra["hosting"],
        "db_ils": infra["db"],
        "cloudinary_ils": infra["cloudinary"],
        "domain_ils": infra["domain"],
        "fixed_costs_ils": fixed,
        "google_ads_ils": ads,
        "total_opex_ils": opex,
        "contribution_after_payme_ils": contribution,
        "ebitda_ils": ebitda,
        "payme_pct_of_take": (payme_cost / revenue) if revenue else Decimal("0"),
        "ads_pct_of_gmv": (ads / gmv) if gmv else Decimal("0"),
    }


def build_projection(assumptions: Assumptions) -> list[dict[str, object]]:
    return [
        project_month(month, tickets, assumptions)
        for month, tickets in enumerate(TICKETS_SOLD_BY_MONTH, start=1)
    ]


CSV_COLUMNS = (
    "month",
    "tickets_sold",
    "new_listings",
    "new_signups",
    "gmv_ils",
    "buyer_fee_revenue_ils",
    "seller_fee_revenue_ils",
    "platform_revenue_ils",
    "charge_volume_ils",
    "payme_cost_ils",
    "sms_cost_ils",
    "hosting_ils",
    "db_ils",
    "cloudinary_ils",
    "domain_ils",
    "fixed_costs_ils",
    "google_ads_ils",
    "total_opex_ils",
    "contribution_after_payme_ils",
    "ebitda_ils",
    "payme_pct_of_take",
    "ads_pct_of_gmv",
)


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            out = {}
            for key in CSV_COLUMNS:
                value = row[key]
                if isinstance(value, Decimal):
                    if key.endswith("pct_of_take") or key.endswith("pct_of_gmv"):
                        out[key] = f"{(value * Decimal('100')).quantize(Q)}%"
                    else:
                        out[key] = f"{value:.2f}"
                else:
                    out[key] = value
            writer.writerow(out)


def totals(rows: list[dict[str, object]]) -> dict[str, Decimal]:
    keys = (
        "tickets_sold",
        "gmv_ils",
        "platform_revenue_ils",
        "payme_cost_ils",
        "sms_cost_ils",
        "fixed_costs_ils",
        "google_ads_ils",
        "total_opex_ils",
        "ebitda_ils",
    )
    acc: dict[str, Decimal] = {key: Decimal("0") for key in keys}
    for row in rows:
        for key in keys:
            acc[key] += Decimal(str(row[key]))
    return acc


def negotiate_month(rows: list[dict[str, object]]) -> int | None:
    """First month PayMe cost exceeds ₪2,000 or 22% of take at ≥80 tickets."""
    for row in rows:
        payme = Decimal(str(row["payme_cost_ils"]))
        take = Decimal(str(row["platform_revenue_ils"]))
        tickets = int(row["tickets_sold"])
        share = (payme / take) if take else Decimal("0")
        if payme >= Decimal("2000") or (tickets >= 80 and share >= Decimal("0.22")):
            return int(row["month"])
    return None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TradeTix 12-month financial projection")
    parser.add_argument("--buyer-fee", type=Decimal, default=Decimal("0.12"), help="Buyer platform fee rate (default 0.12)")
    parser.add_argument("--seller-fee", type=Decimal, default=Decimal("0.00"))
    parser.add_argument("--avg-ticket", type=Decimal, default=Decimal("300"))
    parser.add_argument(
        "--output",
        default=str(Path(__file__).with_name("financial_projection_12m.csv")),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    assumptions = Assumptions(
        seller_fee_rate=args.seller_fee,
        buyer_fee_rate=args.buyer_fee,
        avg_ticket_ils=args.avg_ticket,
    )
    rows = build_projection(assumptions)
    output = Path(args.output)
    write_csv(output, rows)
    units = unit_economics(assumptions)
    year = totals(rows)
    print(f"Wrote {output.resolve()}")
    print(
        f"Unit: face ILS {units['face']} -> charge ILS {units['charge']} -> "
        f"take ILS {units['take']} -> PayMe ILS {units['payme']} -> "
        f"contribution ILS {units['contribution']} "
        f"({(units['payme_share_of_take'] * 100).quantize(Q)}% of take is PSP)"
    )
    print(
        f"Year: {int(year['tickets_sold'])} tickets | GMV ILS {year['gmv_ils']} | "
        f"revenue ILS {year['platform_revenue_ils']} | ads ILS {year['google_ads_ils']} | "
        f"EBITDA ILS {year['ebitda_ils']}"
    )
    month = negotiate_month(rows)
    if month:
        print(f"Negotiate PayMe from month {month} (ILS 2000 PSP or 22% of take).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
