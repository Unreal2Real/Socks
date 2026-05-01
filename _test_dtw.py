"""Test DTW-enhanced recognizer on 8 reference stocks"""
import sys; sys.path.insert(0,'.')
import pandas as pd
from data.fetcher import DataFetcher
from pattern.recognizer import PatternRecognizer
from _config import FACTORY_PATTERN, SCAN

f = DataFetcher()
r = PatternRecognizer(FACTORY_PATTERN)

expected = {
    '603629': ('2026-01-21', '2026-02-12', '2026-04-07'),
    '002008': ('2026-02-12', '2026-03-02', '2026-04-07'),
    '300136': ('2025-12-24', '2026-01-22', '2026-04-13'),
    '002796': ('2025-12-16', '2026-01-28', '2026-02-12'),
    '003036': ('2025-06-16', '2025-08-06', '2026-03-17'),
    '002149': ('2025-12-01', '2026-01-12', '2026-04-14'),
    '002655': ('2026-02-10', '2026-03-02', '2026-04-02'),
    '002980': ('2026-02-25', '2026-03-11', '2026-03-27'),
}

print('DTW-enhanced Pattern Recognizer Test')
print('=' * 70)

hits_start = 0
hits_peak = 0
hits_end = 0

for code, (u_start, u_end, c_end) in expected.items():
    df = f.daily_data(code, days=1000 if code == '003036' else 500)
    if df.empty:
        print(f'{code}: NO DATA')
        continue

    p = r.find_pattern(df, max_days_back=SCAN.get('max_days_back'))

    if not p:
        print(f'{code}: ❌ MISS')
        continue

    start_off = abs((pd.Timestamp(p['uptrend_start_date']) - pd.Timestamp(u_start)).days)
    peak_off = abs((pd.Timestamp(p['uptrend_end_date']) - pd.Timestamp(u_end)).days)
    end_off = abs((pd.Timestamp(p['consolidation_end_date']) - pd.Timestamp(c_end)).days)

    if start_off <= 4: hits_start += 1
    if peak_off <= 2: hits_peak += 1
    if end_off <= 2: hits_end += 1

    s_ok = '✅' if start_off <= 4 else '⚠️'
    p_ok = '✅' if peak_off <= 2 else '⚠️'
    e_ok = '✅' if end_off <= 2 else '⚠️'

    print(f'{code}:')
    print(f'  {s_ok} start: {p["uptrend_start_date"]} (expected {u_start}, off by {start_off}d)')
    print(f'  {p_ok} peak:  {p["uptrend_end_date"]} (expected {u_end}, off by {peak_off}d)')
    print(f'  {e_ok} end:   {p["consolidation_end_date"]} (expected {c_end}, off by {end_off}d)')
    print(f'  score={p["pattern_score"]:.2f}  dtw_sim={p.get("dtw_similarity",0):.2f}  match={p.get("dtw_matched_template","")}')

f.close()
print()
print(f'Results: start≤4d={hits_start}/8  peak≤2d={hits_peak}/8  end≤2d={hits_end}/8')
