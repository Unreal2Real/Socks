"""Quick test: new params + ongoing consolidation"""
import sys; sys.path.insert(0,'.')
from data.fetcher import DataFetcher
from pattern.recognizer import PatternRecognizer
from _config import FACTORY_PATTERN, SCAN
from datetime import date, timedelta

f = DataFetcher()
r = PatternRecognizer(FACTORY_PATTERN)
stocks = f.stock_list()[:500]

matches = []
ongoing = 0
for code, name in stocks:
    df = f.daily_data(code, days=500)
    if df.empty or len(df) < 60:
        continue
    p = r.find_pattern(df, max_days_back=SCAN.get('max_days_back'))
    if not p:
        continue
    
    # Check if it's ongoing (consolidation ends at last data point)
    n = len(df)
    if p['consolidation_end_idx'] == n - 1:
        ongoing += 1
        p['status_note'] = '横盘中'
    else:
        p['status_note'] = '已完成'
    
    # Check freshness
    end_date = date.fromisoformat(p['consolidation_end_date'])
    age = (date.today() - end_date).days
    p['age_days'] = age
    p['stock_code'] = code
    p['stock_name'] = name
    
    # Check retrace
    consol = df.loc[p['uptrend_end_idx']:p['consolidation_end_idx'], 'close']
    peak = float(df.loc[p['uptrend_end_idx'], 'close'])
    min_c = float(consol.min())
    p['actual_retrace'] = round((peak - min_c) / peak * 100, 1)
    
    matches.append(p)

# Filter by freshness
fresh = [m for m in matches if m['age_days'] <= 30]
completed = [m for m in matches if m['status_note'] == '已完成']
ongoing_list = [m for m in matches if m['status_note'] == '横盘中']

print(f'Total: {len(matches)} (completed={len(completed)} ongoing={len(ongoing_list)})')
print(f'Recent (<=30d): {len(fresh)}')
print()

print('=== All matches (sorted by score) ===')
matches.sort(key=lambda x: x['pattern_score'], reverse=True)
for m in matches[:20]:
    fresh_mark = '✓' if m['age_days'] <= 30 else f"({m['age_days']}d)"
    print(f"  {m['stock_code']} {m['stock_name']} score={m['pattern_score']:.2f} retrace={m['actual_retrace']}% age={fresh_mark} {m['status_note']} end={m['consolidation_end_date']}")

if fresh:
    print(f'\n=== Recent only ({len(fresh)}) ===')
    fresh.sort(key=lambda x: x['pattern_score'], reverse=True)
    for m in fresh:
        print(f"  {m['stock_code']} {m['stock_name']} score={m['pattern_score']:.2f} retrace={m['actual_retrace']}% {m['status_note']}")

f.close()
