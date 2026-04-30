"""Diagnose: layer by layer what's rejecting stocks"""
import sys; sys.path.insert(0,'.')
from data.fetcher import DataFetcher
from indicators.technical import TechnicalIndicators
from _config import FACTORY_PATTERN, SCAN
from datetime import datetime, timedelta, date

f = DataFetcher()
config = FACTORY_PATTERN
stocks = f.stock_list()[:300]

stats = {
    'total': 0,
    'enough_data': 0,
    'uptrend_start': 0,
    'uptrend_peak': 0,
    'gain_met': 0,
    'consol_min_days': 0,
    'pass_retrace': 0,
    'pass_volatility': 0,
    'pass_bandwidth': 0,
    'pass_volume_ratio': 0,
    'pass_all_consol': 0,
    'recent_enough': 0,
    'final': 0,
}
all_matches = []

today = date.today()

for code, name in stocks:
    stats['total'] += 1
    
    df = f.daily_data(code, days=500)
    if df.empty or len(df) < 60:
        continue
    stats['enough_data'] += 1
    
    df = TechnicalIndicators.calculate_all(df.ffill().bfill())
    n = len(df)
    consol_max = config['consolidation_days_max']
    consol_min = config['consolidation_days_min']
    ut_thresh = config['uptrend_gain']
    
    # Scan from back
    found_any = False
    for i in range(n - consol_max - 1, 20, -1):
        if not TechnicalIndicators.is_bullish_arrangement(df, i):
            continue
        ok = True
        for j in range(i - 4, i + 1):
            if not TechnicalIndicators.is_bullish_arrangement(df, j):
                ok = False; break
        if not ok: continue
        
        if not found_any:
            stats['uptrend_start'] += 1
            found_any = True
        
        start_price = df.loc[i, 'close']
        peak_idx = i; peak_price = start_price
        ut_end = None
        
        for k in range(i + 1, n - consol_min):
            if not TechnicalIndicators.is_bullish_arrangement(df, k):
                break
            cur = df.loc[k, 'close']
            if cur > peak_price: peak_price = cur; peak_idx = k
            cur_gain = (cur - start_price) / start_price
            if cur_gain >= ut_thresh:
                for jj in range(k + 1, min(k + 5, n)):
                    if df.loc[jj, 'close'] < df.loc[jj, 'ma5']:
                        ut_end = peak_idx
                        break
                if ut_end is not None: break
        
        if ut_end is None: continue
        
        if not all_matches or all_matches[-1]['code'] != code:
            stats['uptrend_peak'] += 1
        
        # Check consolidation
        for c in range(ut_end + 1, min(ut_end + consol_max + 1, n)):
            days = c - ut_end
            if days < consol_min: continue
            
            period = df.loc[ut_end:c]
            if 'bb_bandwidth' not in period.columns: continue
            
            peak_p = df.loc[ut_end, 'close']
            min_c = period['close'].min()
            retrace = (peak_p - min_c) / peak_p
            
            avg_bw = period['bb_bandwidth'].mean()
            vol = TechnicalIndicators.calculate_volatility(df, ut_end, c)
            avg_vr = period['volume_ratio'].mean()
            
            if retrace <= config.get('max_retrace_pct', 0.12):
                stats['pass_retrace'] += 1
            if vol < config['volatility']:
                stats['pass_volatility'] += 1
            if avg_bw < config['bandwidth']:
                stats['pass_bandwidth'] += 1
            if avg_vr < config['volume_ratio']:
                stats['pass_volume_ratio'] += 1
                
            if retrace <= config.get('max_retrace_pct', 0.12) and \
               vol < config['volatility'] and \
               avg_bw < config['bandwidth'] and \
               avg_vr < config['volume_ratio']:
                stats['pass_all_consol'] += 1
                end_date = df.loc[c, 'date'].date()
                age = (today - end_date).days
                if age <= SCAN.get('max_pattern_age_days', 30):
                    stats['recent_enough'] += 1
                    stats['final'] += 1
                    all_matches.append({
                        'code': code, 'name': name,
                        'end': str(end_date), 'age': age,
                        'retrace': round(retrace*100,1),
                        'vol': round(vol,3),
                        'bw': round(avg_bw,3),
                        'vr': round(avg_vr,3),
                    })
                break  # Found valid consolidation, move to next stock
            break  # First candidate failed, move on
        break  # Found first uptrend, done with this stock

print('=== 逐层过滤统计 (300只) ===')
for k, v in stats.items():
    print(f'  {k}: {v}')

print(f'\n=== 通过全部条件 (30天内): {stats["final"]} ===')
for m in all_matches[:10]:
    print(f"  {m['code']} {m['name']} end={m['end']} age={m['age']}d retrace={m['retrace']}%")

# Show what happens without age filter
print(f'\n=== 去掉30天限制: {stats["pass_all_consol"]} ===')

# Show WHY stocks fail consolidation - the first failed step
print(f'\n=== 盘整失败分析 ===')
print(f'  通过所有: {stats["pass_all_consol"]}')
print(f'  失败在回撤: {stats["uptrend_peak"] - stats["pass_retrace"]} (retrace > 12%)')
print(f'  失败在波动: {stats["uptrend_peak"] - stats["pass_volatility"]} (vol > 12%)')
print(f'  失败在带宽: {stats["uptrend_peak"] - stats["pass_bandwidth"]} (bw > 30%)')
print(f'  失败在量比: {stats["uptrend_peak"] - stats["pass_volume_ratio"]} (vr > 80%)')
print(f'  上涨段未达标: {stats["uptrend_start"] - stats["uptrend_peak"]}')

f.close()
