import requests, re
r = requests.get('http://localhost:5555/')
t = r.text
s1 = t.find('<script>')
s2 = t.find('</script>', s1)
js = t[s1:s2]

# Check for startScan
print('startScan defined:', 'function startScan' in js)
print('labelBad defined:', 'function labelBad' in js)
print('choiceDialog:', 'choiceDialog' in t)
print('closeChoiceDialog:', 'closeChoiceDialog' in js)
print('startCorrectMode:', 'startCorrectMode' in js)

# Check all function declarations (quick)
funcs = re.findall(r'function\s+(\w+)', js)
print('Core functions:', [f for f in funcs if f in ['startScan','stopScan','analyzeStock','viewStock','labelGood','labelBad','closeChoiceDialog','startCorrectMode']])
