"""Offline persistence tests: raw cache reuse confers no Judge approval."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pipeline.report_quality import JudgeResponseCache


class JudgeResponseCacheTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.output = Path(directory.name)
        self.cache = JudgeResponseCache(self.output)
        self.request = {"model": "offline-model", "instructions": "원문만 검사한다.",
            "prompt": "원래 줄\n공백  보존", "strict_schema": {
                "type": "object", "properties": {"checks": {"type": "array"}},
                "required": ["checks"]}, "format_version": 1}
        self.raw = '{\n  "checks": ["한글 café 🧪\\n"],\n  "note": "줄 끝"\n}\r\n'

    def path(self):
        return next((self.output / "quality-responses").glob("*.json"))

    def test_unicode_newlines_and_request_key_order_round_trip_exactly(self):
        self.assertIsNone(self.cache.load(self.request))
        self.cache.save(self.request, self.raw)
        reordered = dict(reversed(list(self.request.items())))
        reordered["strict_schema"] = dict(reversed(list(self.request["strict_schema"].items())))
        reopened = JudgeResponseCache(self.output)
        self.assertEqual(reopened.load(reordered), self.raw)

    def test_every_request_boundary_invalidates_cached_response(self):
        self.cache.save(self.request, self.raw)
        changes = {"model": "other-model", "instructions": "changed instructions",
                   "prompt": "changed actual input", "format_version": 2,
                   "strict_schema": {"type": "object", "required": ["new_field"]}}
        for field, value in changes.items():
            with self.subTest(field=field):
                request = deepcopy(self.request)
                request[field] = value
                self.assertIsNone(self.cache.load(request))
        self.assertEqual(self.cache.load(self.request), self.raw)

    def test_corrupt_mismatched_or_missing_envelope_is_cache_miss(self):
        self.cache.save(self.request, self.raw)
        original = json.loads(self.path().read_text())
        for field, value in (("key", "0" * 64), ("version", 99), ("version", True),
                             ("raw", 42), ("raw", "tampered"), ("raw_sha256", "0" * 64)):
            with self.subTest(field=field, value=value):
                envelope = {**original, field: value}
                self.path().write_text(json.dumps(envelope))
                self.assertIsNone(self.cache.load(self.request))
        for raw_file in (b"{unfinished", b"[]", b"{}", b"\xff\xfe"):
            with self.subTest(raw_file=raw_file):
                self.path().write_bytes(raw_file)
                self.assertIsNone(self.cache.load(self.request))
        self.path().unlink()
        self.assertIsNone(self.cache.load(self.request))

    def test_atomic_save_and_failed_replace_leave_no_temporary_files(self):
        self.cache.save(self.request, self.raw)
        with patch("pathlib.Path.replace", side_effect=OSError("offline replacement failure")):
            with self.assertRaises(OSError):
                self.cache.save(self.request, "new response")
        self.assertEqual(self.cache.load(self.request), self.raw)
        self.assertEqual(list((self.output / "quality-responses").iterdir()), [self.path()])
        self.cache.save(self.request, "second response\n")
        self.assertEqual(self.cache.load(self.request), "second response\n")
        self.assertEqual(list((self.output / "quality-responses").iterdir()), [self.path()])


if __name__ == "__main__":
    unittest.main()
