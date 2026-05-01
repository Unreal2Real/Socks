import sys; sys.path.insert(0,'.')
from data.fetcher import DataFetcher
from indicators.technical import TechnicalIndicators
from _config import FACTORY_PATTERN
f = DataFetcher()
df = f.daily_data('002655', days=500)
df = TechnicalIndicators.calculate_all(df.ffill().bfill())
n = len(df)
consol_min = FACTORY_PATTERN['consolidation_days_min']
found = 0
for i in range(n-consol_min-1, 20, -1):
    if not TechnicalIndicators.is_bullish_arrangement(df, i): continue
    ok = True
    for j in range(i-4,i+1):
        if not TechnicalIndicators.is_bullish_arrangement(df,j): ok=False; break
    if not ok: continue
    sp = df.loc[i,'close']
    peak=i; pp=sp
    for k in range(i+1, n-consol_min):
        if not TechnicalIndicators.is_bullish_arrangement(df,k): break
        cur=df.loc[k,'close']
        if cur>pp: pp=cur; peak=k
        g=(cur-sp)/sp
        if g>=FACTORY_PATTERN['uptrend_gain']:
            days = k-i+1
            if days<FACTORY_PATTERN['uptrend_min_days']: continue
            for jj in range(k+1,min(k+5,n)):
                if df.loc[jj,'close']<df.loc[jj,'ma5']:
                    last_idx=n-1
                    og_days=last_idx-peak
                    period_og=df.loc[peak:last_idx]; min_og=period_og['close'].min()
                    elev_og=(min_og-sp)/sp
                    print(f'  i={i} peak={peak} ongoing={og_days}d elev={elev_og:.1%}')
                    for c in range(peak+consol_min, min(peak+180,n)):
                        period=df.loc[peak:c]; min_c=period['close'].min()
                        elev=(min_c-sp)/sp
                        if elev>=FACTORY_PATTERN['min_elevation']:
                            print(f'  COMPLETED c={c} ({c-peak}d) elev={elev:.1%}')
                            break
                    found+=1; break
        if found>=3: break
    if found>=3: break
f.close()
