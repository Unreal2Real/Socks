"""Diagnose all 8 reference stocks against current algorithm"""
import sys; sys.path.insert(0,'.')
from data.fetcher import DataFetcher
from pattern.recognizer import PatternRecognizer
from indicators.technical import TechnicalIndicators
from _config import FACTORY_PATTERN, SCAN
import pandas as pd, numpy as np

f = DataFetcher()
config = dict(FACTORY_PATTERN)
r = PatternRecognizer(config)

# User's reference stocks with expected time ranges
references = [
    ('603629', '2026-01-21', '2026-02-12', '2026-04-07'),   # uptrend: 1/21->2/12, consol: 2/12->4/7
    ('002008', '2026-02-12', '2026-03-02', '2026-04-07'),   # uptrend: 2/12->3/2, consol: 3/2->4/7
    ('300136', '2025-12-24', '2026-01-22', '2026-04-13'),   # uptrend: 12/24->1/22, consol: 1/22->4/13
    ('002796', '2025-12-16', '2026-01-28', '2026-02-12'),   # uptrend: 12/16->1/28, consol: 1/28->2/12
    ('003036', '2025-06-16', '2025-08-06', '2026-03-17'),   # uptrend: 6/16->8/6, consol: 8/6->3/17
    ('002149', '2025-12-01', '2026-01-12', '2026-04-14'),   # uptrend: 12/1->1/12, consol: 1/12->4/14
    ('002655', '2026-02-10', '2026-03-02', '2026-04-02'),   # uptrend: 2/10->3/2, consol: 3/2->4/2
    ('002980', '2026-02-25', '2026-03-11', '2026-03-27'),   # uptrend: 2/25->3/11, consol: 3/11->3/27
]

print('=== 8只参考股票诊断 ===')
print(f'当前配置: gain>={config["uptrend_gain"]:.0%}  consol_max={config["consolidation_days_max"]}d  consol_min={config["consolidation_days_min"]}d')
print(f'回撤≤{config["max_retrace_pct"]:.0%}  振幅<{config["volatility"]:.0%}  带宽<{config["bandwidth"]:.0%}')
print()

