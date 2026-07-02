from django.test import SimpleTestCase

from mentora.knowledge.asset_streaming import parse_range_header


class AssetStreamingRangeTests(SimpleTestCase):
    def test_parse_closed_range(self):
        self.assertEqual(parse_range_header("bytes=0-99", 1000), (0, 99))

    def test_parse_open_start_range(self):
        self.assertEqual(parse_range_header("bytes=500-", 1000), (500, 999))

    def test_parse_suffix_range(self):
        self.assertEqual(parse_range_header("bytes=-200", 1000), (800, 999))

    def test_rejects_invalid_range(self):
        self.assertIsNone(parse_range_header("bytes=900-100", 1000))
        self.assertIsNone(parse_range_header("invalid", 1000))
