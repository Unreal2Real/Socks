"""Deep diagnostic: verify algorithm against user expectations"""
import sys; sys.path.insert(0,'.')
import pandas as pd, numpy as np
from data.fetcher import DataFetcher
from pattern.recognizer import PatternRecognizer
from indicators.technical import TechnicalIndicators
from _config import FACTORY_PATTERN, SCAN

f = DataFetcher()
config = FACTORY_PATTERN
r = PatternRecognizer(config)

# These are the user's expected ranges
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

print('=== Algorithm vs User Expectation ===')
print(f'Config: gain>={config["uptrend_gain"]:.0%} min_up_days={config["uptrend_min_days"]} min_consol={config["consolidation_days_min"]} elevation>={config["min_elevation"]:.0%}')
print()

algo_hits = 0
algo_correct = 0

for code, (exp_us, exp_ue, exp_ce) in expected.items():
    print(f'--- {code} ---')
    df = f.daily_data(code, days=1000 if code in ['003036'] else 500)
    if df.empty:
        print(f'  NO DATA')
        continue
    
    df = TechnicalIndicators.calculate_all(df.ffill().bfill())
    n = len(df)
    
    # Expected dates as timestamps
    exp_us_ts = pd.Timestamp(exp_us)
    exp_ue_ts = pd.Timestamp(exp_ue)
    exp_ce_ts = pd.Timestamp(exp_ce)
    
    # What does algorithm find?
    p = r.find_pattern(df, max_days_back=SCAN.get('max_days_back'))
    if p:
        algo_us = pd.Timestamp(p['uptrend_start_date'])
        algo_ue = pd.Timestamp(p['uptrend_end_date'])
        algo_ce = pd.Timestamp(p['consolidation_end_date'])
        
        # Check if it matches expectation (within 5 days tolerance)
        start_ok = abs((algo_us - exp_us_ts).days) <= 5
        peak_ok = abs((algo_ue - exp_ue_ts).days) <= 5
        end_ok = abs((algo_ce - exp_ce_ts).days) <= 5
        
        print(f'  Expected: {exp_us}->{exp_ue}->{exp_ce}')
        print(f'  Algo:     {p["uptrend_start_date"]}->{p["uptrend_end_date"]}->{p["consolidation_end_date"]}')
        print(f'  Match: start={start_ok} peak={peak_ok} end={end_ok} score={p["pattern_score"]:.2f} gain={p["uptrend_gain"]:.1%}')
        
        algo_hits += 1
        if start_ok and peak_ok and end_ok:
            algo_correct += 1
            print(f'  ✅ CORRECT')
        else:
            # Why different?
            print(f'  ⚠️ MISMATCH - investigating...')
            # Check nearby uptrend starts
            exp_s_mask = df['date'].dt.date == exp_us_ts.date()
            exp_p_mask = df['date'].dt.date == exp_ue_ts.date()
            if exp_s_mask.any() and exp_p_mask.any():
                exp_si = df[exp_s_mask].index[0]
                exp_pi = df[exp_p_mask].index[0]
                exp_sp = float(df.loc[exp_si, 'close'])
                exp_pp = float(df.loc[exp_pi, 'close'])
                exp_gain = (exp_pp - exp_sp) / exp_sp
                print(f'    User expected uptrend: {exp_us}(¥{exp_sp:.1f})->{exp_ue}(¥{exp_pp:.1f}) gain={exp_gain:.1%}')
                
                # Check if expected start is bullish
                is_bull = TechnicalIndicators.is_bullish_arrangement(df, exp_si)
                bull_streak = 0
                for j in range(exp_si-4, exp_si+1):
                    if TechnicalIndicators.is_bullish_arrangement(df, j):
                        bull_streak += 1
                print(f'    Expected start idx={exp_si}: bullish={is_bull} streak={bull_streak}/5')
                if bull_streak < 5:
                    print(f'    ❌ FAIL: insufficient consecutive bullish days at expected start')
                
                # Check if algorithm's start is more bullish
                algo_si = df[df['date'].dt.date == algo_us.date()].index[0]
                algo_sp = float(df.loc[algo_si, 'close'])
                algo_bull = sum(1 for j in range(algo_si-4, algo_si+1) if TechnicalIndicators.is_bullish_arrangement(df, j))
                print(f'    Algo start idx={algo_si}: ¥{algo_sp:.1f} bull={algo_bull}/5')
                
                # The bigger issue: what if the real uptrend continued past what user thinks is the peak?
                print(f'    Checking if uptrend actually continued past {exp_ue}...')
                for k in range(exp_pi+1, min(exp_pi+30, n-10)):
                    if not TechnicalIndicators.is_bullish_arrangement(df, k):
                        break
                    cur = float(df.loc[k, 'close'])
                    cur_g = (cur - exp_sp) / exp_sp
                    if cur > exp_pp:
                        print(f'      ⚠️ Higher peak at {df.loc[k,"date"].date()}: ¥{cur:.1f} gain={cur_g:.1%}')
                        break
    else:
        print(f'  Algorithm MISS')
        # Check why
        exp_s_mask = df['date'].dt.date == exp_us_ts.date()
        if exp_s_mask.any():
            si = df[exp_s_mask].index[0]
            is_bull = sum(1 for j in range(si-4, si+1) if TechnicalIndicators.is_bullish_arrangement(df, j))
            print(f'  Expected start idx={si}: bull_streak={is_bull}/5')
            if is_bull < 5:
                print(f'  → Failed: not enough consecutive bullish days at expected start')
    
    print()

print(f'RESULT: algo_hits={algo_hits}/8 algo_correct={algo_correct}/8')
f.close()
