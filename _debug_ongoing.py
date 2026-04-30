"""Debug: why isn't ongoing consolidation triggering?"""
import sys; sys.path.insert(0,'.')
import pandas as pd
from data.fetcher import DataFetcher
from indicators.technical import TechnicalIndicators
from _config import FACTORY_PATTERN

f = DataFetcher()
config = FACTORY_PATTERN

# Test on a stock that has a known pattern
for code in ['600395','600348','600575','600109','601088']:
    df = f.daily_data(code, days=500)
    if df.empty: continue
    df = TechnicalIndicators.calculate_all(df.ffill().bfill())
    n = len(df)
    last_idx = n - 1
    last_date = df.loc[last_idx, 'date'].date()
    
    consol_max = config['consolidation_days_max']
    consol_min = config['consolidation_days_min']
    
    print(f'\n=== {code} (data up to {last_date}) ===')
    
    # Backward scan
    found_any = False
    for i in range(n - consol_max - 1, 20, -1):
        if not TechnicalIndicators.is_bullish_arrangement(df, i):
            continue
        ok = True
        for j in range(i - 4, i + 1):
            if not TechnicalIndicators.is_bullish_arrangement(df, j):
                ok = False; break
        if not ok: continue
        
        if found_any: continue
        found_any = True
        
        start_price = df.loc[i, 'close']
        peak_idx = i; peak_price = start_price
        
        for k in range(i + 1, n - consol_min):
            if not TechnicalIndicators.is_bullish_arrangement(df, k):
                break
            cur = df.loc[k, 'close']
            if cur > peak_price: peak_price = cur; peak_idx = k
            cur_gain = (cur - start_price) / start_price
            if cur_gain >= config['uptrend_gain']:
                for jj in range(k + 1, min(k + 5, n)):
                    if df.loc[jj, 'close'] < df.loc[jj, 'ma5']:
                        peak_idx = peak_idx
                        break
        
        # Try ongoing consolidation first
        ongoing_days = last_idx - peak_idx
        if ongoing_days >= consol_min:
            period = df.loc[peak_idx:last_idx]
            peak_p = df.loc[peak_idx, 'close']
            min_c = period['close'].min()
            retrace = (peak_p - min_c) / peak_p
            avg_bw = period['bb_bandwidth'].mean() if 'bb_bandwidth' in period.columns else 999
            vol = TechnicalIndicators.calculate_volatility(df, peak_idx, last_idx)
            avg_vr = period['volume_ratio'].mean() if 'volume_ratio' in period.columns else 999
            
            passed = retrace <= config['max_retrace_pct'] and \
                     vol < config['volatility'] and \
                     avg_bw < config['bandwidth'] and \
                     avg_vr < config['volume_ratio']
            
            print(f'  Ongoing ({ongoing_days}d): retrace={retrace:.1%} vol={vol:.1%} bw={avg_bw:.1%} vr={avg_vr:.1%} → {"PASS" if passed else "FAIL"}')
            if not passed:
                reasons = []
                if retrace > config['max_retrace_pct']: reasons.append(f'retrace {retrace:.1%}>{config["max_retrace_pct"]:.0%}')
                if vol >= config['volatility']: reasons.append(f'vol {vol:.1%}>={config["volatility"]:.0%}')
                if avg_bw >= config['bandwidth']: reasons.append(f'bw {avg_bw:.1%}>={config["bandwidth"]:.0%}')
                if avg_vr >= config['volume_ratio']: reasons.append(f'vr {avg_vr:.1%}>={config["volume_ratio"]:.0%}')
                print(f'    Failed: {", ".join(reasons)}')
        
        # Try completed consolidation
        for c in range(peak_idx + consol_min, min(peak_idx + consol_max + 1, n)):
            period = df.loc[peak_idx:c]
            if 'bb_bandwidth' not in period.columns: continue
            peak_p2 = df.loc[peak_idx, 'close']
            min_c2 = period['close'].min()
            retrace2 = (peak_p2 - min_c2) / peak_p2
            avg_bw2 = period['bb_bandwidth'].mean()
            vol2 = TechnicalIndicators.calculate_volatility(df, peak_idx, c)
            avg_vr2 = period['volume_ratio'].mean()
            
            if retrace2 <= config['max_retrace_pct'] and \
               vol2 < config['volatility'] and \
               avg_bw2 < config['bandwidth'] and \
               avg_vr2 < config['volume_ratio']:
                print(f'  Completed ({c-peak_idx}d): retrace={retrace2:.1%} vol={vol2:.1%} bw={avg_bw2:.1%} vr={avg_vr2:.1%} end={df.loc[c,"date"].date()}')

f.close()
