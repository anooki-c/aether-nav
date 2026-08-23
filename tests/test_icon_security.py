import unittest

from backend.icon_utils import valid_icon_content


class IconSecurityTests(unittest.TestCase):
    def test_accepts_supported_image_signatures(self):
        self.assertTrue(valid_icon_content(b"\x89PNG\r\n\x1a\n", "image/png", "icon.png"))
        self.assertTrue(valid_icon_content(b"\xff\xd8\xff\xe0", "image/jpeg", "icon.jpg"))
        self.assertTrue(valid_icon_content(b"RIFFxxxxWEBP", "image/webp", "icon.webp"))
        self.assertTrue(valid_icon_content(b"\x00\x00\x01\x00", "image/x-icon", "icon.ico"))

    def test_rejects_mismatched_content_and_unsafe_svg(self):
        self.assertFalse(valid_icon_content(b"not an image", "image/png", "icon.png"))
        self.assertFalse(valid_icon_content(b"<svg><script>alert(1)</script></svg>", "image/svg+xml", "icon.svg"))
        self.assertFalse(valid_icon_content(b"<svg><foreignObject /></svg>", "image/svg+xml", "icon.svg"))
        self.assertTrue(valid_icon_content(b"<svg viewBox='0 0 1 1'></svg>", "image/svg+xml", "icon.svg"))


if __name__ == "__main__":
    unittest.main()
