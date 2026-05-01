import json
with open('results/latest_scan.json','r',encoding='utf-8') as f:
    d = json.load(f)
print('scan_time:', d['scan_time'])
print('matched:', d['matched'])
ongoing = [r for r in d['results'] if r['consolidation_end_date'] >= '2026-04-28']
print('ongoing:', len(ongoing))
d['results'].sort(key=lambda x: x['pattern_score'], reverse=True)
print()
for r in d['results'][:15]:
    print(f"  {r['stock_code']} {r['stock_name']} score={r['pattern_score']:.2f} gain={r['uptrend_gain']:.1%} up={r['uptrend_start_date']}->{r['uptrend_end_date']} end={r['consolidation_end_date']}")
