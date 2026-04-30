"""Draw the algorithm's interpretation of the pattern"""
import sys; sys.path.insert(0,'.')
import json
from data.fetcher import DataFetcher
from pattern.recognizer import PatternRecognizer
from _config import FACTORY_PATTERN, SCAN
import pandas as pd

f = DataFetcher()
r = PatternRecognizer(FACTORY_PATTERN)

# Pick a few top-scoring ongoing stocks
codes = ['600971','601225','000582','600356','600585','601088']

for code in codes:
    df = f.daily_data(code, days=500)
    if df.empty: continue
    
    p = r.find_pattern(df, max_days_back=SCAN.get('max_days_back'))
    if not p: 
        print(f'{code}: no pattern')
        continue
    
    # Extract the three segments
    start_i = p['uptrend_start_idx'] - 5  # Look back a bit
    end_i = p['consolidation_end_idx'] + 5 if 'consolidation_end_idx' in p else len(df) - 1
    
    seg = df.iloc[max(0,start_i):min(len(df), end_i+1)].copy()
    
    print(f'\n=== {code} (data rows: {start_i} to {end_i}) ===')
    print(f'  形态: score={p["pattern_score"]:.2f} gain={p["uptrend_gain"]:.1%}')
    print(f'  上涨段: idx={p["uptrend_start_idx"]}({p["uptrend_start_date"]}) -> idx={p["uptrend_end_idx"]}({p["uptrend_end_date"]})')
    print(f'  盘整段: idx={p["uptrend_end_idx"]} -> idx={p["consolidation_end_idx"]}({p["consolidation_end_date"]})')
    
    peak_close = df.loc[p['uptrend_end_idx'], 'close']
    min_in_consol = df.loc[p['uptrend_end_idx']:p['consolidation_end_idx'], 'close'].min()
    avg_in_consol = df.loc[p['uptrend_end_idx']:p['consolidation_end_idx'], 'close'].mean()
    retrace = (peak_close - min_in_consol) / peak_close * 100
    avg_drop = (peak_close - avg_in_consol) / peak_close * 100
    
    print(f'  峰顶: {peak_close:.2f}  盘整最低: {min_in_consol:.2f}  盘整均价: {avg_in_consol:.2f}')
    print(f'  回撤: {retrace:.1f}%  均价距峰顶: {avg_drop:.1f}%')
    
    # Show daily close for the consolidation period
    consol_dates = df.loc[p['uptrend_end_idx']:p['consolidation_end_idx'], ['date', 'close', 'ma5', 'ma10', 'ma20']]
    print(f'  盘整段日线 ({len(consol_dates)}天):')
    for _, row in consol_dates.iterrows():
        bull = 'BULL' if row['ma5'] > row['ma10'] > row['ma20'] else ''
        print(f'    {row["date"].date()} close={row["close"]:.2f} {bull}')

f.close()

# Now save benchmark comparison data for visualization
print('\n\n=== Generating visualization data ===')
f2 = DataFetcher()
r2 = PatternRecognizer(FACTORY_PATTERN)

viz_data = []
for code in ['601088', '601225', '600971']:
    df = f2.daily_data(code, days=500)
    if df.empty: continue
    p = r2.find_pattern(df, max_days_back=SCAN.get('max_days_back'))
    if not p: continue
    
    n = len(df)
    start_show = max(0, p['uptrend_start_idx'] - 30)
    end_show = min(n, p['consolidation_end_idx'] + 20)
    
    segment = df.iloc[start_show:end_show]
    points = []
    for _, row in segment.iterrows():
        points.append({
            'date': row['date'].strftime('%Y-%m-%d') if hasattr(row['date'], 'strftime') else str(row['date'])[:10],
            'close': float(row['close']),
            'ma5': float(row['ma5']) if pd.notna(row.get('ma5')) else None,
            'ma10': float(row['ma10']) if pd.notna(row.get('ma10')) else None,
            'ma20': float(row['ma20']) if pd.notna(row.get('ma20')) else None,
        })
    
    viz_data.append({
        'code': code,
        'score': p['pattern_score'],
        'gain': round(p['uptrend_gain'] * 100, 1),
        'retrace': round(retrace, 1),
        'uptrend_start': p['uptrend_start_date'],
        'uptrend_end': p['uptrend_end_date'],
        'consolidation_end': p['consolidation_end_date'],
        'uptrend_start_idx': p['uptrend_start_idx'] - start_show,
        'uptrend_end_idx': p['uptrend_end_idx'] - start_show,
        'consolidation_end_idx': p['consolidation_end_idx'] - start_show,
        'points': points,
    })

with open('results/_viz_data.json', 'w', encoding='utf-8') as f:
    json.dump(viz_data, f, ensure_ascii=False, indent=2)
print(f'Saved {len(viz_data)} patterns to results/_viz_data.json')
f2.close()
