import sys; sys.path.insert(0,'.')
from data.fetcher import DataFetcher
from indicators.technical import TechnicalIndicators
from _config import FACTORY_PATTERN
import numpy as np

f = DataFetcher()
config = FACTORY_PATTERN
code = '601088'

df = f.daily_data(code, days=500)
df = TechnicalIndicators.calculate_all(df.ffill().bfill())

n = len(df)
consol_max = config['consolidation_days_max']
uptrend_thresh = config['uptrend_gain']

# Original forward scan
found = 0
for i in range(20, n - consol_max):
    if not TechnicalIndicators.is_bullish_arrangement(df, i):
        continue
    ok = True
    for j in range(i - 4, i + 1):
        if not TechnicalIndicators.is_bullish_arrangement(df, j):
            ok = False; break
    if not ok:
        continue
    
    found += 1
    if found > 3:
        break

    start_price = df.loc[i, 'close']
    peak_idx = i; peak_price = start_price
    ut_end = None
    
    for k in range(i + 1, n - config['consolidation_days_min']):
        is_bull = TechnicalIndicators.is_bullish_arrangement(df, k)
        cur = df.loc[k, 'close']
        if cur > peak_price: peak_price = cur; peak_idx = k
        cur_gain = (cur - start_price) / start_price
        
        if not is_bull:
            # Check if we already met gain + close < ma5 exit condition
            if cur_gain >= uptrend_thresh and ut_end is None:
                # check later days for ma5 break
                for jj in range(k, min(k + 20, n)):
                    if df.loc[jj, 'close'] < df.loc[jj, 'ma5']:
                        ut_end = peak_idx if peak_idx >= i else k
                        break
            break  # exit bull arrangement
        
        if cur_gain >= uptrend_thresh and ut_end is None:
            for jj in range(k + 1, min(k + 5, n)):
                if df.loc[jj, 'close'] < df.loc[jj, 'ma5']:
                    ut_end = peak_idx
                    break
    
    if ut_end is None:
        print(f'  forward i={i}: no uptrend_end (peak_gain={((peak_price-start_price)/start_price):.1%})')
        continue
    
    ut_gain = (peak_price - start_price) / start_price
    print(f'  forward i={i}: uptrend {df.loc[i,"date"].date()} -> {df.loc[ut_end,"date"].date()} gain={ut_gain:.1%}')
    
    for c in range(ut_end + 1, min(ut_end + consol_max + 1, n)):
        days = c - ut_end
        if days < config['consolidation_days_min']:
            continue
        period = df.loc[ut_end:c]
        if 'bb_bandwidth' not in period.columns:
            continue
        avg_bw = period['bb_bandwidth'].mean()
        if avg_bw >= config['bandwidth']:
            continue
        vol = TechnicalIndicators.calculate_volatility(df, ut_end, c)
        if vol >= config['volatility']:
            continue
        avg_vr = period['volume_ratio'].mean()
        if avg_vr >= config['volume_ratio']:
            continue
        print(f'    MATCH! consol={days}d bw={avg_bw:.3f} vol={vol:.3f} vr={avg_vr:.3f}')
        break
    else:
        print(f'    no valid consolidation')

# Show the tail of data to understand recent price action
print(f'\nLast 30 days:')
tail = df.tail(30)[['date','close','ma5','ma10','ma20']]
for _, row in tail.iterrows():
    bull = 'BULL' if row['ma5'] > row['ma10'] > row['ma20'] else ''
    print(f"  {row['date'].date()} close={row['close']:.2f} ma5={row['ma5']:.0f} ma10={row['ma10']:.0f} ma20={row['ma20']:.0f} {bull}")

f.close()