issues_found = {}
for code, ut_start_date, ut_end_date, consol_end_date in references:
    print(f'--- {code} ---')
    df = f.daily_data(code, days=1000 if code in ['003036', '300136'] else 500)
    if df.empty:
        print(f'  NO DATA')
        issues_found[code] = 'NO_DATA'
        continue
    
    df = TechnicalIndicators.calculate_all(df.ffill().bfill())
    n = len(df)
    
    # 1. Check if in stock list
    all_codes = [c for c, _ in f.stock_list()]
    in_list = code in all_codes or code.zfill(6) in all_codes
    if not in_list:
        print(f'  不在当前股票列表！被 _is_main_board 过滤掉')
        issues_found[code] = 'FILTERED_OUT'
        continue
    
    # 2. Check current algorithm
    p = r.find_pattern(df, max_days_back=SCAN.get('max_days_back'))
    if p:
        gap_start = (pd.Timestamp(ut_start_date) - pd.Timestamp(p['uptrend_start_date'])).days
        gap_end = (pd.Timestamp(consol_end_date) - pd.Timestamp(p['consolidation_end_date'])).days
        print(f'  当前算法: MATCH! gap_start={gap_start}d gap_end={gap_end}d')
        print(f'    上涨: {p["uptrend_start_date"]}->{p["uptrend_end_date"]} 盘整: {p["consolidation_end_date"]}')
        issues_found[code] = 'MATCH'
    else:
        print(f'  当前算法: MISS')
        issues_found[code] = 'MISS'
    
    # 3. Trace the expected dateline
    ut_start_ts = pd.Timestamp(ut_start_date)
    ut_end_ts = pd.Timestamp(ut_end_date)
    consol_end_ts = pd.Timestamp(consol_end_date)
    
    # Find rows
    mask_start = df['date'].dt.date == ut_start_ts.date()
    mask_peak = df['date'].dt.date == ut_end_ts.date()
    mask_end = df['date'].dt.date == consol_end_ts.date()
    
    if mask_start.any() and mask_peak.any():
        start_i = df[mask_start].index[0]
        peak_i = df[mask_peak].index[0]
        
        start_p = df.loc[start_i, 'close']
        peak_p = df.loc[peak_i, 'close']
        gain = (peak_p - start_p) / start_p
        ut_days = peak_i - start_i + 1
        
        # Check bullish arrangement during uptrend
        bull_days = sum(1 for i in range(start_i, peak_i+1) if TechnicalIndicators.is_bullish_arrangement(df, i))
        
        print(f'  期望上涨: {ut_start_date}(¥{start_p:.1f}) -> {ut_end_date}(¥{peak_p:.1f})')
        print(f'    涨幅: {gain:.1%}  天数: {ut_days}  其中多头: {bull_days}/{ut_days}')
        
        # Check if algorithm rejects due to uptrend
        if gain < config['uptrend_gain']:
            print(f'    ⚠️ 涨幅不足: {gain:.1%} < {config["uptrend_gain"]:.0%}')
        if ut_days < config.get('uptrend_min_days', 5):
            print(f'    ⚠️ 天数太短: {ut_days} < {config.get("uptrend_min_days",5)}')
        if bull_days < ut_days:
            print(f'    ⚠️ 多头不连续: {bull_days}/{ut_days}')
        
        # Check consolidation
        if mask_end.any():
            end_i = df[mask_end].index[0]
            consol_days = end_i - peak_i
            period = df.loc[peak_i:end_i]
            min_c = period['close'].min()
            avg_c = period['close'].mean()
            retrace = (peak_p - min_c) / peak_p
            avg_drop = (peak_p - avg_c) / peak_p
            
            if 'bb_bandwidth' in period.columns:
                avg_bw = period['bb_bandwidth'].mean()
                vol = TechnicalIndicators.calculate_volatility(df, peak_i, end_i)
                avg_vr = period['volume_ratio'].mean()
            else:
                avg_bw = 999; vol = 999; avg_vr = 999
            
            print(f'  期望盘整: {ut_end_date} -> {consol_end_date} ({consol_days}天)')
            print(f'    回撤: {retrace:.1%}  均价距峰顶: {avg_drop:.1%}  振幅: {vol:.1%}  带宽: {avg_bw:.1%}  量比: {avg_vr:.1%}')
            
            failures = []
            if consol_days > config['consolidation_days_max']:
                failures.append(f'盘整天数 {consol_days} > {config["consolidation_days_max"]} (MAX!)')
            if consol_days < config['consolidation_days_min']:
                failures.append(f'盘整天数 {consol_days} < {config["consolidation_days_min"]}')
            if retrace > config['max_retrace_pct']:
                failures.append(f'回撤 {retrace:.1%} > {config["max_retrace_pct"]:.0%}')
            if avg_drop > config['max_retrace_pct'] * 0.6:
                failures.append(f'均价距峰 {avg_drop:.1%} > {config["max_retrace_pct"]*0.6:.1%}')
            if vol >= config['volatility']:
                failures.append(f'振幅 {vol:.1%} >= {config["volatility"]:.0%}')
            if avg_bw >= config['bandwidth']:
                failures.append(f'带宽 {avg_bw:.1%} >= {config["bandwidth"]:.0%}')
            
            for f in failures:
                print(f'    ⚠️ {f}')
        else:
            print(f'  期望盘整终点 {consol_end_date} 不在数据中 (可能继续到今天)')
    else:
        print(f'  找不到期塑的日期行')
    
    print()

# Summary
print('='*60)
print('问题汇总:')
for code, issue in issues_found.items():
    print(f'  {code}: {issue}')

# Key fixes
print()
print('需要修复:')
print('  1. 300136 被 _is_main_board 过滤 → 创业板/深市都保留')
print('  2. consolidation_days_max=40 太短 → 用户例子盘整30-200天')
print('  3. 大盘整段中因为持续时间长, 波动自然大 → 阈值不够容忍')

f.close()
