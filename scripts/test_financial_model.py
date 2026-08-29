"""Unit tests for TradeTix unit economics (no I/O besides temp CSV)."""

from __future__ import annotations

import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from financial_model import (
    Assumptions,
    ads_budget,
    build_projection,
    money,
    negotiate_month,
    payme_fee,
    unit_economics,
    write_csv,
)


class UnitEconomicsTests(unittest.TestCase):
    def test_payme_on_12_percent_take(self):
        assumptions = Assumptions(buyer_fee_rate=Decimal("0.12"))
        units = unit_economics(assumptions)
        self.assertEqual(units["charge"], money(336))
        self.assertEqual(units["payme"], money(Decimal("336") * Decimal("0.015") + Decimal("1.20")))
        self.assertEqual(units["contribution"], units["take"] - units["payme"])

    def test_live_7_percent_take_is_thinner(self):
        live = unit_economics(Assumptions(buyer_fee_rate=Decimal("0.07")))
        plan = unit_economics(Assumptions(buyer_fee_rate=Decimal("0.12")))
        self.assertLess(live["contribution"], plan["contribution"])
        self.assertGreater(live["payme_share_of_take"], plan["payme_share_of_take"])

    def test_zero_seller_fee(self):
        units = unit_economics(Assumptions())
        self.assertEqual(units["seller_fee"], money(0))

    def test_ads_never_below_floor(self):
        assumptions = Assumptions(ads_floor_ils=Decimal("2000"))
        spend = ads_budget(money(1000), tickets=2, listings=3, assumptions=assumptions, month=1)
        self.assertGreaterEqual(spend, money(2000))

    def test_projection_has_twelve_months_and_csv(self):
        rows = build_projection(Assumptions())
        self.assertEqual(len(rows), 12)
        self.assertGreater(int(rows[-1]["tickets_sold"]), int(rows[0]["tickets_sold"]))
        self.assertIsNotNone(negotiate_month(rows))
        self.assertGreater(rows[-1]["ebitda_ils"], Decimal("0"))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.csv"
            write_csv(path, rows)
            text = path.read_text(encoding="utf-8-sig")
            self.assertIn("platform_revenue_ils", text)
            self.assertEqual(len(text.strip().splitlines()), 13)


if __name__ == "__main__":
    unittest.main()
