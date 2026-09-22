"""원문 형식을 보존하면서 단계별로 조사 자료 범위를 넓히는 공개 계약."""
import unittest
from datetime import date
from pathlib import Path

from market_agent.parser import read_input
from market_agent.schemas import Evidence


class AdaptiveMaterialTests(unittest.TestCase):
    def setUp(self):
        self.data = read_input(Path(__file__).parents[1] / 'fixtures/input.md')

    def source(self, key, text, tech='SW-01', **updates):
        values = dict(
            id=key, doc_id='DOC-' + key, title='Synthetic material ' + key,
            url='https://example.org/' + key, excerpt=text, locator='Source section',
            published_at=date(2026, 9, 1), access_status='full_text',
            content_status='substantive', tech_ids=[tech],
        )
        values.update(updates)
        return Evidence(**values)

    def packet(self, evidence, level):
        from market_agent.adaptive_materials import build_packet
        return build_packet(self.data, evidence, level)

    def assert_original_materials(self, packet, evidence):
        self.assertIsInstance(packet, dict)
        for quote_id, item in packet.items():
            with self.subTest(quote_id=quote_id):
                self.assertIsInstance(quote_id, str)
                self.assertTrue(quote_id)
                self.assertIn(item['evidence_id'], evidence)
                original = evidence[item['evidence_id']]
                self.assertTrue(item['text'].strip())
                self.assertIn(item['text'], original.excerpt)
                self.assertEqual(item['access_status'], original.access_status)
                self.assertEqual(item['content_status'], original.content_status)
                self.assertTrue(item['locator'])
                self.assertEqual(set(item['tech_ids']), set(original.tech_ids))

    def test_related_body_without_fixed_market_keywords_reaches_semantic_review(self):
        source = self.source(
            'MKT-no-keyword',
            'The distribution remains skewed across requests and the retained fraction varies by layer',
        )
        evidence = {source.id: source}

        packet = self.packet(evidence, 0)

        self.assertEqual({item['evidence_id'] for item in packet.values()}, {source.id})
        self.assert_original_materials(packet, evidence)

    def test_table_short_item_and_long_paragraph_are_not_discarded_for_format(self):
        sources = [
            self.source('MKT-table', '| Release | Terms |\n| --- | --- |\n| Preview | Academic only |'),
            self.source('MKT-short', 'Academic only'),
            self.source('MKT-long', ' '.join(
                f'Layer-{index} retains an independently selected fraction according to the observed distribution'
                for index in range(180)
            )),
        ]
        for source in sources:
            with self.subTest(source=source.id):
                evidence = {source.id: source}
                packet = self.packet(evidence, 0)
                self.assertTrue(packet, '문장부호·단어 수·표 형식으로 전체 자료를 잃으면 안 됩니다')
                self.assertEqual({item['evidence_id'] for item in packet.values()}, {source.id})
                self.assert_original_materials(packet, evidence)

    def test_levels_add_provided_summaries_then_search_snippets_without_promotion(self):
        body = self.source('MKT-body', 'A related implementation describes its integration boundary')
        summary = self.source('UPSTREAM-summary', '상위 기술 분석자가 기록한 적용 조건',
                              access_status='provided_summary', content_status='unchecked')
        snippet = self.source('SEARCH-snippet', '검색 결과에 표시된 관련 제품 소개',
                              access_status='snippet', content_status='unchecked')
        evidence = {item.id: item for item in [body, summary, snippet]}

        for level, expected in [
            (0, {body.id}),
            (1, {body.id, summary.id}),
            (2, {body.id, summary.id, snippet.id}),
        ]:
            with self.subTest(level=level):
                packet = self.packet(evidence, level)
                self.assertEqual({item['evidence_id'] for item in packet.values()}, expected)
                self.assert_original_materials(packet, evidence)

    def test_future_metadata_identity_mismatch_and_failed_sources_are_excluded_at_every_level(self):
        good = self.source('MKT-good', 'The implementation is available under academic terms')
        blocked = [
            self.source('MKT-future', 'Future release description', published_at=date(2027, 1, 1)),
            self.source('MKT-metadata', 'Title and authors only', content_status='metadata_only'),
            self.source('MKT-mismatch', 'An unrelated namesake', content_status='identity_mismatch'),
            self.source('MKT-failed', 'Search snippet after failed retrieval',
                        access_status='failed', content_status='unchecked'),
        ]
        evidence = {item.id: item for item in [good, *blocked]}

        for level in [0, 1, 2]:
            with self.subTest(level=level):
                packet = self.packet(evidence, level)
                self.assertEqual({item['evidence_id'] for item in packet.values()}, {good.id})
                self.assert_original_materials(packet, evidence)

    def test_many_sources_for_one_technology_cannot_exclude_the_other_technology(self):
        software = [self.source(f'MKT-SW-{index}', f'Layer {index} retains a bounded representation')
                    for index in range(30)]
        hardware = self.source('MKT-HW', 'Passive optical links connect several hosts', tech='HW-01')
        evidence = {item.id: item for item in [*software, hardware]}

        packet = self.packet(evidence, 0)

        technologies = {tech for item in packet.values() for tech in item['tech_ids']}
        self.assertEqual(technologies, {'SW-01', 'HW-01'})
        self.assertIn(hardware.id, {item['evidence_id'] for item in packet.values()})
        self.assert_original_materials(packet, evidence)

    def test_quote_ids_are_stable_and_equal_text_from_different_owners_is_not_merged(self):
        text = 'Evaluation copies are distributed under academic terms'
        software = self.source('MKT-SW-identical', text)
        hardware = self.source('MKT-HW-identical', text, tech='HW-01')
        evidence = {software.id: software, hardware.id: hardware}

        first = self.packet(evidence, 0)
        repeated = self.packet(evidence, 0)
        reversed_order = self.packet(dict(reversed(list(evidence.items()))), 0)

        self.assertEqual(first, repeated)
        self.assertEqual(first, reversed_order)
        self.assertEqual({item['evidence_id'] for item in first.values()}, set(evidence))
        self.assert_original_materials(first, evidence)


