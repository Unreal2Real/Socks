"""Debug: what peaks does the new algorithm find?"""
import sys; sys.path.insert(0,'.')
import pandas as pd
from data.fetcher import DataFetcher
from indicators.technical import TechnicalIndicators
from pattern.recognizer import PatternRecognizer
from _config import FACTORY_PATTERN

f = DataFetcher()
r = PatternRecognizer(FACTORY_PATTERN)

codes = ['603629','002008','300136','002796','003036','002149','002655','002980']

for code in codes:
    df = f.daily_data(code, days=1000 if code == '003036' else 500)
    df = TechnicalIndicators.calculate_all(df.ffill().bfill())
    n = len(df)
    
    peaks = r._find_peaks(df)
    print(f'{code}: {len(peaks)} peaks')
    
    # Show peaks near recent data
    recent_peaks = [p for p in peaks if p > n - 200]
    for p in recent_peaks[:10]:
        pd_date = df.loc[p, 'date'].date()
        pp = float(df.loc[p, 'close'])
        start = r._find_uptrend_start(df, p)
        if start:
            sd = df.loc[start, 'date'].date()
            sp = float(df.loc[start, 'close'])
            gain = (pp-sp)/sp
            print(f'  peak={pd_date} ¥{pp:.1f} start={sd} ¥{sp:.1f} gain={gain:.1%}')
    print()

f.close()
