import requests, time, json

r = requests.post('http://localhost:5555/api/scan/start', json={'limit': 800}, timeout=10)
print('scan started:', r.json()['task_id'])

while True:
    time.sleep(3)
    pr = requests.get('http://localhost:5555/api/scan/progress', timeout=5)
    p = pr.json()['data']
    if p['total'] > 0:
        print(f"  {p['progress']}/{p['total']} ({p['percent']:.0f}%) matched={p['matched']}")
    if not p['running']:
        break

if json.load(open('results/latest_scan.json','r',encoding='utf-8')).get('matched', 0) == 0:
    print("\n⚠️ 800只零匹配！回撤检查太严了，试试放宽到15%...")
    # Skip to analysis without another scan
    
import sys; sys.path.insert(0,'.')
from data.fetcher import DataFetcher
from pattern.recognizer import PatternRecognizer
from _config import FACTORY_PATTERN

f = DataFetcher()
cfg = dict(FACTORY_PATTERN)
cfg['max_retrace_pct'] = 0.08
r = PatternRecognizer(cfg)

# Test the 4 previously matched stocks with the new rule
codes = ['600089','600188','600546','600585']
for code in codes:
    df = f.daily_data(code, days=500)
    p = r.find_pattern(df)
    if p:
        print(f'  {code}: MATCH retrace bypassed (unexpected)')
    else:
        print(f'  {code}: REJECTED (correct - dropped too much from peak)')

# Now test with looser retrace to find real candidates
cfg2 = dict(FACTORY_PATTERN)
cfg2['max_retrace_pct'] = 0.15
r2 = PatternRecognizer(cfg2)
print(f'\nWith retrace=15%:')
for code in codes:
    df = f.daily_data(code, days=500)
    p = r2.find_pattern(df)
    if p:
        peak = float(df[df['date'].dt.strftime('%Y-%m-%d') == p['uptrend_end_date']]['close'].iloc[0]) if not df[df['date'].dt.strftime('%Y-%m-%d') == p['uptrend_end_date']].empty else 0
        min_p = float(df.loc[p['uptrend_end_idx']:p['consolidation_end_idx'], 'close'].min())
        act_retrace = (peak - min_p) / peak * 100 if peak else 0
        print(f'  {code}: rejected (actual retrace={act_retrace:.1f}%)')
    else:
        print(f'  {code}: no match')

f.close()
