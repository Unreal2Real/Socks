"""Test all 8 ref stocks with actual recognizer"""
import sys; sys.path.insert(0,'.')
from data.fetcher import DataFetcher
from pattern.recognizer import PatternRecognizer
from _config import FACTORY_PATTERN, SCAN

f = DataFetcher()
r = PatternRecognizer(FACTORY_PATTERN)
refs = ['603629','002008','300136','002796','003036','002149','002655','002980']

print(f'TESTING: gain>={FACTORY_PATTERN["uptrend_gain"]:.0%}  consol>={FACTORY_PATTERN["consolidation_days_min"]}d  elev>={FACTORY_PATTERN["min_elevation"]:.0%}')
print()

passed = 0
for code in refs:
    df = f.daily_data(code, days=1000 if code in ['003036','300136'] else 500)
    if df.empty:
        print(f'{code}: NO DATA')
        continue
    p = r.find_pattern(df, max_days_back=SCAN.get('max_days_back'))
    if p:
        passed += 1
        print(f'{code}: ✅ MATCH  score={p["pattern_score"]:.2f}  gain={p["uptrend_gain"]:.1%}  consol={p["consolidation_days"]}d')
        print(f'      上涨: {p["uptrend_start_date"]}->{p["uptrend_end_date"]}  盘整->{p["consolidation_end_date"]}')
    else:
        print(f'{code}: ❌ MISS')

f.close()
print(f'\nResult: {passed}/{len(refs)}')
