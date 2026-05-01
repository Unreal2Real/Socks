"""Test if user's exact dates pass all algorithm checks"""
import sys; sys.path.insert(0,'.')
import pandas as pd
from data.fetcher import DataFetcher
from indicators.technical import TechnicalIndicators
from _config import FACTORY_PATTERN

f = DataFetcher()
config = FACTORY_PATTERN

checks = [
    ('603629', '2026-01-21', '2026-02-12', '2026-04-07'),
    ('002008', '2026-02-12', '2026-03-02', '2026-04-07'),
    ('300136', '2025-12-24', '2026-01-22', '2026-04-13'),
    ('002796', '2025-12-16', '2026-01-28', '2026-02-12'),
    ('003036', '2025-06-16', '2025-08-06', '2026-03-17'),
    ('002149', '2025-12-01', '2026-01-12', '2026-04-14'),
    ('002655', '2026-02-10', '2026-03-02', '2026-04-02'),
    ('002980', '2026-02-25', '2026-03-11', '2026-03-27'),
]

for code, us, ue, ce in checks:
    df = f.daily_data(code, days=1000 if code == '003036' else 500)
    df = TechnicalIndicators.calculate_all(df.ffill().bfill())
    
    us_ts = pd.Timestamp(us)
    ue_ts = pd.Timestamp(ue)
    ce_ts = pd.Timestamp(ce)
    
    m_s = df['date'].dt.date == us_ts.date()
    m_p = df['date'].dt.date == ue_ts.date()
    m_e = df['date'].dt.date == ce_ts.date()
    
    if not m_s.any() or not m_p.any():
        print(f'{code}: date not in data')
        continue
    
    si = df[m_s].index[0]
    pi = df[m_p].index[0]
    
    sp = float(df.loc[si, 'close'])
    pp = float(df.loc[pi, 'close'])
    gain = (pp - sp) / sp
    
    # Check start condition
    bull_start = sum(1 for j in range(si-4, si+1) if TechnicalIndicators.is_bullish_arrangement(df, j))
    
    # Check uptrend exit: did close go below MA5 for 2 days near peak?
    below_streak = 0
    found_exit = False
    for k in range(pi, min(pi+10, len(df))):
        if df.loc[k, 'close'] < df.loc[k, 'ma5']:
            below_streak += 1
            if below_streak >= 2:
                found_exit = True
                break
        else:
            below_streak = 0
    
    # Check elevation at consolidation end
    elev_ok = False
    if m_e.any():
        ei = df[m_e].index[0]
        consol_df = df.loc[pi:ei]
        min_c = float(consol_df['close'].min())
        elev = (min_c - sp) / sp
        elev_ok = elev >= config['min_elevation']
    else:
        ei = len(df) - 1
        consol_df = df.loc[pi:ei]
        min_c = float(consol_df['close'].min())
        elev = (min_c - sp) / sp
        elev_ok = elev >= config['min_elevation']
    
    issues = []
    if bull_start < 2: issues.append(f'bull_start={bull_start}/5')
    if gain < config['uptrend_gain']: issues.append(f'gain={gain:.1%}<{config["uptrend_gain"]:.0%}')
    if not found_exit: issues.append('no MA5 exit signal near peak')
    if not elev_ok: issues.append(f'elev={elev:.1%}<{config["min_elevation"]:.0%}')
    
    print(f'{code}: start_bull={bull_start}/5 gain={gain:.1%} exit_signal={found_exit} elev_ok={elev_ok}', end='')
    if issues:
        print(f'  ❌ {", ".join(issues)}')
    else:
        print(f'  ✅ ALL PASS')

f.close()
