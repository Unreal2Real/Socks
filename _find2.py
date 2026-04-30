import requests, time

r = requests.post('http://localhost:5555/api/scan/start', json={'limit': 500}, timeout=10)
print(f'scan started: {r.json()}')

while True:
    time.sleep(3)
    pr = requests.get('http://localhost:5555/api/scan/progress', timeout=5)
    p = pr.json()['data']
    print(f'  {p["progress"]}/{p["total"]} ({p["percent"]}%) matched={p["matched"]} current={p["current"]}')
    if not p['running']:
        break

rr = requests.get('http://localhost:5555/api/scan/results', timeout=10)
results = rr.json()['data']
print(f'\nFound {len(results)} matches:')
for p in results[:3]:
    print(f'  {p["stock_code"]} {p["stock_name"]} score={p["pattern_score"]:.2f}')
    print(f'    uptrend: {p["uptrend_start_date"]} -> {p["uptrend_end_date"]}')
    print(f'    consol:  {p["consolidation_start_date"]} -> {p["consolidation_end_date"]}')
