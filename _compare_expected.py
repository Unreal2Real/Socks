"""Show algorithm vs user side by side"""
import sys; sys.path.insert(0,'.')
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

hit = 0
total = 0

for code, (u_start, u_end, c_end) in expected.items():
    total += 1
    df = f.daily_data(code, days=1000 if code == '003036' else 500)
    p = r.find_pattern(df, max_days_back=SCAN.get('max_days_back'))
    
    if not p:
        print(f'{code}: MISS')
        continue
    
    algo_u_start = p['uptrend_start_date']
    algo_u_end = p['uptrend_end_date']
    algo_c_end = p['consolidation_end_date']
    
    start_match = abs((f.daily_data.__wrapped__ if hasattr(f.daily_data,'__wrapped__') else 0) or algo_u_start[:7] == u_start[:7])
    
    # Calculate day differences
    from datetime import date
    us_a = date.fromisoformat(algo_u_start)
    us_e = date.fromisoformat(u_start)
    ue_a = date.fromisoformat(algo_u_end)
    ue_e = date.fromisoformat(u_end)
    ce_a = date.fromisoformat(algo_c_end)
    ce_e = date.fromisoformat(c_end)
    
    start_off = abs((us_a - us_e).days)
    peak_off = abs((ue_a - ue_e).days)
    end_off = abs((ce_a - ce_e).days)
    
    ok = '✅' if start_off <= 10 and peak_off <= 5 else '⚠️'
    
    print(f'{code}: {ok}')
    print(f'  你:  上{u_start}→{u_end}  盘→{c_end}')
    print(f'  算法: 上{algo_u_start}→{algo_u_end}  盘→{algo_c_end}')
    print(f'  差:  起点{start_off}d  峰顶{peak_off}d  结束{end_off}d')
    
    if start_off <= 10 and peak_off <= 5:
        hit += 1
    print()

f.close()
print(f'Window match (≤10d start, ≤5d peak): {hit}/{total}')
