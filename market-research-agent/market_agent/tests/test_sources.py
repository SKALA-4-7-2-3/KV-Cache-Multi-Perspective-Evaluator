import unittest
from pathlib import Path
from market_agent.parser import read_input
from market_agent.sources import select_segments, rank_candidates, fallback_url


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.tech = read_input(Path(__file__).parents[1]/'fixtures/input.md').technologies['SW-01']

    def test_finds_late_evidence_and_preserves_restriction_and_offsets(self):
        raw = ('Navigation menu unrelated links.\n\n' * 600) + '# RDKV deployment\n\nRDKV integration is experimental.\n\nNot supported for production use.\n'
        segments = select_segments(raw, self.tech, ['ecosystem_support'])
        joined = '\n'.join(s.text for s in segments)
        self.assertIn('Not supported for production use', joined)
        self.assertIn('RDKV integration', joined)
        self.assertLessEqual(sum(len(s.text) for s in segments), 12000)
        for s in segments:
            self.assertEqual(raw[s.start:s.end], s.text)

    def test_relevant_direct_source_precedes_adjacent_high_search_rank(self):
        candidates = [dict(url='https://example.org/ai', title='AI infrastructure', content='LLM memory'),
            dict(url='https://github.com/lab/rdkv', title='RDKV official implementation', content='RDKV support license')]
        ordered = rank_candidates(candidates, self.tech, ['commercialization'])
        self.assertEqual(ordered[0]['url'], candidates[1]['url'])

    def test_fallback_only_transforms_known_arxiv_document(self):
        self.assertEqual(fallback_url('https://arxiv.org/pdf/2605.08317v1'), 'https://arxiv.org/abs/2605.08317v1')
        self.assertIsNone(fallback_url('https://example.org/report.pdf'))
