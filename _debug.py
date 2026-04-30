import sys; sys.path.insert(0,'.')
from data.fetcher import DataFetcher
from pattern.recognizer import PatternRecognizer
from _config import FACTORY_PATTERN
import pandas as pd

f = DataFetcher()
r = PatternRecognizer(FACTORY_PATTERN)

# 放宽参数测试
config2 = dict(FACTORY_PATTERN)
config2['uptrend_gain'] = 0.10
config2['bandwidth'] = 0.30
config2['volatility'] = 0.30
r2 = PatternRecognizer(config2)

test_codes = ['600519','600036','601857','600690','002594','601088','600028']

for code in test_codes:
    df = f.daily_data(code, days=500)
    if df.empty:
        print(f'  {code}: NO DATA')
        continue
    
    # check technical indicators
    import numpy as np
    from indicators.technical import TechnicalIndicators
    df2 = TechnicalIndicators.calculate_all(df.copy().ffill().bfill())
    
    # count bullish arrangement days
    bull_count = sum(1 for i in range(20, len(df2)) if TechnicalIndicators.is_bullish_arrangement(df2, i))
    
    p = r.find_pattern(df)
    p2 = r2.find_pattern(df)
    print(f'  {code}: data={len(df)} bull_days={bull_count} pattern={bool(p)} pattern2={bool(p2)}')
    if p2:
        print(f'    relaxed: score={p2["pattern_score"]:.2f} gain={p2["uptrend_gain"]:.1%} consol={p2["consolidation_days"]}d')
        print(f'    uptrend: {p2["uptrend_start_date"]} -> {p2["uptrend_end_date"]}')
        
f.close()
print('\ndone')
