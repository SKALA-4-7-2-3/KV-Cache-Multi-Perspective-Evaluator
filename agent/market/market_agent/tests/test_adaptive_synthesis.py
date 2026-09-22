import unittest
from pathlib import Path
from market_agent.parser import read_input
from market_agent.schemas import Analysis, Evidence, Synthesis, SynthesisRow, SynthesisReview, SynthesisReviews


class AdaptiveSynthesisTests(unittest.TestCase):
    def setUp(self):
        self.data=read_input(Path(__file__).parents[1]/'fixtures/input.md')
        self.source=Evidence(id='MKT-native',doc_id='DOC-native',title='RDKV integration',url='https://example.org/rdkv',
            excerpt='RDKV plugs into the serving stack without altering trained weights',
            access_status='full_text',content_status='substantive',tech_ids=['SW-01'])

    def apply(self,relation='exact',level=0,judgment='기존 추론 스택에 연결하는 PoC 경로를 우선 검토한다.',review_supported=True):
        from market_agent.adaptive_materials import build_packet
        from market_agent.synthesis import apply_synthesis
        evidence={self.source.id:self.source}
        packet=build_packet(self.data,evidence,level)
        draft=Synthesis(assessments=[SynthesisRow(tech_id='SW-01',criterion_id='ecosystem_support',
            observation='학습 가중치를 변경하지 않고 추론 스택에 연결한다는 자료가 있다.',
            judgment=judgment,relation_to_technology=relation,quote_ids=[next(iter(packet))],
            conditions=['대상 환경에서 연결 가능 여부를 재현한다.'],limitations=['지원 버전은 별도 확인'])])
        review=SynthesisReviews(reviews=[SynthesisReview(tech_id='SW-01',criterion_id='ecosystem_support',
            supported=review_supported,relevant=True,scope_preserved=True,uncertainty_preserved=True,reason='자료와 판단 범위 대조')])
        return apply_synthesis(self.data,Analysis(assessments=[],followup_questions=[]),draft,review,packet,evidence,level,
            targets=[('SW-01','ecosystem_support')])

    def test_synonym_without_support_keyword_passes_semantic_review(self):
        result,errors,records=self.apply()
        self.assertFalse(errors)
        row=result.assessments[0]
        self.assertEqual(row.generation_method,'model_synthesis')
        self.assertIn('PoC 경로',row.judgment)
        self.assertIn('가중치',row.observation)
        self.assertTrue(records)

    def test_level_zero_defers_related_claim_but_level_one_evaluates_it(self):
        early,errors,_=self.apply(relation='method_family')
        later,later_errors,_=self.apply(relation='method_family',level=1)
        self.assertFalse(early.assessments)
        self.assertTrue(errors)
        self.assertFalse(later_errors)
        self.assertEqual(later.assessments[0].evaluation_mode,'provisional')

    def test_model_judgment_is_used_instead_of_predefined_decision(self):
        first,_,_=self.apply(judgment='플러그인 설치 경로를 우선 검토한다.')
        second,_,_=self.apply(judgment='관리 계층을 추가하는 연결 경로를 우선 검토한다.')
        self.assertNotEqual(first.assessments[0].judgment,second.assessments[0].judgment)

    def test_rejected_semantic_review_never_becomes_verified_output(self):
        result,errors,_=self.apply(review_supported=False)
        self.assertFalse(result.assessments)
        self.assertTrue(errors)

    def test_ungrounded_numbers_fail_even_in_broadest_stage(self):
        result,errors,_=self.apply(level=2,judgment='비용이 42% 감소하므로 도입한다.')
        self.assertFalse(result.assessments)
        self.assertTrue(any(e['code']=='unsupported_number' for e in errors))


class TranslatedQuantityTests(unittest.TestCase):
    def test_korean_and_english_quantity_scales_are_equivalent(self):
        from market_agent.quantities import numeric_tokens
        self.assertEqual(numeric_tokens('1.44 million units'),numeric_tokens('144만 대'))
        self.assertEqual(numeric_tokens('1.9 billion dollars'),numeric_tokens('19억 달러'))
        self.assertNotEqual(numeric_tokens('1.9 billion dollars'),numeric_tokens('19만 달러'))
