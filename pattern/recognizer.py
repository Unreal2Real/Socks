import pandas as pd
import numpy as np
from typing import Optional, Tuple
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from indicators.technical import TechnicalIndicators


class PatternRecognizer:

    def __init__(self, config: dict):
        self.uptrend_gain_threshold = config.get('uptrend_gain', 0.15)
        self.consolidation_days_min = config.get('consolidation_days_min', 10)
        self.uptrend_min_days = config.get('uptrend_min_days', 5)
        self.min_elevation = config.get('min_elevation', 0.10)

    def find_pattern(self, df: pd.DataFrame,
                     max_days_back: int = None) -> Optional[dict]:

        if len(df) < 60:
            return None

        if max_days_back and len(df) > max_days_back + 60:
            df = df.tail(max_days_back + 60).reset_index(drop=True)

        df = TechnicalIndicators.calculate_all(df.ffill().bfill())
        n = len(df)
        start_i = n - self.consolidation_days_min - 1

        best = None
        best_score = -1

        for i in range(start_i, 20, -1):
            uptrend = self._scan_uptrend(df, i)
            if not uptrend:
                continue

            peak_idx, gain = uptrend
            start_price = df.loc[i, 'close']
            efficiency = gain / (peak_idx - i + 1)

            consol = self._scan_consolidation(df, peak_idx, start_price)
            if consol:
                end_idx, consol_days = consol
                if efficiency > best_score:
                    best_score = efficiency
                    best = ('done', i, peak_idx, gain, end_idx, consol_days)
                continue

            last_idx = n - 1
            if last_idx - peak_idx >= self.consolidation_days_min:
                consol_df = df.loc[peak_idx:last_idx]
                if (consol_df['close'].min() - start_price) / start_price >= self.min_elevation:
                    if efficiency > best_score:
                        best_score = efficiency
                        best = ('ongoing', i, peak_idx, gain, last_idx, last_idx - peak_idx)

        if best:
            _, i, peak_idx, gain, end_idx, consol_days = best
            return self._build_result(df, i, peak_idx, gain, end_idx, consol_days)

        return None

    def _scan_uptrend(self, df: pd.DataFrame, start_idx: int) -> Optional[Tuple[int, float]]:
        start_price = df.loc[start_idx, 'close']
        peak_idx = start_idx
        peak_price = start_price
        below_ma5 = 0
        max_i = len(df) - self.consolidation_days_min

        for i in range(start_idx + 1, max_i):
            cur = df.loc[i, 'close']
            if cur > peak_price:
                peak_price = cur
                peak_idx = i

            if df.loc[i, 'close'] < df.loc[i, 'ma5']:
                below_ma5 += 1
                if below_ma5 >= 3 and peak_price > start_price:
                    gain = (peak_price - start_price) / start_price
                    if gain >= self.uptrend_gain_threshold and peak_idx - start_idx + 1 >= self.uptrend_min_days:
                        return peak_idx, gain
            else:
                below_ma5 = 0

        return None

    def _scan_consolidation(self, df: pd.DataFrame, start_idx: int,
                            start_price: float) -> Optional[Tuple[int, int]]:
        n = len(df)
        for i in range(start_idx + self.consolidation_days_min, min(start_idx + 180, n)):
            min_c = df.loc[start_idx:i, 'close'].min()
            if (min_c - start_price) / start_price >= self.min_elevation:
                return i, i - start_idx
        return None

    def _build_result(self, df, start_i, peak_idx, gain, end_idx, days):
        return {
            'uptrend_start_idx': start_i,
            'uptrend_start_date': str(df.loc[start_i, 'date'])[:10],
            'uptrend_end_idx': peak_idx,
            'uptrend_end_date': str(df.loc[peak_idx, 'date'])[:10],
            'uptrend_gain': round(gain, 4),
            'consolidation_start_idx': peak_idx,
            'consolidation_start_date': str(df.loc[peak_idx, 'date'])[:10],
            'consolidation_end_idx': end_idx,
            'consolidation_end_date': str(df.loc[end_idx, 'date'])[:10],
            'consolidation_days': days,
            'pattern_score': round(gain, 2),
            'type': 'factory',
        }
