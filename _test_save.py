import requests, time

r = requests.post('http://localhost:5555/api/scan/start', json={'limit':500}, timeout=10)
print('scan started:', r.json()['task_id'])

while True:
    time.sleep(3)
    pr = requests.get('http://localhost:5555/api/scan/progress', timeout=5)
    p = pr.json()['data']
    print(f"  {p['progress']}/{p['total']} ({p['percent']}%) matched={p['matched']}")
    if not p['running']:
        break

# Test results saved to disk
import os
if os.path.exists('results/latest_scan.json'):
    import json
    data = json.load(open('results/latest_scan.json','r',encoding='utf-8'))
    print(f"\nSaved: {data['scan_time']}, matched={data['matched']}, files={len(os.listdir('results'))}")

# Test last_scan API
r = requests.get('http://localhost:5555/api/scan/last', timeout=10)
j = r.json()['data']
print(f"last_scan: {j.get('last_scan','')}")
active = [x for x in j.get('data',[]) if x.get('status')!='exited']
exited = [x for x in j.get('data',[]) if x.get('status')=='exited']
print(f"active: {len(active)}, exited: {len(exited)}")
for x in active[:5]:
    print(f"  {x['stock_code']} {x['stock_name']} score={x['pattern_score']:.2f} status={x.get('status','?')}")
