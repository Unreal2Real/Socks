"""Extract reference curves from 8 user-labeled stocks"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pandas as pd
import numpy as np
from data.fetcher import DataFetcher
from indicators.technical import TechnicalIndicators

f = DataFetcher()

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

os.makedirs('templates/factory', exist_ok=True)

for code, (us, ue, ce) in expected.items():
    df = f.daily_data(code, days=1000 if code == '003036' else 500)
    if df.empty:
        print(f'{code}: NO DATA')
        continue

    df = TechnicalIndicators.calculate_all(df.ffill().bfill())

    us_ts = pd.Timestamp(us)
    ce_ts = pd.Timestamp(ce)

    m_s = df['date'].dt.date == us_ts.date()
    m_e = df['date'].dt.date == ce_ts.date()

    if not m_s.any():
        print(f'{code}: start date {us} not found')
        continue
    if not m_e.any():
        ei = len(df) - 1
        ce = str(df.iloc[-1]['date'].date())
        print(f'{code}: end date not found, using last data point {ce}')
    else:
        ei = df[m_e].index[0]

    si = df[m_s].index[0]
    segment = df.loc[si:ei]
    closes = segment['close'].values
    dates = segment['date'].dt.strftime('%Y-%m-%d').values

    norm = (closes - closes.min()) / (closes.max() - closes.min() + 1e-10)

    entry = {
        'stock_code': code,
        'stock_name': df.loc[si, 'name'] if 'name' in df.columns else '',
        'start_date': us,
        'end_date': ce,
        'days': len(norm),
        'points': [{'date': str(d), 'price': float(c), 'norm': float(n)}
                    for d, c, n in zip(dates, closes, norm)],
        'series': norm.tolist(),
    }

    path = os.path.join('templates', 'factory', f'{code}.json')
    with open(path, 'w', encoding='utf-8') as fp:
        json.dump(entry, fp, ensure_ascii=False, indent=2)

    print(f'{code}: {len(norm)} days saved → templates/factory/{code}.json')

f.close()
print('\nDone. 8 reference curves saved.')
