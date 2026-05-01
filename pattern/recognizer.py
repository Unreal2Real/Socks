import pandas as pd
import numpy as np
from typing import Optional, Tuple
import sys
import os

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
        start = n - self.consolidation_days_min - 1
        end = 20

        for i in range(start, end, -1):
            if not self._is_uptrend_start(df, i):
                continue

            uptrend_result = self._scan_uptrend(df, i)
            if not uptrend_result:
                continue

            uptrend_end_idx, uptrend_gain = uptrend_result
            start_price = df.loc[i, 'close']

            last_idx = n - 1
            ongoing_days = last_idx - uptrend_end_idx
            if ongoing_days >= self.consolidation_days_min and \
               self._is_elevated(df, uptrend_end_idx, last_idx, start_price):
                consolidation_end_idx = last_idx
                consolidation_days = ongoing_days
            else:
                consol = self._scan_consolidation(df, uptrend_end_idx, start_price)
                if consol:
                    consolidation_end_idx, consolidation_days = consol
                else:
                    continue

            return {
                'uptrend_start_idx': i,
                'uptrend_start_date': str(df.loc[i, 'date'])[:10],
                'uptrend_end_idx': uptrend_end_idx,
                'uptrend_end_date': str(df.loc[uptrend_end_idx, 'date'])[:10],
                'uptrend_gain': round(uptrend_gain, 4),
                'consolidation_start_idx': uptrend_end_idx,
                'consolidation_start_date': str(df.loc[uptrend_end_idx, 'date'])[:10],
                'consolidation_end_idx': consolidation_end_idx,
                'consolidation_end_date': str(df.loc[consolidation_end_idx, 'date'])[:10],
                'consolidation_days': consolidation_days,
                'pattern_score': self._calculate_score(i, uptrend_end_idx,
                                                       consolidation_end_idx, df),
                'type': 'factory',
            }

        return None

    def _is_uptrend_start(self, df: pd.DataFrame, idx: int) -> bool:
        bull_count = 0
        for j in range(idx - 4, idx + 1):
            if TechnicalIndicators.is_bullish_arrangement(df, j):
                bull_count += 1
        return bull_count >= 2

    def _scan_uptrend(self, df: pd.DataFrame,
                      start_idx: int) -> Optional[Tuple[int, float]]:
        start_price = df.loc[start_idx, 'close']
        peak_idx = start_idx
        peak_price = start_price
        below_ma5_streak = 0

        max_i = len(df) - self.consolidation_days_min
        for i in range(start_idx + 1, max_i):
            current_price = df.loc[i, 'close']

            if current_price > peak_price:
                peak_price = current_price
                peak_idx = i

            if df.loc[i, 'close'] < df.loc[i, 'ma5']:
                below_ma5_streak += 1
                if below_ma5_streak >= 2 and peak_price > start_price:
                    current_gain = (peak_price - start_price) / start_price
                    if current_gain >= self.uptrend_gain_threshold:
                        uptrend_days = peak_idx - start_idx + 1
                        if uptrend_days >= self.uptrend_min_days:
                            return peak_idx, (peak_price - start_price) / start_price
            else:
                below_ma5_streak = 0

        return None

    def _scan_consolidation(self, df: pd.DataFrame,
                            start_idx: int,
                            start_price: float) -> Optional[Tuple[int, int]]:
        n = len(df)
        max_end = min(start_idx + 180, n)

        for i in range(start_idx + self.consolidation_days_min, max_end):
            days = i - start_idx
            if self._is_elevated(df, start_idx, i, start_price):
                return i, days
        return None

    def _is_elevated(self, df: pd.DataFrame,
                     start_idx: int, end_idx: int,
                     uptrend_start_price: float) -> bool:
        period_df = df.loc[start_idx:end_idx]
        min_close = period_df['close'].min()
        elevated_pct = (min_close - uptrend_start_price) / uptrend_start_price
        return elevated_pct >= self.min_elevation

    def _calculate_score(self, uptrend_start: int, uptrend_end: int,
                         consolidation_end: int, df: pd.DataFrame) -> float:
        score = 0.0
        gain = TechnicalIndicators.calculate_price_change(df, uptrend_start, uptrend_end)
        if gain >= 0.80: score += 0.4
        elif gain >= 0.40: score += 0.3
        elif gain >= 0.15: score += 0.2
        elif gain >= 0.06: score += 0.1

        start_p = df.loc[uptrend_start, 'close']
        period = df.loc[uptrend_end:consolidation_end]
        min_c = period['close'].min()
        elevation = (min_c - start_p) / start_p

        if elevation >= 0.80: score += 0.6
        elif elevation >= 0.40: score += 0.4
        elif elevation >= 0.15: score += 0.2
        elif elevation >= 0.06: score += 0.1

        return min(score, 1.0)
