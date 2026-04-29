import pandas as pd
import numpy as np
from typing import Optional, Tuple
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from indicators.technical import TechnicalIndicators


class FactoryPatternRecognizer:
    def __init__(self, config: dict):
        self.uptrend_gain_threshold = config.get('uptrend_gain', 0.20)
        self.consolidation_days_min = config.get('consolidation_days_min', 10)
        self.consolidation_days_max = config.get('consolidation_days_max', 20)
        self.bandwidth_threshold = config.get('bandwidth', 0.15)
        self.volatility_threshold = config.get('volatility', 0.15)
        self.volume_ratio_threshold = config.get('volume_ratio', 0.5)
        self.uptrend_min_days = config.get('uptrend_min_days', 5)

    def find_pattern(self, df: pd.DataFrame) -> Optional[dict]:
        if len(df) < 60:
            return None

        df = TechnicalIndicators.calculate_all(df)

        for i in range(20, len(df) - self.consolidation_days_max):
            if self._is_uptrend_start(df, i):
                uptrend_result = self._scan_uptrend(df, i)
                if uptrend_result:
                    uptrend_end_idx, uptrend_gain = uptrend_result

                    consolidation_result = self._scan_consolidation(df, uptrend_end_idx)
                    if consolidation_result:
                        consolidation_end_idx, consolidation_days = consolidation_result

                        return {
                            'uptrend_start_idx': i,
                            'uptrend_start_date': df.loc[i, 'date'],
                            'uptrend_end_idx': uptrend_end_idx,
                            'uptrend_end_date': df.loc[uptrend_end_idx, 'date'],
                            'uptrend_gain': uptrend_gain,
                            'consolidation_start_idx': uptrend_end_idx,
                            'consolidation_start_date': df.loc[uptrend_end_idx, 'date'],
                            'consolidation_end_idx': consolidation_end_idx,
                            'consolidation_end_date': df.loc[consolidation_end_idx, 'date'],
                            'consolidation_days': consolidation_days,
                            'pattern_score': self._calculate_pattern_score(df, i, uptrend_end_idx, consolidation_end_idx)
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

    def classify_pattern_proximity(self, df: pd.DataFrame) -> dict:
        """
        判断股票离"厂"字形态有多近，用于确定观察状态。
        返回: {'status': 'no_pattern'|'watching_uptrend'|'watching_consolidation',
               'score': float, 'notes': str}
        """
        if len(df) < 60:
            return {'status': 'no_pattern', 'score': 0, 'notes': '数据不足'}

        df = TechnicalIndicators.calculate_all(df)

        best_uptrend = None
        best_gain = 0

        for i in range(20, len(df) - 10):
            if not self._is_uptrend_start(df, i):
                continue
            start_price = df.loc[i, 'close']
            peak_idx = i
            peak_price = start_price

            for j in range(i + 1, len(df)):
                if not TechnicalIndicators.is_bullish_arrangement(df, j):
                    break
                cur = df.loc[j, 'close']
                if cur > peak_price:
                    peak_price = cur
                    peak_idx = j

            gain = (peak_price - start_price) / start_price
            if gain > best_gain:
                best_gain = gain
                best_uptrend = {
                    'start_idx': i,
                    'peak_idx': peak_idx,
                    'peak_price': peak_price,
                    'start_price': start_price,
                    'gain': gain,
                }

        if best_uptrend is None:
            return {'status': 'no_pattern', 'score': 0, 'notes': '无明显上涨段'}

        peak_idx = best_uptrend['peak_idx']
        gain = best_uptrend['gain']
        consolidation_days = len(df) - peak_idx - 1

        if gain >= self.uptrend_gain_threshold * 0.8 and consolidation_days >= 3:
            consol_df = df.loc[peak_idx:]
            avg_bw = consol_df['bb_bandwidth'].mean() if 'bb_bandwidth' in consol_df.columns else 999
            vol = TechnicalIndicators.calculate_volatility(df, peak_idx, len(df) - 1)
            avg_vr = consol_df['volume_ratio'].mean() if 'volume_ratio' in consol_df.columns else 999

            near_score = 0
            notes_parts = []

            if gain >= self.uptrend_gain_threshold:
                near_score += 0.4
                notes_parts.append(f'涨幅满足({gain:.1%})')
            else:
                near_score += 0.2
                notes_parts.append(f'涨幅不足({gain:.1%}<{self.uptrend_gain_threshold:.0%})')

            if consolidation_days >= self.consolidation_days_min:
                near_score += 0.3
                notes_parts.append(f'盘整{consolidation_days}天')
            else:
                near_score += 0.1
                notes_parts.append(f'盘整仅{consolidation_days}天')

            if avg_bw < self.bandwidth_threshold * 1.2:
                near_score += 0.15
            if vol < self.volatility_threshold * 1.2:
                near_score += 0.1
            if avg_vr < self.volume_ratio_threshold * 1.2:
                near_score += 0.05

            score_ratio = near_score / 1.0

            if near_score >= 0.6:
                return {
                    'status': 'watching_consolidation',
                    'score': round(score_ratio, 2),
                    'notes': ' | '.join(notes_parts),
                    'gain': round(gain, 4),
                    'consolidation_days': consolidation_days,
                }
            return {
                'status': 'watching_uptrend',
                'score': round(score_ratio, 2),
                'notes': ' | '.join(notes_parts),
                'gain': round(gain, 4),
                'consolidation_days': consolidation_days,
            }

        if gain >= self.uptrend_gain_threshold * 0.5:
            return {
                'status': 'watching_uptrend',
                'score': round(gain / self.uptrend_gain_threshold, 2),
                'notes': f'上涨中({gain:.1%})',
                'gain': round(gain, 4),
                'consolidation_days': 0,
            }

        return {'status': 'no_pattern', 'score': 0, 'notes': '无明显形态'}

    def _calculate_pattern_score(self, df: pd.DataFrame, uptrend_start: int,
                                  uptrend_end: int, consolidation_end: int) -> float:
        score = 0.0

        uptrend_gain = TechnicalIndicators.calculate_price_change(df, uptrend_start, uptrend_end)
        if uptrend_gain >= 0.20:
            score += 0.3
        elif uptrend_gain >= 0.15:
            score += 0.2

        consolidation_volatility = TechnicalIndicators.calculate_volatility(df, uptrend_end, consolidation_end)
        if consolidation_volatility <= 0.10:
            score += 0.3
        elif consolidation_volatility <= 0.15:
            score += 0.2

        consolidation_df = df.loc[uptrend_end:consolidation_end]
        if 'bb_bandwidth' in consolidation_df.columns:
            avg_bandwidth = consolidation_df['bb_bandwidth'].mean()
            if avg_bandwidth <= 0.10:
                score += 0.2
            elif avg_bandwidth <= 0.15:
                score += 0.1

        if 'volume_ratio' in consolidation_df.columns:
            avg_volume_ratio = consolidation_df['volume_ratio'].mean()
            if avg_volume_ratio <= 0.4:
                score += 0.2
            elif avg_volume_ratio <= 0.5:
                score += 0.1

        return min(score, 1.0)
