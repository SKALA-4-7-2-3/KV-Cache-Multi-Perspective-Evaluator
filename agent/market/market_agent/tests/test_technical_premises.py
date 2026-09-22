import unittest
from pathlib import Path
from market_agent.parser import read_input
from market_agent.schemas import SelectedClaim, SelectedExtraction
from market_agent.quotes import quote_bank, resolve_quotes
from market_agent.claims import validate_claims
from market_agent.tests.test_json_input import SW, HW


class TechnicalPremiseTests(unittest.TestCase):
    def test_registered_excerpt_can_support_only_conditional_customer_value(self):
        data=read_input([SW,HW],as_of='2026-09-22')
        tech=data.technologies['HW-01'];e=data.evidence[tech.evidence_ids[0]]
        e.excerpt='PF Memory Appliance can expand shared memory capacity for long-context inference.'
        bank=quote_bank({e.id:e},technical_ids={e.id})
        self.assertTrue(bank)
        item=SelectedClaim(tech_id=tech.id,criterion_id='business_value',statement='공유 메모리 용량 확장 가능성을 제시함',
            basis='inference',relation_to_technology='exact',quote_id=next(iter(bank)),subject='PF Memory Appliance',
            conditions=['입력 연구 조건의 재현 및 고객 비용 검증 필요'],metric=None,evidence_level='inference')
        claims=resolve_quotes(data,SelectedExtraction(claims=[item],reviews=[]),bank,{e.id:e}).claims
        pool,errors=validate_claims(data,claims,{e.id:e})
        self.assertFalse(errors);self.assertTrue(pool)
        self.assertIn('독립',claims[0].citation.source_character)
        for criterion in ('commercialization','adoption','ecosystem_support'):
            bad=claims[0].model_copy(update={'criterion_id':criterion})
            self.assertFalse(validate_claims(data,[bad],{e.id:e})[0])
        unowned=e.model_copy(update={'tech_ids':['SW-01']})
        self.assertFalse(validate_claims(data,claims,{e.id:unowned})[0])
