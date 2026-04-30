import json
from datetime import datetime, timedelta

with open('results/latest_scan.json','r',encoding='utf-8') as f:
    data = json.load(f)
results = data['results']
print(f'扫描时间: {data["scan_time"]}')
print(f'匹配数量: {len(results)}')
print()

# 按盘整结束日期排序
results.sort(key=lambda x: x.get('consolidation_end_date',''))
for r in results[:15]:
    print(f'  {r["stock_code"]} {r["stock_name"]} consol_end={r["consolidation_end_date"]} score={r["pattern_score"]}')
print('  ...')
print()

# 统计最近30天
today = datetime.now().date()
cut30 = (today - timedelta(days=30)).isoformat()
cut60 = (today - timedelta(days=60)).isoformat()
cut90 = (today - timedelta(days=90)).isoformat()

recent30 = [r for r in results if r['consolidation_end_date'] >= cut30]
recent60 = [r for r in results if r['consolidation_end_date'] >= cut60]
recent90 = [r for r in results if r['consolidation_end_date'] >= cut90]

print(f'盘整结束在最近30天内的({cut30}~): {len(recent30)}')
for r in recent30:
    print(f'  {r["stock_code"]} {r["stock_name"]} end={r["consolidation_end_date"]}')

print(f'\n盘整结束在最近60天内的({cut60}~): {len(recent60)}')
for r in recent60:
    print(f'  {r["stock_code"]} {r["stock_name"]} end={r["consolidation_end_date"]}')

print(f'\n盘整结束在最近90天内的({cut90}~): {len(recent90)}')

# 最早的盘整结束日期
earliest = min(results, key=lambda x: x['consolidation_end_date'])
latest = max(results, key=lambda x: x['consolidation_end_date'])
print(f'\n最早结束: {earliest["stock_code"]} {earliest["consolidation_end_date"]}')
print(f'最晚结束: {latest["stock_code"]} {latest["consolidation_end_date"]}')
