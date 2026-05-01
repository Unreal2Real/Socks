"""Find ALL candidates for each stock, pick best"""
import sys; sys.path.insert(0,'.')
import pandas as pd, numpy as np
from data.fetcher import DataFetcher
from indicators.technical import TechnicalIndicators
from _config import FACTORY_PATTERN, SCAN

f = DataFetcher()
config = FACTORY_PATTERN

expected = {
    '603629': ('2026-01-21', '2026-02-12', '2026-04-07'),
    '002008': ('2026-02-12', '2026-03-02', '2026-04-07'),
    '300136': ('2025-12-24', '2026-01-22', '2026-04-13'),
    '002796': ('2025-12-16', '2026-01-28', '2026-02-12'),
    '003036': ('2025-06-16', '2025-08-06', '2026-03-17'),
    '002149': ('2025-12-01', '2026-01-12', '2026-04-14'),
    '002655': ('2026-02-10', '2026-03-02', '2026-04-02'),
    '002980': ('2026-02-25', '2026-03-11', '2026-03-27'),
}

for code, (exp_us, exp_ue, exp_ce) in expected.items():
    print(f'=== {code} ===')
    df = f.daily_data(code, days=1000 if code == '003036' else 500)
    if df.empty:
        print('  NO DATA')
        continue
    
    df = TechnicalIndicators.calculate_all(df.ffill().bfill())
    n = len(df)
    exp_us_ts = pd.Timestamp(exp_us)
    exp_ce_ts = pd.Timestamp(exp_ce)
    
    consol_min = config['consolidation_days_min']
    gain_thresh = config['uptrend_gain']
    min_elev = config['min_elevation']
    min_up_days = config.get('uptrend_min_days', 5)
    
    # Find ALL uptrend starts (scan backward)
    candidates = []
    for i in range(n - consol_min - 1, 20, -1):
        # Check if this day is a valid uptrend start (at least 2/5 bullish)
        bull_count = sum(1 for j in range(i-4, i+1) if TechnicalIndicators.is_bullish_arrangement(df, j))
        if bull_count < 2:
            continue
        
        # Scan uptrend from here
        start_price = df.loc[i, 'close']
        peak_idx = i
        peak_price = start_price
        below_ma5_streak = 0
        
        for k in range(i + 1, n - consol_min):
            cur = df.loc[k, 'close']
            if cur > peak_price:
                peak_price = cur
                peak_idx = k
            
            if df.loc[k, 'close'] < df.loc[k, 'ma5']:
                below_ma5_streak += 1
                if below_ma5_streak >= 2 and peak_price > start_price:
                    gain = (peak_price - start_price) / start_price
                    up_days = peak_idx - i + 1
                    if gain >= gain_thresh and up_days >= min_up_days:
                        # Check ongoing consolidation
                        last_idx = n - 1
                        og_days = last_idx - peak_idx
                        if og_days >= consol_min:
                            consol_df = df.loc[peak_idx:last_idx]
                            min_c = consol_df['close'].min()
                            elev = (min_c - start_price) / start_price
                            if elev >= min_elev:
                                score = og_days * max(elev, 0.01)
                                candidates.append({
                                    'start_i': i, 'peak_i': peak_idx, 'end_i': last_idx,
                                    'start_date': str(df.loc[i, 'date'].date()),
                                    'peak_date': str(df.loc[peak_idx, 'date'].date()),
                                    'end_date': str(df.loc[last_idx, 'date'].date()),
                                    'gain': gain, 'consol_days': og_days, 'elev': elev,
                                    'score': score, 'ongoing': True,
                                })
                        # Check completed consolidation
                        for c in range(peak_idx + consol_min, min(peak_idx + 180, n)):
                            consol_df = df.loc[peak_idx:c]
                            min_c = consol_df['close'].min()
                            elev = (min_c - start_price) / start_price
                            if elev >= min_elev:
                                consol_days = c - peak_idx
                                score = consol_days * max(elev, 0.01)
                                candidates.append({
                                    'start_i': i, 'peak_i': peak_idx, 'end_i': c,
                                    'start_date': str(df.loc[i, 'date'].date()),
                                    'peak_date': str(df.loc[peak_idx, 'date'].date()),
                                    'end_date': str(df.loc[c, 'date'].date()),
                                    'gain': gain, 'consol_days': consol_days, 'elev': elev,
                                    'score': score, 'ongoing': False,
                                })
                                break
                    break
            else:
                below_ma5_streak = 0
    
    if not candidates:
        print(f'  ZERO CANDIDATES')
        continue
    
    candidates.sort(key=lambda x: x['score'], reverse=True)
    
    print(f'  Found {len(candidates)} candidates')
    print(f'  Top 3 by score (consol_days × elev):')
    for c in candidates[:3]:
        match = '✅ MATCH' if abs((pd.Timestamp(c['start_date']) - exp_us_ts).days) <= 5 else ''
        print(f'    start={c["start_date"]} peak={c["peak_date"]} end={c["end_date"]} '
              f'consol={c["consol_days"]}d gain={c["gain"]:.1%} elev={c["elev"]:.1%} '
              f'score={c["score"]:.2f} {match}')
    
    # Does the best candidate match user expectation?
    best = candidates[0]
    print(f'  Best vs expected: start={best["start_date"]} (expected {exp_us})')
    print(f'                     end={best["end_date"]} (expected {exp_ce})')
    print()

f.close()
