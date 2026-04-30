"""检查匹配的厂字形态：上涨后是否真的没有下跌"""
import json, sys; sys.path.insert(0,'.')
from data.fetcher import DataFetcher
from _config import FACTORY_PATTERN
from indicators.technical import TechnicalIndicators

with open('results/latest_scan.json','r',encoding='utf-8') as f:
    results = json.load(f)['results']

f = DataFetcher()
config = FACTORY_PATTERN

for r in results:
    code = r['stock_code']
    name = r['stock_name']
    df = f.daily_data(code, days=500)
    df = TechnicalIndicators.calculate_all(df.ffill().bfill())
    
    # 从 pattern 中获取关键索引——需要重新找到对应的行
    end_date = r['consolidation_end_date']
    start_date = r['uptrend_start_date']
    uptrend_end_date = r['uptrend_end_date']
    
    # 找到对应行
    df['date_str'] = df['date'].dt.strftime('%Y-%m-%d')
    start_row = df[df['date_str'] == start_date]
    peak_row = df[df['date_str'] == uptrend_end_date]
    end_row = df[df['date_str'] == end_date]
    
    if start_row.empty or peak_row.empty or end_row.empty:
        print(f'{code} {name}: 日期匹配失败')
        continue
    
    start_idx = start_row.index[0]
    peak_idx = peak_row.index[0]
    end_idx = end_row.index[0]
    
    peak_price = df.loc[peak_idx, 'close']
    start_price = df.loc[start_idx, 'close']
    
    # 盘整段最低价
    consol_df = df.loc[peak_idx:end_idx]
    consol_low = consol_df['close'].min()
    consol_high = consol_df['close'].max()
    consol_close = df.loc[end_idx, 'close']
    
    # 关键指标
    retrace_pct = (peak_price - consol_low) / peak_price * 100  # 从峰顶回撤%
    consol_range = (consol_high - consol_low) / peak_price * 100  # 盘整振幅%
    peak_to_end = (peak_price - consol_close) / peak_price * 100  # 峰顶到结束%
    
    # 盘整段每天的价格
    prices = consol_df['close'].tolist()
    
    print(f'\n{code} {name}')
    print(f'  上涨: {start_date}({start_price:.1f}) → {uptrend_end_date}({peak_price:.1f})  +{(peak_price/start_price-1)*100:.1f}%')
    print(f'  盘整: {uptrend_end_date} → {end_date}  ({len(consol_df)}天)')
    print(f'  峰顶回落: {retrace_pct:.1f}%  盘整振幅: {consol_range:.1f}%  收在: {consol_close:.1f}')
    
    # 判断问题
    issues = []
    if retrace_pct > 10:
        issues.append(f'⚠️ 从顶峰回落 {retrace_pct:.1f}% → 不是"横在那里"')
    if consol_close < peak_price * 0.95:
        issues.append(f'⚠️ 收盘价远离顶峰 {(1-consol_close/peak_price)*100:.1f}%')
    if consol_range > 10:
        issues.append(f'⚠️ 盘整振幅 {consol_range:.1f}% → 波动太大')
    
    if not issues:
        print(f'  ✅ 形态正确: 涨后横盘不跌')
    else:
        for i in issues:
            print(f'  {i}')

f.close()
