"""diagnose ref stocks v2"""
import sys; sys.path.insert(0,'.')
import pandas as pd, numpy as np
from data.fetcher import DataFetcher
from pattern.recognizer import PatternRecognizer
from indicators.technical import TechnicalIndicators
from _config import FACTORY_PATTERN, SCAN

fetcher = DataFetcher()
config = dict(FACTORY_PATTERN)

refs = [
    ('603629', '2026-01-21', '2026-02-12', '2026-04-07'),
    ('002008', '2026-02-12', '2026-03-02', '2026-04-07'),
    ('300136', '2025-12-24', '2026-01-22', '2026-04-13'),
    ('002796', '2025-12-16', '2026-01-28', '2026-02-12'),
    ('003036', '2025-06-16', '2025-08-06', '2026-03-17'),
    ('002149', '2025-12-01', '2026-01-12', '2026-04-14'),
    ('002655', '2026-02-10', '2026-03-02', '2026-04-02'),
    ('002980', '2026-02-25', '2026-03-11', '2026-03-27'),
]

print(f'Config: gain>={config["uptrend_gain"]:.0%} min_up_days={config.get("uptrend_min_days",5)}')
print(f'consol_min={config["consolidation_days_min"]}d elevation>={config.get("min_elevation",0.10):.0%}')
print()

for code, us, ue, ce in refs:
    df = fetcher.daily_data(code, days=500)
    if df.empty:
        print(f'{code}: NO DATA')
        continue
    
    df = TechnicalIndicators.calculate_all(df.ffill().bfill())
    
    us_ts = pd.Timestamp(us); ue_ts = pd.Timestamp(ue); ce_ts = pd.Timestamp(ce)
    m_s = df['date'].dt.date == us_ts.date()
    m_p = df['date'].dt.date == ue_ts.date()
    m_e = df['date'].dt.date == ce_ts.date()
    
    if not m_s.any() or not m_p.any():
        print(f'{code}: date not found in data')
        continue
    
    si = df[m_s].index[0]
    pi = df[m_p].index[0]
    sp = float(df.loc[si, 'close'])
    pp = float(df.loc[pi, 'close'])
    gain_pct = (pp - sp) / sp * 100
    up_days = pi - si + 1
    
    print(f'{code}:')
    print(f'  涨幅: {gain_pct:.0f}% ({up_days}d)  ¥{sp:.1f}→¥{pp:.1f}')
    
    if m_e.any():
        ei = df[m_e].index[0]
    else:
        ei = len(df) - 1
        ce = str(df.iloc[-1]['date'].date())
    
    consol_days = ei - pi
    period = df.loc[pi:ei]
    min_c = float(period['close'].min())
    avg_c = float(period['close'].mean())
    last_c = float(period['close'].iloc[-1])
    
    ret = (pp - min_c) / pp * 100
    avg_r = (pp - avg_c) / pp * 100
    from_start = (min_c - sp) / sp * 100
    
    bw = float(period['bb_bandwidth'].mean()) if 'bb_bandwidth' in period.columns else 999
    vl = TechnicalIndicators.calculate_volatility(df, pi, ei) * 100
    vr = float(period['volume_ratio'].mean()) if 'volume_ratio' in period.columns else 999
    
    print(f'  盘整: {consol_days}d  (到 {ce})')
    print(f'    峰顶¥{pp:.1f}  最低¥{min_c:.1f}  均价¥{avg_c:.1f}')
    print(f'    回撤: {ret:.1f}%  均价距峰: {avg_r:.1f}%  最低距起点: +{from_start:.1f}%')
    print(f'    振幅: {vl:.1f}%  带宽: {bw:.1f}%  量比: {vr:.1f}%')
    
    checks = []
    if gain_pct/100 < config['uptrend_gain']: checks.append(f'gain {gain_pct:.0f}%<{config["uptrend_gain"]*100:.0f}%')
    if up_days < config.get('uptrend_min_days',5): checks.append(f'days {up_days}<{config.get("uptrend_min_days",5)}')
    if consol_days < config['consolidation_days_min']: checks.append(f'consol {consol_days}<{config["consolidation_days_min"]}')
    elevation = from_start / 100
    if elevation < config.get('min_elevation', 0.10): checks.append(f'elevation {from_start:.1f}%<{config.get("min_elevation",0.10)*100:.0f}%')
    
    if checks:
        print(f'    ❌ 失败: {", ".join(checks)}')
    else:
        print(f'    ✅ 全部通过')
    
    # WHAT MATTERS MOST: is the stock still elevated vs the uptrend start?
    is_elevated = from_start > gain_pct * 0.3  # at least 30% of the gain remains
    print(f'    核心: 仍高于起点+{from_start:.1f}% ← {"✅ 厂商字" if is_elevated else "❌ 跌回去了"}')

fetcher.close()
