# apps/bundles/tests/test_stats.py
from django.test import SimpleTestCase

from apps.bundles.stats import aggregate_purchase_rows, credits_total, sum_credits


class SumCreditsTests(SimpleTestCase):
    def test_basic(self):
        self.assertEqual(sum_credits({"listing": 10, "boost": 2}), {"listing": 10, "boost": 2})

    def test_numeric_strings_and_floats_are_counted(self):
        self.assertEqual(sum_credits({"a": "5", "b": 3.0}), {"a": 5, "b": 3})

    def test_bad_values_ignored(self):
        snap = {"a": None, "b": True, "c": "x", "d": -4, "e": [1], "f": 7}
        self.assertEqual(sum_credits(snap), {"f": 7})

    def test_non_dict_snapshot(self):
        for bad in (None, [], "x", 5):
            self.assertEqual(sum_credits(bad), {})
            self.assertEqual(credits_total(bad), 0)

    def test_total(self):
        self.assertEqual(credits_total({"listing": 10, "boost": 2}), 12)


class AggregateTests(SimpleTestCase):
    def test_groups_by_bundle(self):
        rows = [
            (1, {"listing": 10}),
            (1, {"listing": 10, "boost": 1}),
            (2, {"ads": 3}),
        ]
        s = aggregate_purchase_rows(rows)
        self.assertEqual(s[1], {"purchases": 2, "creditsByService": {"listing": 20, "boost": 1}, "creditsTotal": 21})
        self.assertEqual(s[2], {"purchases": 1, "creditsByService": {"ads": 3}, "creditsTotal": 3})

    def test_purchase_without_credits_still_counts(self):
        s = aggregate_purchase_rows([(5, {}), (5, None)])
        self.assertEqual(s[5], {"purchases": 2, "creditsByService": {}, "creditsTotal": 0})

    def test_bundle_without_purchases_is_absent(self):
        self.assertEqual(aggregate_purchase_rows([]), {})

    def test_accepts_generator(self):
        gen = ((1, {"a": 1}) for _ in range(3))
        self.assertEqual(aggregate_purchase_rows(gen)[1]["creditsTotal"], 3)
