import unittest

from service import save_event


class StoreTests(unittest.TestCase):
    def test_save_uses_caller_key(self):
        store = save_event("invoice.created", {"id": 7})
        self.assertEqual(store.items, {"invoice.created": {"id": 7}})


if __name__ == "__main__":
    unittest.main()
