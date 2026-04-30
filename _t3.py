import requests
codes = ['601088','600028','601857','600036','600690','600519','601398','600050']
for c in codes:
    r = requests.get(f'http://localhost:5555/api/stock/{c}?days=500', timeout=30)
    j = r.json()
    p = j.get('pattern')
    if p:
        print(f'{c}: MATCH score={p["pattern_score"]:.2f} gain={p["uptrend_gain"]:.1%} days={p["consolidation_days"]}')
        print(f'  uptrend={p["uptrend_start_date"]}->{p["uptrend_end_date"]}  consol={p["consolidation_start_date"]}->{p["consolidation_end_date"]}')
    else:
        print(f'{c}: -')
