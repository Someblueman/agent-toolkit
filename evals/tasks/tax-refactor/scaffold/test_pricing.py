import unittest

from pricing import calculate_tax, invoice_total, receipt


class TestPricing(unittest.TestCase):
    def test_tax(self):
        self.assertEqual(calculate_tax(100.0, 0.08), 8.0)

    def test_receipt(self):
        self.assertEqual(receipt(100.0, 0.08), "subtotal 100.00 + tax 8.00 = 108.00")

    def test_invoice_total(self):
        self.assertEqual(invoice_total(100.0, 0.08, 5.0), 113.0)


if __name__ == "__main__":
    unittest.main()
