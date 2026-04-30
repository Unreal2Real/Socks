import sys; sys.path.insert(0,'.')
from data.fetcher import DataFetcher
from pattern.recognizer import PatternRecognizer
from _config import FACTORY_PATTERN, SCAN
from datetime import date

f = DataFetcher()
r = PatternRecognizer(FACTORY_PATTERN)
stocks = f.stock_list()[:500]
total = sum(1 for c,n in stocks if not f.daily_data(c, days=500).empty and len(f.daily_data(c, days=500))>=60)
matched=0; ongoing=0; recent=0

for code, name in stocks:
    df = f.daily_data(code, days=500)
    if df.empty or len(df) < 60: continue
    p = r.find_pattern(df, max_days_back=SCAN.get('max_days_back'))
    if not p: continue
    matched += 1
    if p['consolidation_end_date'] >= '2026-04-28': ongoing += 1
    if (date.today() - date.fromisoformat(p['consolidation_end_date'])).days <= 60: recent += 1

print('Scanned:', total, 'Matched:', matched, 'Ongoing:', ongoing, 'Recent60d:', recent)
print('Rate:', round(matched/total*100,1), '%')

# Check 000421
df = f.daily_data('000421', days=500)
p = r.find_pattern(df, max_days_back=SCAN.get('max_days_back'))
if p:
    print('000421: MATCH score=', p['pattern_score'], 'gain=', round(p['uptrend_gain']*100,1), '%')
else:
    print('000421: MISS')
f.close()