if __name__ == '__main__':
    unittest.main()

class SourceBalanceTests(unittest.TestCase):
    setUp=AdaptiveMaterialTests.setUp
    source=AdaptiveMaterialTests.source
    packet=AdaptiveMaterialTests.packet
    def test_title_only_fragment_does_not_displace_real_body(self):
        title='# Title:RDKV KV cache inference product support release'
        body='Academic evaluation only; contact the authors for licensing'
        source=self.source('paper',title+'\n\n'+body)
        other=self.source('other','The runtime accepts custom adapters')
        packet=self.packet({source.id:source,other.id:other},0)
        self.assertIn(body,[p['text'] for p in packet.values()])
        self.assertNotIn(title,[p['text'] for p in packet.values()])
    def test_many_registry_fragments_do_not_crowd_out_web_sources(self):
        provided={f'P{i}':self.source(f'P{i}','RDKV memory inference support cost '*40,
            access_status='provided_summary',url='https://example.org/paper',doc_id='one-paper') for i in range(30)}
        web=self.source('MKT-web','The runtime accepts plug-in adapters',url='https://example.org/runtime')
        packet=self.packet({**provided,web.id:web},1)
        self.assertIn(web.id,{p['evidence_id'] for p in packet.values()})
        self.assertIn('provided_summary',{p['access_status'] for p in packet.values()})


class StructuredContentTests(unittest.TestCase):
    def test_short_unpunctuated_source_body_remains_eligible(self):
        from market_agent.sources import content_quality
        data=read_input(Path(__file__).parents[1]/'fixtures/input.md')
        self.assertEqual(content_quality('# Terms\n\nAcademic only','https://example.org/terms',data.technologies['SW-01'])[0],'substantive')

    def test_table_only_body_is_substantive_but_metadata_table_is_not(self):
        from market_agent.sources import content_quality
        from market_agent.parser import read_input
        from pathlib import Path
        data=read_input(Path(__file__).parents[1]/'fixtures/input.md')
        tech=data.technologies['SW-01']
        table='| Year | Revenue |\n| --- | --- |\n| 2025 | USD 10 million |'
        self.assertEqual(content_quality(table,'https://example.org/report',tech)[0],'substantive')
        terms='| Release | Terms |\n| --- | --- |\n| Preview | Academic only |'
        self.assertEqual(content_quality(terms,'https://example.org/terms',tech)[0],'substantive')
        self.assertEqual(content_quality('| Cite as | arXiv:2605.08317 |','https://example.org/paper',tech)[0],'metadata_only')
