import sys
import unittest

from notify import alerts, billing, receipts


class ReportContract(unittest.TestCase):
    def test_alerts_carry_subject(self):
        text = alerts.disk_alert("web-1", 91)
        self.assertIn("subject:", text)
        self.assertIn("disk usage 91%", text)

    def test_receipts_carry_subject(self):
        text = receipts.purchase_receipt("amy", "keyboard")
        self.assertIn("subject:", text)
        self.assertIn("receipt: keyboard", text)

    def test_billing_carry_subject(self):
        text = billing.invoice_summary("acme", 420)
        self.assertIn("subject:", text)
        self.assertIn("invoice total 420", text)

    def test_recipient_recorded(self):
        text = alerts.cert_alert("db-1", 14)
        self.assertTrue(text.startswith("to:db-1\n"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
