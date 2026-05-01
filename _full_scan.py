import requests, time, json
r = requests.post('http://localhost:5555/api/scan/start', json={'limit': 3000}, timeout=10)
print('task_id:', r.json()['task_id'])

while True:
    time.sleep(8)
    pr = requests.get('http://localhost:5555/api/scan/progress', timeout=5)
    p = pr.json()['data']
    if p['total'] > 0:
        print(f"  {p['progress']}/{p['total']} ({p['percent']:.0f}%) matched={p['matched']}")
    if not p['running']:
        break

d = json.load(open('results/latest_scan.json','r',encoding='utf-8'))
print(f"\nDone: {d['scan_time']}")
print(f"Total scanned: {d['total_scanned']}  Matched: {d['matched']}")

ongoing = [r for r in d['results'] if r['consolidation_end_date'] >= '2026-04-27']
print(f"Ongoing (横盘中): {len(ongoing)}")

d['results'].sort(key=lambda x: x['pattern_score'], reverse=True)
print("\nTop 20 by score:")
for r in d['results'][:20]:
    status = 'ACTIVE' if r['consolidation_end_date'] >= '2026-04-27' else r['consolidation_end_date']
    print(f"  {r['stock_code']} {r['stock_name']} score={r['pattern_score']:.2f} gain={r['uptrend_gain']:.1%} consol={r['consolidation_days']}d {status}")
