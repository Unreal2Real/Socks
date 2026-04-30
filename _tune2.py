"""Test retrace=12% + vol=12% - find candidates"""
import sys; sys.path.insert(0,'.')
from data.fetcher import DataFetcher
from pattern.recognizer import PatternRecognizer
from _config import FACTORY_PATTERN

f = DataFetcher()
r = PatternRecognizer(FACTORY_PATTERN)
stocks = f.stock_list()[:500]

matches = []
for code, name in stocks:
    df = f.daily_data(code, days=500)
    if df.empty or len(df) < 60:
        continue
    p = r.find_pattern(df)
    if p:
        peak_df = df[df['date'].dt.strftime('%Y-%m-%d') == p['uptrend_end_date']]
        if not peak_df.empty:
            peak_price = float(peak_df['close'].iloc[0])
            start_idx = p['uptrend_end_idx']
            end_idx = p['consolidation_end_idx']
            consol = df.loc[start_idx:end_idx, 'close']
            min_p = consol.min()
            avg_p = consol.mean()
            retrace = (peak_price - min_p) / peak_price * 100
            avg_drop = (peak_price - avg_p) / peak_price * 100
            p['actual_retrace'] = round(retrace, 1)
            p['avg_drop'] = round(avg_drop, 1)
        p['stock_code'] = code
        p['stock_name'] = name
        matches.append(p)

matches.sort(key=lambda x: x['actual_retrace'])
print(f'{len(matches)} matches:')
for p in matches[:15]:
    print(f"  {p['stock_code']} {p['stock_name']} score={p['pattern_score']:.2f} retrace={p.get('actual_retrace','?')}% avg_drop={p.get('avg_drop','?')}%")

f.close()
