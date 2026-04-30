import requests, time
r = requests.post('http://localhost:5555/api/scan/start', json={'limit': 1200}, timeout=10)
print('scan:', r.json()['task_id'])
while True:
    time.sleep(5)
    pr = requests.get('http://localhost:5555/api/scan/progress', timeout=5)
    p = pr.json()['data']
    if p['total'] > 0: print(f"  {p['progress']}/{p['total']} ({p['percent']:.0f}%) matched={p['matched']}")
    if not p['running']: break

import json
d = json.load(open('results/latest_scan.json','r',encoding='utf-8'))
print(f"\nDone: {d['scan_time']}, matched={d['matched']}")
for r in d['results'][:8]:
    print(f"  {r['stock_code']} {r['stock_name']} score={r['pattern_score']:.2f} end={r['consolidation_end_date']}")
