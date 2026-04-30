import requests, time, json

r = requests.post('http://localhost:5555/api/scan/start', json={'limit': 2000}, timeout=10)
print('scan started:', r.json()['task_id'])

while True:
    time.sleep(5)
    pr = requests.get('http://localhost:5555/api/scan/progress', timeout=5)
    p = pr.json()['data']
    if p['total'] > 0: print(f"  {p['progress']}/{p['total']} ({p['percent']:.0f}%) matched={p['matched']}")
    if not p['running']: break

d = json.load(open('results/latest_scan.json','r',encoding='utf-8'))
print(f"\nDone: {d['scan_time']}, matched={d['matched']}")

ongoing = [r for r in d['results'] if r['consolidation_end_date'] >= '2026-04-28']
completed = [r for r in d['results'] if r['consolidation_end_date'] < '2026-04-28']
print(f'Ongoing (up to today): {len(ongoing)}')
print(f'Completed earlier: {len(completed)}')

print('\nTop 10 by score:')
d['results'].sort(key=lambda x: x['pattern_score'], reverse=True)
for r in d['results'][:10]:
    status = '横盘中' if r['consolidation_end_date'] >= '2026-04-28' else f"完成{r['consolidation_end_date']}"
    print(f"  {r['stock_code']} {r['stock_name']} score={r['pattern_score']:.2f} gain={r['uptrend_gain']:.1%} {status}")
