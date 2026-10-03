"""Checks for important grouped-data edge cases and mortgage amortization."""
import unittest
import numpy as np
from extend_analysis import insurance_median_interval, payment_factor

class AnalysisChecks(unittest.TestCase):
    def test_even_split_across_bins_is_not_false_precision(self):
        counts = [0]*12
        counts[0] = counts[5] = 10
        self.assertEqual(insurance_median_interval(counts, 20), (0, 1500))

    def test_upper_tail_is_unbounded(self):
        counts = [0]*11 + [7]
        lo, hi = insurance_median_interval(counts, 7)
        self.assertEqual(lo, 4000)
        self.assertTrue(np.isinf(hi))

    def test_invalid_counts_are_missing_not_zero_cost(self):
        for counts,total in [([0]*12,0), ([1]*12,11), ([np.nan]*12,12)]:
            self.assertTrue(np.isnan(insurance_median_interval(counts,total)).all())

    def test_amortization_for_historical_and_scenario_rates(self):
        for rate in [.03935769230769231,.06721153846153846,.0703,.0753]:
            balance=250000.0
            payment=balance*payment_factor(rate)
            for _ in range(360):
                balance=balance*(1+rate/12)-payment
            self.assertAlmostEqual(float(balance),0,places=5)

if __name__ == '__main__':
    unittest.main()
