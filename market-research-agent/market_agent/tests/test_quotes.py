import unittest
from pathlib import Path

from market_agent.parser import read_input
from market_agent.schemas import Evidence, SelectedClaim, SelectedExtraction


class QuoteTests(unittest.TestCase):
    def setUp(self):
        self.data=read_input(Path(__file__).parents[1]/'fixtures/input.md')
        self.e=Evidence(id='MKT-X',doc_id='WEB-X',title='PF-NIC support',url='https://example.org/support',
            excerpt='PF-NIC supports shared CXL memory for AI inference. Evaluation partners can access the software under a research license.',
            access_status='full_text',content_status='substantive',tech_ids=['HW-01'])

    def test_quotes_are_original_substrings_and_input_summaries_are_excluded(self):
        from market_agent.quotes import quote_bank
        bank=quote_bank({**self.data.evidence,self.e.id:self.e})
        self.assertTrue(bank)
        for item in bank.values():
            self.assertEqual(item['evidence_id'],self.e.id)
            self.assertIn(item['text'],self.e.excerpt)
            self.assertLessEqual(len(item['text'].split()),25)

    def test_model_selects_id_and_cannot_supply_a_fabricated_quote(self):
        from market_agent.quotes import quote_bank, resolve_quotes
        bank=quote_bank({self.e.id:self.e})
        qid=next(iter(bank))
        claim=SelectedClaim(tech_id='HW-01',criterion_id='ecosystem_support',statement='공급사는 PF-NIC 지원을 설명함',
            basis='fact',relation_to_technology='method_family',quote_id=qid,subject='PF-NIC',conditions=['연결 미확인'],metric=None)
        answer=resolve_quotes(self.data,SelectedExtraction(claims=[claim],reviews=[]),bank,{self.e.id:self.e})
        self.assertEqual(answer.claims[0].citation.quote,bank[qid]['text'])
        self.assertEqual(answer.claims[0].citation.evidence_id,self.e.id)

    def test_unknown_quote_id_is_not_relinked_to_an_unrelated_source(self):
        from market_agent.quotes import resolve_quotes
        claim=SelectedClaim(tech_id='HW-01',criterion_id='ecosystem_support',statement='unsupported',basis='fact',
            relation_to_technology='method_family',quote_id='invented',subject='PF-NIC',conditions=[],metric=None)
        answer=resolve_quotes(self.data,SelectedExtraction(claims=[claim],reviews=[]),{}, {})
        self.assertEqual(answer.claims[0].citation.evidence_id,'unknown_quote:invented')
