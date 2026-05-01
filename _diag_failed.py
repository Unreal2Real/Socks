"""Debug: why stocks fail - check valley/peak/consolidation"""
import sys; sys.path.insert(0,'.')
import pandas as pd
from data.fetcher import DataFetcher
from indicators.technical import TechnicalIndicators
from _config import FACTORY_PATTERN

f = DataFetcher()
config = FACTORY_PATTERN

problems = [
    ('603629', '2026-01-21', '2026-02-12', '2026-04-07'),
    ('300136', '2025-12-24', '2026-01-22', '2026-04-13'),
    ('003036', '2025-06-16', '2025-08-06', '2026-03-17'),
    ('002980', '2026-02-25', '2026-03-11', '2026-03-27'),
]

for code, us, ue, ce in problems:
    print(f'=== {code} ===')
    df = f.daily_data(code, days=1000 if code == '003036' else 500)
    df = TechnicalIndicators.calculate_all(df.ffill().bfill())
    n = len(df)
    
    us_ts = pd.Timestamp(us); ue_ts = pd.Timestamp(ue); ce_ts = pd.Timestamp(ce)
    m_s = df['date'].dt.date == us_ts.date()
    m_p = df['date'].dt.date == ue_ts.date()
    m_e = df['date'].dt.date == ce_ts.date()
    
    if not m_s.any() or not m_p.any():
        print(f'  Date not found')
        continue
    
    si = df[m_s].index[0]
    pi = df[m_p].index[0]
    sp = float(df.loc[si, 'close'])
    pp = float(df.loc[pi, 'close'])
    
    # Check valley
    window = 8
    left_min = float(df.loc[max(si-window,0):si-1, 'close'].min()) if si >= window else float('inf')
    right_min = float(df.loc[si+1:min(si+window,n-1), 'close'].min()) if si < n-window else float('inf')
    is_valley = sp < left_min and sp < right_min
    print(f'  User start: {us} idx={si} price={sp:.1f}')
    print(f'    Valley check (w={window}): left_min={left_min:.1f} right_min={right_min:.1f} → {"VALLEY" if is_valley else "NOT valley"}')
    
    # Check peak
    left_max = float(df.loc[max(pi-window,0):pi-1, 'close'].max()) if pi >= window else 0
    right_max = float(df.loc[pi+1:min(pi+window,n-1), 'close'].max()) if pi < n-window else 0
    is_peak = pp > left_max and pp > right_max
    print(f'  User peak:  {ue} idx={pi} price={pp:.1f}')
    print(f'    Peak check (w={window}): left_max={left_max:.1f} right_max={right_max:.1f} → {"PEAK" if is_peak else "NOT peak"}')
    
    # Check if MA5 breaks after peak
    below_streak = 0
    found_ma5_exit = False
    ma5_exit_day = None
    for k in range(pi, min(pi+30, n)):
        if df.loc[k, 'close'] < df.loc[k, 'ma5']:
            below_streak += 1
            if below_streak >= 3 and not found_ma5_exit:
                found_ma5_exit = True
                ma5_exit_day = df.loc[k, 'date'].date()
        else:
            below_streak = 0
    print(f'    MA5 exit (3d streak): {found_ma5_exit} at {ma5_exit_day}')
    
    # Check consolidation at user's end date
    if m_e.any():
        ei = df[m_e].index[0]
        consol_df = df.loc[pi:ei]
        min_c = float(consol_df['close'].min())
        elev = (min_c - sp) / sp
        print(f'  User consol end: {ce} idx={ei} elev={elev:.1%} (≥{config["min_elevation"]:.0%}? {elev>=config["min_elevation"]})')
    
    print()

f.close()
