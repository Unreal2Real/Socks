import requests, time

r = requests.post('http://localhost:5555/api/scan/start', json={'limit': 500}, timeout=10)
print('scan started:', r.json()['task_id'])

while True:
    time.sleep(3)
    pr = requests.get('http://localhost:5555/api/scan/progress', timeout=5)
    p = pr.json()['data']
    if p['total'] > 0:
        print(f"  {p['progress']}/{p['total']} ({p['percent']}%) matched={p['matched']}")
    if not p['running']:
        break

import json, os
if os.path.exists('results/latest_scan.json'):
    data = json.load(open('results/latest_scan.json','r',encoding='utf-8'))
    results = data['results']
    print(f"\nSaved: {data['scan_time']}, matched={data['matched']}")
    from datetime import datetime, timedelta
    today = datetime.now().date()
    for r in results:
        end = r['consolidation_end_date']
        days_ago = (today - datetime.strptime(end, '%Y-%m-%d').date()).days
        print(f"  {r['stock_code']} {r['stock_name']} score={r['pattern_score']:.2f} end={end} ({days_ago}天前)")
else:
    print("\nNo results file (all filtered out - no recent patterns)")
