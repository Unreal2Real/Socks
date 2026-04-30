import sys; sys.path.insert(0,'.')
from data.fetcher import DataFetcher
from _config import FACTORY_PATTERN
from indicators.technical import TechnicalIndicators
import numpy as np

f = DataFetcher()
config = FACTORY_PATTERN
code = '601088'

df = f.daily_data(code, days=500)
df = TechnicalIndicators.calculate_all(df.ffill().bfill())

n = len(df)
consol_max = config['consolidation_days_max']
uptrend_thresh = config['uptrend_gain']

# Test from back to front (as our recognizer does)
start = n - consol_max - 1
found_uptrend_starts = 0
found_uptrend_ends = 0
found_consol = 0

for i in range(start, 20, -1):
    # Check uptrend start
    if not TechnicalIndicators.is_bullish_arrangement(df, i):
        continue
    ok = True
    for j in range(i - 4, i + 1):
        if not TechnicalIndicators.is_bullish_arrangement(df, j):
            ok = False
            break
    if not ok:
        continue
    
    found_uptrend_starts += 1
    if found_uptrend_starts > 10:
        break
    
    # Scan uptrend
    start_price = df.loc[i, 'close']
    peak_idx = i
    peak_price = start_price
    ut_end = None
    ut_gain = 0
    
    for k in range(i + 1, n - config['consolidation_days_min']):
        if not TechnicalIndicators.is_bullish_arrangement(df, k):
            break
        cur = df.loc[k, 'close']
        if cur > peak_price:
            peak_price = cur
            peak_idx = k
        cur_gain = (cur - start_price) / start_price
        if cur_gain >= uptrend_thresh:
            for jj in range(k + 1, min(k + 5, n)):
                if df.loc[jj, 'close'] < df.loc[jj, 'ma5']:
                    ut_end = peak_idx
                    ut_gain = (peak_price - start_price) / start_price
                    break
            if ut_end is not None:
                break
        elif cur_gain < -0.05:
            # lost momentum
            break
    
    if ut_end is None:
        continue
    
    found_uptrend_ends += 1
    if found_uptrend_ends > 5:
        break
    
    # Scan consolidation
    for c in range(ut_end + 1, min(ut_end + consol_max + 1, n)):
        days = c - ut_end
        if days < config['consolidation_days_min']:
            continue
        
        period = df.loc[ut_end:c]
        
        if 'bb_bandwidth' not in period.columns:
            break
        
        avg_bw = period['bb_bandwidth'].mean()
        if avg_bw >= config['bandwidth']:
            continue
        
        vol = TechnicalIndicators.calculate_volatility(df, ut_end, c)
        if vol >= config['volatility']:
            continue
        
        avg_vr = period['volume_ratio'].mean()
        if avg_vr >= config['volume_ratio']:
            continue
        
        found_consol += 1
        print(f'  MATCH at i={i} ut_end={ut_end} consol_end={c}')
        print(f'    uptrend: {df.loc[i,"date"].date()} -> {df.loc[ut_end,"date"].date()} gain={ut_gain:.1%}')
        print(f'    consol: {df.loc[ut_end,"date"].date()} -> {df.loc[c,"date"].date()} days={days}')
        print(f'    bw={avg_bw:.3f} vol={vol:.3f} vr={avg_vr:.3f}')
        break

print(f'\nuptrend_starts={found_uptrend_starts} uptrend_ends={found_uptrend_ends} matches={found_consol}')

# Quick check: near misses
print(f'\nNear miss analysis on first uptrend found by bull arrangement:')
for i in range(start, n - 60, -1):
    if not TechnicalIndicators.is_bullish_arrangement(df, i):
        continue
    ok = True
    for j in range(i - 4, i + 1):
        if not TechnicalIndicators.is_bullish_arrangement(df, j):
            ok = False
            break
    if not ok:
        continue
    
    start_price = df.loc[i, 'close']
    peak = i; peak_p = start_price
    max_gain = 0
    for k in range(i + 1, min(i + 50, n)):
        if not TechnicalIndicators.is_bullish_arrangement(df, k):
            break
        cur = df.loc[k, 'close']
        if cur > peak_p: peak_p = cur; peak = k
        g = (cur - start_price) / start_price
        if g > max_gain: max_gain = g
    
    # Check consolidation
    c_start = peak
    for c in range(c_start + config['consolidation_days_min'], min(c_start + consol_max + 1, n)):
        period = df.loc[c_start:c]
        if 'bb_bandwidth' not in period.columns:
            continue
        avg_bw = period['bb_bandwidth'].mean()
        vol = TechnicalIndicators.calculate_volatility(df, c_start, c)
        avg_vr = period['volume_ratio'].mean()
        if avg_bw < config['bandwidth'] and vol < config['volatility'] and avg_vr < config['volume_ratio']:
            print(f'  NEEDED: gain>={uptrend_thresh} got={max_gain:.1%} at i={i} peak_at={peak}')
            print(f'    consol possible: {df.loc[c_start,"date"].date()} -> {df.loc[c,"date"].date()} bw={avg_bw:.3f} vol={vol:.3f} vr={avg_vr:.3f}')
            break
    
    if max_gain < uptrend_thresh:
        print(f'  FAIL gain: max={max_gain:.1%} < {uptrend_thresh:.0%} at i={i}')
    break

f.close()
