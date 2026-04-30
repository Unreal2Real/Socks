import pandas as pd
import numpy as np
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from indicators.technical import TechnicalIndicators

np.random.seed(42)

BASE_PRICE = 20.0
DAYS = 120

def make_ma5(ma10, noise=0.01):
    return ma10 * (1 + np.random.uniform(-noise, noise))

def make_ma10(ma20, noise=0.015):
    return ma20 * (1 + np.random.uniform(-noise, noise))

dates = pd.date_range('2025-01-01', periods=DAYS, freq='B')

# =============================================
# Case A: 完美形态
# =============================================
# 上涨段: 10天, 从20→24 (+20%), MA5>MA10>MA20 持续
# 盘整段: 20天, 布林带收窄(0.08), 波动率低(0.12), 成交量萎缩(0.35)
# 完美通过所有阈值
close_A = []
close_A.append(BASE_PRICE)
for day in range(1, DAYS):
    if day <= 10:
        pct = 0.018 + np.random.uniform(-0.003, 0.003)
        close_A.append(close_A[-1] * (1 + pct))
    elif day <= 30:
        pct = np.random.uniform(-0.005, 0.005)
        close_A.append(close_A[-1] * (1 + pct))
    else:
        pct = np.random.uniform(-0.008, 0.008)
        close_A.append(close_A[-1] * (1 + pct))
close_A = np.array(close_A)

high_A = close_A * (1 + np.random.uniform(0.005, 0.015, DAYS))
low_A  = close_A * (1 - np.random.uniform(0.005, 0.015, DAYS))
open_A = close_A * (1 + np.random.uniform(-0.003, 0.003, DAYS))
vol_A  = np.full(DAYS, 8_000_000)
vol_A[11:31] = 3_000_000

df_A = pd.DataFrame({
    'date': dates, 'open': open_A, 'high': high_A,
    'low': low_A, 'close': close_A, 'volume': vol_A
})
df_A = TechnicalIndicators.calculate_all(df_A)

# =============================================
# Case B: 上涨不足 (14% 刚好不够)
# =============================================
close_B = [BASE_PRICE]
for day in range(1, DAYS):
    if day <= 10:
        pct = 0.013 + np.random.uniform(-0.002, 0.002)
        close_B.append(close_B[-1] * (1 + pct))
    elif day <= 30:
        pct = np.random.uniform(-0.005, 0.005)
        close_B.append(close_B[-1] * (1 + pct))
    else:
        pct = np.random.uniform(-0.008, 0.008)
        close_B.append(close_B[-1] * (1 + pct))
close_B = np.array(close_B)
gain_B = (close_B[10] - close_B[0]) / close_B[0]

high_B = close_B * (1 + np.random.uniform(0.005, 0.015, DAYS))
low_B  = close_B * (1 - np.random.uniform(0.005, 0.015, DAYS))
open_B = close_B * (1 + np.random.uniform(-0.003, 0.003, DAYS))
vol_B  = np.full(DAYS, 8_000_000)
vol_B[11:31] = 3_000_000

df_B = pd.DataFrame({
    'date': dates, 'open': open_B, 'high': high_B,
    'low': low_B, 'close': close_B, 'volume': vol_B
})
df_B = TechnicalIndicators.calculate_all(df_B)

# =============================================
# Case C: 盘整成交量萎缩不足 (volume_ratio=0.70)
# =============================================
close_C = [BASE_PRICE]
for day in range(1, DAYS):
    if day <= 10:
        pct = 0.020 + np.random.uniform(-0.002, 0.002)
        close_C.append(close_C[-1] * (1 + pct))
    elif day <= 30:
        pct = np.random.uniform(-0.005, 0.005)
        close_C.append(close_C[-1] * (1 + pct))
    else:
        pct = np.random.uniform(-0.008, 0.008)
        close_C.append(close_C[-1] * (1 + pct))
close_C = np.array(close_C)

