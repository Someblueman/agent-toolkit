import unittest

from flows import batch_receipt, email_receipt, webhook_receipt


class ReceiptTests(unittest.TestCase):
    def test_each_flow_preserves_tags(self):
        tags = ("priority", "external")
        self.assertEqual(email_receipt("e-1", tags).tags, tags)
        self.assertEqual(webhook_receipt("w-1", tags).tags, tags)
        self.assertEqual(batch_receipt("b-1", tags).tags, tags)


if __name__ == "__main__":
    unittest.main()
