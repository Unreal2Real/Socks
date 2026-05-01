import requests
r = requests.get('http://localhost:5555/')
t = r.text
print('btnConfirm:', 'btnConfirm' in t)
print('labelBad with confirm:', 'confirm' in t)
print('完全不符 tag:', '完全不符' in t)
print('ALL OK:', all(['btnConfirm' in t, 'confirm' in t, '完全不符' in t]))
