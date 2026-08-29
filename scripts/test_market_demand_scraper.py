"""Offline tests for demand classification — no browser, no network."""

from __future__ import annotations

import unittest

from market_demand_scraper import (
    classify_category,
    classify_demand,
    infer_sports_hit,
)


class DemandClassificationTests(unittest.TestCase):
    def test_sold_out_hebrew(self):
        self.assertEqual(classify_demand("ההופעה סולד אאוט ואין כרטיסים"), "Sold Out")

    def test_sold_out_english(self):
        self.assertEqual(classify_demand("This show is Sold out"), "Sold Out")

    def test_fast_selling(self):
        self.assertEqual(classify_demand("כרטיסים אחרונים ליציע"), "Fast Selling")

    def test_no_demand_signal(self):
        self.assertIsNone(classify_demand("כרטיסים זמינים להזמנה"))

    def test_comedy_category(self):
        self.assertEqual(classify_category("ניקי גולדשטיין סטנדאפ בתל אביב"), "Comedy")

    def test_sports_watchlist(self):
        hit = infer_sports_hit("מכבי חיפה נגד בית״ר ירושלים")
        self.assertTrue(hit)
        self.assertEqual(classify_category("מכבי חיפה נגד בית״ר ירושלים", sports_hit=True), "Sports")


if __name__ == "__main__":
    unittest.main()
