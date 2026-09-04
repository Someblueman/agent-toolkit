import unittest

from paths import avatar_upload, document_upload, export_upload


class UploadTests(unittest.TestCase):
    def test_paths_preserve_content_type(self):
        for make, expected_private in (
            (document_upload, False), (avatar_upload, True), (export_upload, False)
        ):
            upload = make("item", b"data", "image/webp")
            self.assertEqual(upload.content_type, "image/webp")
            self.assertEqual(upload.private, expected_private)


if __name__ == "__main__":
    unittest.main()
