import sys; sys.path.insert(0,'.')
from data.fetcher import DataFetcher
from indicators.technical import TechnicalIndicators
import pandas as pd

f = DataFetcher()
df = f.daily_data('603629', days=500)
df = TechnicalIndicators.calculate_all(df.ffill().bfill())
n = len(df)

exp_peak = pd.Timestamp('2026-02-12')

print('603629: peaks near user expected (2026-02-12 ±10d):')
for i in range(n):
    d = df.loc[i, 'date'].date()
    if abs((pd.Timestamp(str(d)) - exp_peak).days) <= 10:
        cur = float(df.loc[i, 'close'])
        left_max = float(df.loc[max(i-5,0):i-1, 'close'].max()) if i >= 5 else 0
        right_max = float(df.loc[i+1:min(i+5,n-1), 'close'].max()) if i < n-5 else 0
        is_peak = cur > left_max and cur > right_max
        mark = 'PEAK' if is_peak else ''
        print(f'  {d} idx={i} close={cur:.1f} left={left_max:.1f} right={right_max:.1f} {mark}')

# Try bigger window
print('\nPeaks with window=10:')
for i in range(10, n-10):
    d = df.loc[i, 'date'].date()
    if abs((pd.Timestamp(str(d)) - exp_peak).days) <= 10:
        cur = float(df.loc[i, 'close'])
        left_max = float(df.loc[max(i-10,0):i-1, 'close'].max())
        right_max = float(df.loc[i+1:min(i+10,n-1), 'close'].max())
        is_peak = cur > left_max and cur > right_max
        if is_peak:
            print(f'  PEAK: {d} idx={i} close={cur:.1f}')

f.close()
