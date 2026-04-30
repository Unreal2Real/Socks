import requests, time, json

r = requests.post('http://localhost:5555/api/scan/start', json={'limit': 2000}, timeout=10)
print('scan:', r.json()['task_id'])

while True:
    time.sleep(5)
    pr = requests.get('http://localhost:5555/api/scan/progress', timeout=5)
    p = pr.json()['data']
    if p['total'] > 0:
        print(f"  {p['progress']}/{p['total']} ({p['percent']:.0f}%) matched={p['matched']}")
    if not p['running']:
        break

d = json.load(open('results/latest_scan.json', 'r', encoding='utf-8'))
print(f"\nDone: {d['scan_time']}, matched={d['matched']}")

ongoing = [r for r in d['results'] if r['consolidation_end_date'] >= '2026-04-28']
print(f'Ongoing (today): {len(ongoing)}')

d['results'].sort(key=lambda x: x['pattern_score'], reverse=True)
print('\nTop 15:')
for r in d['results'][:15]:
    status = 'ACTIVE' if r['consolidation_end_date'] >= '2026-04-28' else f'ended={r["consolidation_end_date"]}'
    print(f"  {r['stock_code']} {r['stock_name']} "
          f"score={r['pattern_score']:.2f} "
          f"gain={r['uptrend_gain']:.1%} "
          f"retrace=?(not in file) "
          f"{status}")

# Check if 000421 is in results
codes = [r['stock_code'] for r in d['results']]
print(f'\n000421 in results: {("000421" in codes) or "000421" in [c.zfill(6) for c in codes]}')
