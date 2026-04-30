import pandas as pd
import numpy as np
from typing import Optional, Tuple
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from indicators.technical import TechnicalIndicators


class PatternRecognizer:

    def __init__(self, config: dict):
        self.uptrend_gain_threshold = config.get('uptrend_gain', 0.20)
        self.consolidation_days_min = config.get('consolidation_days_min', 10)
        self.consolidation_days_max = config.get('consolidation_days_max', 20)
        self.bandwidth_threshold = config.get('bandwidth', 0.15)
        self.volatility_threshold = config.get('volatility', 0.15)
        self.volume_ratio_threshold = config.get('volume_ratio', 0.5)
        self.uptrend_min_days = config.get('uptrend_min_days', 5)

    def find_pattern(self, df: pd.DataFrame,
                     max_days_back: int = None) -> Optional[dict]:

        if len(df) < 60:
            return None

        if max_days_back and len(df) > max_days_back + 60:
            df = df.tail(max_days_back + 60).reset_index(drop=True)

        df = TechnicalIndicators.calculate_all(df.ffill().bfill())

        n = len(df)
        start = n - self.consolidation_days_max - 1
        end = 20

        for i in range(start, end, -1):
            if self._is_uptrend_start(df, i):
                uptrend_result = self._scan_uptrend(df, i)
                if uptrend_result:
                    uptrend_end_idx, uptrend_gain = uptrend_result
                    consolidation_result = self._scan_consolidation(df, uptrend_end_idx)
                    if consolidation_result:
                        consolidation_end_idx, consolidation_days = consolidation_result
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
                            'pattern_score': self._calculate_pattern_score(df, i, uptrend_end_idx, consolidation_end_idx),
                            'type': 'factory',
                        }

        return None

    def _is_uptrend_start(self, df: pd.DataFrame, idx: int) -> bool:
        if not TechnicalIndicators.is_bullish_arrangement(df, idx):
            return False
        for j in range(idx - 4, idx + 1):
            if not TechnicalIndicators.is_bullish_arrangement(df, j):
                return False
        return True

    def _scan_uptrend(self, df: pd.DataFrame, start_idx: int) -> Optional[Tuple[int, float]]:
        start_price = df.loc[start_idx, 'close']
        peak_idx = start_idx
        peak_price = start_price

        for i in range(start_idx + 1, len(df) - self.consolidation_days_min):
            if not TechnicalIndicators.is_bullish_arrangement(df, i):
                break

            current_price = df.loc[i, 'close']
            if current_price > peak_price:
                peak_price = current_price
                peak_idx = i

            current_gain = (current_price - start_price) / start_price
            if current_gain >= self.uptrend_gain_threshold:
                for j in range(i + 1, min(i + 5, len(df))):
                    if df.loc[j, 'close'] < df.loc[j, 'ma5']:
                        return peak_idx, (peak_price - start_price) / start_price

        return None

    def _scan_consolidation(self, df: pd.DataFrame, start_idx: int) -> Optional[Tuple[int, int]]:
        for i in range(start_idx + 1, min(start_idx + self.consolidation_days_max + 1, len(df))):
            days = i - start_idx
            if days < self.consolidation_days_min:
                continue
            if self._is_valid_consolidation(df, start_idx, i):
                return i, days
        return None

    def _is_valid_consolidation(self, df: pd.DataFrame, start_idx: int, end_idx: int) -> bool:
        period_df = df.loc[start_idx:end_idx]

        if 'bb_bandwidth' not in period_df.columns:
            return False

        avg_bandwidth = period_df['bb_bandwidth'].mean()
        if avg_bandwidth >= self.bandwidth_threshold:
            return False

        volatility = TechnicalIndicators.calculate_volatility(df, start_idx, end_idx)
        if volatility >= self.volatility_threshold:
            return False

        avg_volume_ratio = period_df['volume_ratio'].mean()
        if avg_volume_ratio >= self.volume_ratio_threshold:
            return False

        return True

    def _calculate_pattern_score(self, df: pd.DataFrame, uptrend_start: int,
                                  uptrend_end: int, consolidation_end: int) -> float:
        score = 0.0

        gain = TechnicalIndicators.calculate_price_change(df, uptrend_start, uptrend_end)
        if gain >= 0.20:
            score += 0.3
        elif gain >= 0.15:
            score += 0.2

        vol = TechnicalIndicators.calculate_volatility(df, uptrend_end, consolidation_end)
        if vol <= 0.10:
            score += 0.3
        elif vol <= 0.15:
            score += 0.2

        consol_df = df.loc[uptrend_end:consolidation_end]
        if 'bb_bandwidth' in consol_df.columns:
            avg_bw = consol_df['bb_bandwidth'].mean()
            if avg_bw <= 0.10:
                score += 0.2
            elif avg_bw <= 0.15:
                score += 0.1

        if 'volume_ratio' in consol_df.columns:
            avg_vr = consol_df['volume_ratio'].mean()
            if avg_vr <= 0.4:
                score += 0.2
            elif avg_vr <= 0.5:
                score += 0.1

        return min(score, 1.0)
