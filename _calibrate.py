"""Analyze 000421 vs current algorithm"""
import sys; sys.path.insert(0,'.')
from data.fetcher import DataFetcher
from pattern.recognizer import PatternRecognizer
from indicators.technical import TechnicalIndicators
from _config import FACTORY_PATTERN, SCAN
import pandas as pd, numpy as np

f = DataFetcher()
config = FACTORY_PATTERN

print("=== 000421 南京公用 ===")
df = f.daily_data('000421', days=500)
df = TechnicalIndicators.calculate_all(df.ffill().bfill())
n = len(df)

print(f'数据量: {n} 天')
print(f'日期范围: {df.iloc[0]["date"].date()} ~ {df.iloc[-1]["date"].date()}')
print()

# Show recent price action
print("最近 40 天日线:")
tail = df.tail(40)
for _, row in tail.iterrows():
    bull = '多头' if row['ma5'] > row['ma10'] > row['ma20'] else ''
    print(f"  {row['date'].date()} close={row['close']:.2f} ma5={row['ma5']:.0f} ma10={row['ma10']:.0f} ma20={row['ma20']:.0f} {bull}")

# Current algorithm result
r = PatternRecognizer(FACTORY_PATTERN)
p = r.find_pattern(df, max_days_back=SCAN.get('max_days_back'))
if p:
    print(f"\n当前算法匹配: score={p['pattern_score']:.2f} gain={p['uptrend_gain']:.1%}")
    print(f"  上涨: {p['uptrend_start_date']} -> {p['uptrend_end_date']}")
    print(f"  盘整: {p['uptrend_end_date']} -> {p['consolidation_end_date']}")
else:
    print("\n当前算法: 未匹配！")

# Manual scan: find ALL uptrend starts and see which are close to matching
print("\n=== 手动分析：所有可能的上涨段 ===")
consol_max = config['consolidation_days_max']
consol_min = config['consolidation_days_min']

matches = []
for i in range(n - consol_max - 1, 20, -1):
    if not TechnicalIndicators.is_bullish_arrangement(df, i):
        continue
    ok = True
    for j in range(i - 4, i + 1):
        if not TechnicalIndicators.is_bullish_arrangement(df, j):
            ok = False; break
    if not ok: continue
    
    start_price = df.loc[i, 'close']
    peak_idx = i; peak_price = start_price
    
    for k in range(i + 1, min(i + 80, n - consol_min)):
        if not TechnicalIndicators.is_bullish_arrangement(df, k):
            break
        cur = df.loc[k, 'close']
        if cur > peak_price: peak_price = cur; peak_idx = k
        cur_gain = (cur - start_price) / start_price
        if cur_gain >= config['uptrend_gain']:
            for jj in range(k + 1, min(k + 5, n)):
                if df.loc[jj, 'close'] < df.loc[jj, 'ma5']:
                    # Check consolidation
                    best_end = None; best_score = 0; best_info = {}
                    for c in range(peak_idx + consol_min, min(peak_idx + consol_max + 1, n)):
                        period = df.loc[peak_idx:c]
                        if 'bb_bandwidth' not in period.columns: continue
                        min_c = period['close'].min()
                        peak_p = df.loc[peak_idx, 'close']
                        retrace = (peak_p - min_c) / peak_p
                        avg_bw = period['bb_bandwidth'].mean()
                        vol = TechnicalIndicators.calculate_volatility(df, peak_idx, c)
                        avg_vr = period['volume_ratio'].mean()
                        
                        checks = {
                            'retrace': (retrace, config['max_retrace_pct']),
                            'volatility': (vol, config['volatility']),
                            'bandwidth': (avg_bw, config['bandwidth']),
                            'volume_ratio': (avg_vr, config['volume_ratio']),
                        }
                        passed = sum(1 for v, t in checks.values() if v < t)
                        if passed > best_score:
                            best_score = passed
                            best_end = c
                            best_info = {
                                'retrace': round(retrace*100,1),
                                'volatility': round(vol*100,1),
                                'bandwidth': round(avg_bw*100,1),
                                'volume_ratio': round(avg_vr*100,1),
                            }
                    
                    ut_gain = (peak_price - start_price) / start_price
                    print(f"\n上涨段 #{len(matches)+1}:")
                    print(f"  起点: idx={i} {df.loc[i,'date'].date()} price={start_price:.2f}")
                    print(f"  峰顶: idx={peak_idx} {df.loc[peak_idx,'date'].date()} price={peak_price:.2f} (+{ut_gain:.1%})")
                    print(f"  最佳盘整: end_idx={best_end} {df.loc[best_end,'date'].date() if best_end else 'N/A'}")
                    print(f"  检验: 回撤={best_info.get('retrace','?')}%/需≤{config['max_retrace_pct']*100:.0f}% 振幅={best_info.get('volatility','?')}%/需<{config['volatility']*100:.0f}% 带宽={best_info.get('bandwidth','?')}%/需<{config['bandwidth']*100:.0f}% 量比={best_info.get('volume_ratio','?')}%/需<{config['volume_ratio']*100:.0f}%")
                    
                    matches.append({
                        'start': i, 'peak': peak_idx, 'best_end': best_end,
                        'gain': ut_gain, **best_info,
                        'start_date': str(df.loc[i,'date'].date()),
                        'peak_date': str(df.loc[peak_idx,'date'].date()),
                        'end_date': str(df.loc[best_end,'date'].date()) if best_end else 'N/A',
                    })
                    break
    if len(matches) >= 5:
        break

# Also show ongoing
print("\n=== 进行中盘整 (直到今天) ===")
last_idx = n - 1
# Use the first uptrend found
for i in range(n - consol_max - 1, 20, -1):
    if not TechnicalIndicators.is_bullish_arrangement(df, i): continue
    ok = True
    for j in range(i - 4, i + 1):
        if not TechnicalIndicators.is_bullish_arrangement(df, j): ok = False; break
    if not ok: continue
    
    start_price = df.loc[i, 'close']
    peak_idx = i; peak_price = start_price
    for k in range(i + 1, min(i + 80, n - consol_min)):
        if not TechnicalIndicators.is_bullish_arrangement(df, k): break
        cur = df.loc[k, 'close']
        if cur > peak_price: peak_price = cur; peak_idx = k
        cur_gain = (cur - start_price) / start_price
        if cur_gain >= config['uptrend_gain']:
            for jj in range(k + 1, min(k + 5, n)):
                if df.loc[jj, 'close'] < df.loc[jj, 'ma5']:
                    ongoing_days = last_idx - peak_idx
                    if ongoing_days >= consol_min:
                        period = df.loc[peak_idx:last_idx]
                        min_c = period['close'].min()
                        peak_p = df.loc[peak_idx, 'close']
                        retrace = (peak_p - min_c) / peak_p
                        avg_bw = period['bb_bandwidth'].mean()
                        vol = TechnicalIndicators.calculate_volatility(df, peak_idx, last_idx)
                        avg_vr = period['volume_ratio'].mean()
                        print(f"  顶峰: {df.loc[peak_idx,'date'].date()} price={peak_p:.2f}")
                        print(f"  至今: {ongoing_days}天")
                        print(f"  回撤={retrace*100:.1f}% 振幅={vol*100:.1f}% 带宽={avg_bw*100:.1f}% 量比={avg_vr*100:.1f}%")
                        print(f"  阈值: 回撤≤{config['max_retrace_pct']*100:.0f}% 振幅<{config['volatility']*100:.0f}% 带宽<{config['bandwidth']*100:.0f}%")
            break
    break

f.close()
