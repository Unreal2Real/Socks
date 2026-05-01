"""Seed the ML training data with the 8 reference stocks"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pandas as pd
from data.fetcher import DataFetcher
from indicators.technical import TechnicalIndicators
from ml import features, labels, trainer

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

for code, (u_start, u_end, c_end) in expected.items():
    df = f.daily_data(code, days=1000 if code == '003036' else 500)
    df = TechnicalIndicators.calculate_all(df.ffill().bfill())

    us_ts = pd.Timestamp(u_start)
    ue_ts = pd.Timestamp(u_end)
    ce_ts = pd.Timestamp(c_end)

    m_s = df['date'].dt.date == us_ts.date()
    m_p = df['date'].dt.date == ue_ts.date()
    m_e = df['date'].dt.date == ce_ts.date()

    if not m_s.any() or not m_p.any():
        print(f'{code}: date not found')
        continue

    si = df[m_s].index[0]
    pi = df[m_p].index[0]
    ei = df[m_e].index[0] if m_e.any() else len(df) - 1

    feat = features.extract_features(df, si, pi, ei)
    name_lookup = {'603629': '603629', '002008': '大族激光', '300136': '信维通信',
                   '002796': '世嘉科技', '003036': '泰坦股份', '002149': '西部材料',
                   '002655': '共达电声', '002980': '华盛昌'}

    labels.save_label({
        'stock_code': code,
        'stock_name': name_lookup.get(code, code),
        'label': 'good',
        'features': feat,
    })

    print(f'{code}: seeded ✓')

# Also seed BAD examples using the algorithm's wrong picks
bad_examples = {
    '603629': ('2026-02-04', '2026-02-12', '2026-04-29'),
    '003036': ('2025-07-15', '2025-08-06', '2025-08-26'),
    '002980': ('2025-07-31', '2025-08-20', '2025-10-16'),
}

for code, (st, pk, en) in bad_examples.items():
    df = f.daily_data(code, days=1000 if code == '003036' else 500)
    df = TechnicalIndicators.calculate_all(df.ffill().bfill())

    ms = df['date'].dt.date == pd.Timestamp(st).date()
    mp = df['date'].dt.date == pd.Timestamp(pk).date()
    me = df['date'].dt.date == pd.Timestamp(en).date()

    if not ms.any() or not mp.any():
        print(f'{code} BAD: date not found')
        continue

    si = df[ms].index[0]
    pi = df[mp].index[0]
    ei = df[me].index[0]

    feat = features.extract_features(df, si, pi, ei)
    labels.save_label({
        'stock_code': code,
        'stock_name': code,
        'label': 'bad',
        'features': feat,
    })
    print(f'{code}: bad seeded ✓')

f.close()

all_labels = labels.load_labels()
model, metrics = trainer.train_from_labels(all_labels)
stats = labels.get_stats()
print(f'\nTotal labels: {stats["total"]} (good={stats["good"]} bad={stats["bad"]})')
print(f'Training result: {metrics}')
