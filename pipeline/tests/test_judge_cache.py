"""Offline persistence tests: raw cache reuse confers no Judge approval."""
from copy import deepcopy
from hashlib import sha256
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


    def test_verified_correction_redirect_keeps_actual_prompt_provenance_and_old_key(self):
        corrected = {**self.request, "prompt": self.request["prompt"] + "\ncontract correction"}
        self.cache.save(self.request, "old base response")
        base_path = self.output / "quality-responses" / (self.cache._request_key(self.request) + ".json")
        original = base_path.read_bytes()
        self.cache.save_verified(self.request, corrected, self.raw)
        self.assertEqual(self.cache.load(self.request), self.raw)
        self.assertEqual(self.cache.load(corrected), self.raw)
        self.assertEqual(base_path.read_bytes(), original)
        alias_path = base_path.with_suffix(".alias.json")
        alias = json.loads(alias_path.read_text())
        target = json.loads((alias_path.parent / (alias["target_key"] + ".json")).read_text())
        self.assertEqual(alias["base_key"], self.cache._request_key(self.request))
        self.assertEqual(alias["target_key"], self.cache._request_key(corrected))
        self.assertEqual(target["verified_base_key"], alias["base_key"])
        self.assertEqual(alias["actual_prompt_sha256"], target["actual_prompt_sha256"])
        self.assertEqual(alias["actual_prompt_sha256"], sha256(corrected["prompt"].encode()).hexdigest())
        self.assertFalse(list(alias_path.parent.glob("*.tmp")))

    def test_redirect_request_changes_and_unverified_save_are_misses(self):
        corrected = {**self.request, "prompt": "corrected prompt"}
        self.cache.save(corrected, self.raw)
        self.assertIsNone(self.cache.load(self.request))
        self.cache.save_verified(self.request, corrected, self.raw)
        for field, value in (("model", "new-model"), ("strict_schema", {"type": "string"}),
                             ("prompt", "different task"), ("format_version", 2)):
            with self.subTest(field=field):
                self.assertIsNone(self.cache.load({**self.request, field: value}))
        for changes in ({"model": "wrong-model"}, {"format_version": True}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.cache.save_verified(self.request, {**corrected, **changes}, self.raw)

    def test_corrupt_alias_or_target_is_a_miss_even_when_legacy_base_exists(self):
        corrected = {**self.request, "prompt": "corrected prompt"}
        self.cache.save(self.request, "old base response")
        self.cache.save_verified(self.request, corrected, self.raw)
        directory = self.output / "quality-responses"
        alias_path = directory / (self.cache._request_key(self.request) + ".alias.json")
        target_path = directory / (self.cache._request_key(corrected) + ".json")
        alias, target = json.loads(alias_path.read_text()), json.loads(target_path.read_text())
        for field, value in (("base_key", "0" * 64), ("target_key", "../outside"),
                             ("target_key", "0" * 64), ("version", True),
                             ("actual_prompt_sha256", "wrong"), ("actual_prompt_sha256", "0" * 64)):
            with self.subTest(alias_field=field):
                alias_path.write_text(json.dumps({**alias, field: value}))
                self.assertIsNone(self.cache.load(self.request))
        alias_path.write_text(json.dumps(alias))
        for field, value in (("verified_base_key", "0" * 64), ("key", "0" * 64),
                             ("version", 2), ("raw", "tampered"),
                             ("actual_prompt_sha256", "0" * 64)):
            with self.subTest(target_field=field):
                target_path.write_text(json.dumps({**target, field: value}))
                self.assertIsNone(self.cache.load(self.request))
        target_path.unlink()
        self.assertIsNone(self.cache.load(self.request))

    def test_new_verified_base_response_supersedes_old_redirect(self):
        corrected = {**self.request, "prompt": "corrected prompt"}
        self.cache.save_verified(self.request, corrected, self.raw)
        self.cache.save_verified(self.request, self.request, "new verified base")
        self.assertEqual(self.cache.load(self.request), "new verified base")
        self.assertFalse(list((self.output / "quality-responses").glob("*.alias.json")))


if __name__ == "__main__":
    unittest.main()
