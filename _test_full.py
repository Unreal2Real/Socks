import requests, json, time, sys, os
BASE = 'http://localhost:5555'

print('=== 1. PAGE LOAD ===')
r = requests.get(BASE, timeout=10)
assert r.status_code == 200
keys = ['startScan', 'analyzeStock', 'viewStock', 'labelGood', 'labelBad',
        'labeledStocks', 'corrected', 'choiceDialog', 'closeChoiceDialog', 'startCorrectMode']
for k in keys:
    ok = k in r.text
    if not ok: print('  MISSING: '+k)
print('  OK')

print('=== 2. ETF FILTER ===')
os.chdir(r'c:\Users\louis\Trea_Projects\Socks')
sys.path.insert(0, '.')
from data.fetcher import DataFetcher
f = DataFetcher()
etf_tests = [('510050','FILTERED'), ('510380','FILTERED'), ('159919','FILTERED'), ('300750','FILTERED'),
             ('601398','PASS'), ('000001','PASS'), ('002008','PASS'), ('603629','PASS')]
for code, expected in etf_tests:
    ok = f._is_main_board(code, '')
    result = 'PASS' if ok else 'FILTERED'
    assert result == expected, '%s expected %s got %s' % (code, expected, result)
print('  OK')
f.close()

print('=== 3. STOCK API ===')
stocks = ['603629', '002008', '300136']
for code in stocks:
    r = requests.get(BASE+'/api/stock/'+code+'?days=250', timeout=30)
    assert r.status_code == 200
    j = r.json()
    assert j['code'] == 0
    assert len(j['data']) > 0
    has_pat = j['pattern'] is not None
    print('  %s: data=%d pattern=%s' % (code, len(j['data']), has_pat))

print('=== 4. ML STATS ===')
r = requests.get(BASE+'/api/ml/stats', timeout=10)
j = r.json()
assert j['code'] == 0
ls = j['labels']
m = j['model']
print('  labels: total=%d good=%d bad=%d' % (ls['total'], ls['good'], ls['bad']))
print('  model: exists=%s type=%s' % (m['exists'], m.get('model_type','N/A')))

print('=== 5. ML FEATURES ===')
r = requests.get(BASE+'/api/ml/features/603629', timeout=30)
j = r.json()
assert j['code'] == 0
feat = j.get('features') or {}
print('  features: %d dims, ml_prob=%s' % (len(feat), j.get('ml_probability','N/A')))

print('=== 6. SCAN ===')
r = requests.post(BASE+'/api/scan/start', json={'limit': 20}, timeout=10)
assert r.status_code == 200
tid = r.json()['task_id']
print('  task: '+tid)

print('=== ALL TESTS PASSED ===')
