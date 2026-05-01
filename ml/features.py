"""Feature extractor for ML model"""
import numpy as np
from typing import Dict, Optional


def extract_features(df, start_idx: int, peak_idx: int, end_idx: int) -> Dict[str, float]:
    sp = float(df.loc[start_idx, 'close'])
    pp = float(df.loc[peak_idx, 'close'])
    n = len(df)

    segment = df.loc[start_idx:end_idx]
    up_segment = df.loc[start_idx:peak_idx]
    consol_segment = df.loc[peak_idx:end_idx]

    gain = (pp - sp) / sp
    up_days = peak_idx - start_idx + 1
    consol_days = end_idx - peak_idx

    min_close = float(consol_segment['close'].min())
    avg_close = float(consol_segment['close'].mean())
    last_close = float(consol_segment['close'].iloc[-1])

    elevation = (min_close - sp) / sp
    peak_ratio = min_close / pp
    avg_retrace = (pp - avg_close) / pp
    last_retrace = (pp - last_close) / pp

    consol_high = float(consol_segment['close'].max())
    consol_low = min_close
    volatility = (consol_high - consol_low) / avg_close if avg_close > 0 else 0

    age_days = n - 1 - end_idx

    pre = df.loc[max(0, start_idx - 20):start_idx]
    if len(pre) > 3:
        pre_vol = (float(pre['close'].max()) - float(pre['close'].min())) / float(pre['close'].mean())
    else:
        pre_vol = 1.0

    up_vol = float(up_segment['close'].std()) / float(up_segment['close'].mean()) if len(up_segment) > 1 else 0

    return {
        'gain': round(gain, 6),
        'up_days': float(up_days),
        'consol_days': float(consol_days),
        'elevation': round(elevation, 6),
        'peak_ratio': round(peak_ratio, 6),
        'avg_retrace': round(avg_retrace, 6),
        'last_retrace': round(last_retrace, 6),
        'volatility': round(volatility, 6),
        'age_days': float(age_days),
        'pre_volatility': round(pre_vol, 6),
        'up_volatility': round(up_vol, 6),
        'price': round(float(df.loc[end_idx, 'close']), 2),
        'peak_price': round(pp, 2),
        'start_price': round(sp, 2),
    }
