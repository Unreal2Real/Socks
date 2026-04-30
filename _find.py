import requests

stocks = ['600036','601398','000001','002594','601857']
for code in stocks:
    r = requests.get(f'http://localhost:5555/api/stock/{code}?days=500', timeout=30)
    j = r.json()
    mark = 'HAS PATTERN' if j.get('pattern') else '-'
    print(f'  {code}: {mark}')
    if j.get('pattern'):
        p = j['pattern']
        print(f'    score={p["pattern_score"]:.2f}  uptrend={p["uptrend_start_date"]}->{p["uptrend_end_date"]}  consol={p["consolidation_start_date"]}->{p["consolidation_end_date"]}')
