import requests, time
r = requests.post('http://localhost:5555/api/scan/start', json={'limit': 50})
tid = r.json()['task_id']
print('Scan started:', tid)
for i in range(40):
    time.sleep(1.5)
    pr = requests.get('http://localhost:5555/api/scan/progress').json()['data']
    rr = requests.get('http://localhost:5555/api/scan/results').json()
    n = len(rr['data'])
    print(f'  progress={pr["progress"]}/{pr["total"]} matched_api={n} running={pr["running"]}')
    if not pr['running']: break
print('DONE')