high_C = close_C * (1 + np.random.uniform(0.005, 0.015, DAYS))
low_C  = close_C * (1 - np.random.uniform(0.005, 0.015, DAYS))
open_C = close_C * (1 + np.random.uniform(-0.003, 0.003, DAYS))
vol_C  = np.full(DAYS, 8_000_000)
vol_C[11:31] = 5_500_000  # 成交量比 = 5.5M / 8M = 0.6875  > 0.6

df_C = pd.DataFrame({
    'date': dates, 'open': open_C, 'high': high_C,
    'low': low_C, 'close': close_C, 'volume': vol_C
})
df_C = TechnicalIndicators.calculate_all(df_C)

# =============================================
# Case D: 盘整天数过长 (55天，>40上限)
# =============================================
close_D = [BASE_PRICE]
for day in range(1, DAYS):
    if day <= 10:
        pct = 0.020 + np.random.uniform(-0.002, 0.002)
        close_D.append(close_D[-1] * (1 + pct))
    elif day <= 65:
        pct = np.random.uniform(-0.004, 0.004)
        close_D.append(close_D[-1] * (1 + pct))
    else:
        pct = np.random.uniform(-0.008, 0.008)
        close_D.append(close_D[-1] * (1 + pct))
close_D = np.array(close_D)

high_D = close_D * (1 + np.random.uniform(0.005, 0.015, DAYS))
low_D  = close_D * (1 - np.random.uniform(0.005, 0.015, DAYS))
open_D = close_D * (1 + np.random.uniform(-0.003, 0.003, DAYS))
vol_D  = np.full(DAYS, 8_000_000)
vol_D[11:66] = 3_000_000

df_D = pd.DataFrame({
    'date': dates, 'open': open_D, 'high': high_D,
    'low': low_D, 'close': close_D, 'volume': vol_D
})
df_D = TechnicalIndicators.calculate_all(df_D)

# =============================================
# 计算各 case 的关键指标
# =============================================
def calc_case(df, name, label, desc, verdict, uptrend_days=10, consol_days=20):
    idx_s = uptrend_days
    idx_e = uptrend_days + consol_days
    close_s = df.loc[idx_s, 'close']
    close_e = df.loc[idx_e, 'close']

    # 实际上涨涨幅
    gain = (df.loc[uptrend_days, 'close'] - df.loc[0, 'close']) / df.loc[0, 'close']

    # 盘整带宽
    consol_df = df.iloc[uptrend_days:uptrend_days+consol_days+1]
    bw = consol_df['bb_bandwidth'].mean()

    # 波动率
    from indicators.technical import TechnicalIndicators as TI
    vol = TI.calculate_volatility(df, uptrend_days, uptrend_days+consol_days)

    # 成交量比
    vr = consol_df['volume_ratio'].mean()

    return {
        'name': name,
        'label': label,
        'desc': desc,
        'verdict': verdict,
        'gain': gain,
        'bw': bw,
        'vol': vol,
        'vr': vr,
        'consol_days': consol_days,
    }

cases = [
    calc_case(df_A, 'A', '完美形态', '各项指标均在理想范围内',
              '✅ 通过', 10, 20),
    calc_case(df_B, 'B', '上涨不足', '涨幅仅 13%，未达到 15% 阈值',
              '❌ 淘汰', 10, 20),
    calc_case(df_C, 'C', '成交量萎缩不足', f'成交量比 {vol_C[11]/vol_C[0]:.2f} > 0.60 阈值',
              '❌ 淘汰', 10, 20),
    calc_case(df_D, 'D', '盘整天数过长', f'盘整 55 天 > 40 天上限',
              '❌ 淘汰', 10, 55),
]

# 输出到 JS 变量
import json

for i, c in enumerate(cases):
    print(f"Case {c['name']}: gain={c['gain']:.1%}, bw={c['bw']:.3f}, vol={c['vol']:.3f}, vr={c['vr']:.3f}, consol={c['consol_days']}d")

print("\nSummary JSON:")
print(json.dumps(cases, ensure_ascii=False, indent=2))
