"""동일한 수량의 배율·통화 표현만 정규화한다. 단위와 대상 범위는 유지한다."""
import re
from decimal import Decimal

SCALES = {'thousand': 1000, 'million': 1000000, 'billion': 1000000000, 'trillion': 1000000000000}
CURRENCY = r'USD|EUR|KRW|US dollars?|dollars?|euros?|[$€₩]'
QUANTITY = re.compile(rf'(?P<prefix>{CURRENCY})?\s*(?P<number>\d[\d,]*(?:\.\d+)?)\s*'
    rf'(?P<scale>thousand|million|billion|trillion)?\s*(?P<unit>{CURRENCY}|units?|modules?|percent|%)?', re.I)


def currency(text):
    text=text.lower().strip()
    if text in {'usd','$','dollar','dollars','us dollar','us dollars'}:return 'USD'
    if text in {'eur','€','euro','euros'}:return 'EUR'
    if text in {'krw','₩'}:return 'KRW'
    return None


def scale(text):
    return next((Decimal(v) for k,v in SCALES.items() if re.search(r'\b'+k+r'\b',text,re.I)),Decimal(1))


def dimension(text):
    if re.search(r'\bunits?\b|\bmodules?\b',text,re.I):return 'count'
    if '%' in text or re.search(r'\bpercent\b',text,re.I):return 'percent'
    return None


def definition_words(text):
    text=re.sub(r'production volume','production',text.lower())
    return {w.rstrip('s') for w in re.findall(r'[^\W\d_]+',text,re.U)
        if w not in {'of','the','global','worldwide','in'}}


def metric_matches_quote(metric, quote):
    text=' '.join(quote.lower().split())
    definition=definition_words(metric.market_definition)
    if not definition or not definition <= definition_words(text):return False
    region=metric.geography.lower().strip()
    if region in {'global','worldwide'}:
        if not re.search(r'\b(global|worldwide)\b',text):return False
    elif region not in text:return False
    requested_currency=(metric.currency or '').upper() or None
    unit_currency=next((currency(m[0]) for m in re.finditer(CURRENCY,metric.unit,re.I)),None)
    if unit_currency and unit_currency!=requested_currency:return False
    requested_dimension=dimension(metric.unit)
    if not requested_dimension:
        requested_dimension='money' if requested_currency else None
    if not requested_dimension:return False
    desired=Decimal(str(metric.value))*scale(metric.unit)
    # 같은 문장 안의 다른 수량을 혼동하지 않는다. while 절은 연도·대상만 상속한다.
    clauses=re.split(r'\s*,?\s+while\s+|;|(?<=[.!?])\s+',text)
    for clause in clauses:
        years=re.findall(r'\b(?:19|20)\d{2}\b',clause)
        if metric.year not in (years or re.findall(r'\b(?:19|20)\d{2}\b',text)):continue
        if not definition <= definition_words(clause):continue
        if ('capacity' in metric.market_definition.lower()) != ('capacity' in clause):continue
        forecast=bool(re.search(r'forecast|projected|expected|predict|전망|예상',clause))
        if forecast != (metric.actual_or_forecast=='forecast'):continue
        for match in QUANTITY.finditer(clause):
            amount=Decimal(match['number'].replace(',',''))*scale(match['scale'] or '')
            if amount!=desired:continue
            unit=match['unit'] or ''
            actual_currency=currency(match['prefix'] or '') or currency(unit)
            actual_dimension=dimension(unit) or ('money' if actual_currency else None)
            if actual_dimension!=requested_dimension or actual_currency!=requested_currency:continue
            return True
    return False


def numeric_tokens(text):
    """번역문 숫자 비교: million/billion 및 쉼표 표기를 같은 값으로 본다."""
    values=set()
    for match in re.finditer(r'(?<![A-Za-z0-9])(?P<n>\d[\d,]*(?:\.\d+)?)\s*(?P<s>thousand|million|billion|trillion)?',text,re.I):
        values.add(Decimal(match['n'].replace(',',''))*scale(match['s'] or ''))
    return values
