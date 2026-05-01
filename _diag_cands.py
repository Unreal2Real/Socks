"""Debug all candidates for failed stocks"""
import sys; sys.path.insert(0,'.')
import pandas as pd
from data.fetcher import DataFetcher
from indicators.technical import TechnicalIndicators
from pattern.recognizer import PatternRecognizer
from _config import FACTORY_PATTERN

f = DataFetcher()
r = PatternRecognizer(FACTORY_PATTERN)

for code in ['603629','300136','003036','002980']:
    print(f'=== {code} ===')
    df = f.daily_data(code, days=1000 if code == '003036' else 500)
    df = TechnicalIndicators.calculate_all(df.ffill().bfill())
    n = len(df)
    
    candidates = r._find_all_candidates(df, n)
    print(f'  {len(candidates)} candidates')
    
    candidates.sort(key=lambda x: x['score'], reverse=True)
    for c in candidates[:5]:
        sd = df.loc[c['start_idx'], 'date'].date()
        pd_ = df.loc[c['peak_idx'], 'date'].date()
        ed = df.loc[c['end_idx'], 'date'].date()
        print(f'  start={sd} peak={pd_} end={ed} gain={c["gain"]:.1%} score={c["score"]:.3f}')
    
    if not candidates:
        crosses = r._find_golden_crosses(df, n)
        print(f'  Golden crosses: {len(crosses)}')
        for gc in crosses[-5:]:
            print(f'    {df.loc[gc,"date"].date()}')

f.close()
