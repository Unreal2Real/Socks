import pandas as pd
import numpy as np
from typing import Optional, Tuple, List
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

        # Run all three scanners concurrently, pick the best result based on pattern_score
        results = []
        for weight, scanner in [(1.0, self._scan_backward), (0.95, self._fallback_scan), (0.9, self._price_peak_fallback)]:
            res = scanner(df, n)
            if res is not None:
                res['pattern_score'] = res['pattern_score'] * weight
                results.append(res)

        if not results:
            return None

        best = max(results, key=lambda r: r['pattern_score'])
        return best

    def _scan_backward(self, df: pd.DataFrame, n: int) -> Optional[dict]:
        start_i = n - self.consolidation_days_min - 1
        best = None
        best_score = -1

        for i in range(start_i, 20, -1):
            uptrend = self._scan_uptrend(df, i, n, ma5_threshold=5)
            if not uptrend:
                uptrend = self._scan_uptrend(df, i, n, ma5_threshold=3)
            if not uptrend:
                continue

            peak_idx, gain = uptrend
            start_price = df.loc[i, 'close']
            efficiency = gain / max(peak_idx - i + 1, 1)

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

    def _fallback_scan(self, df: pd.DataFrame, n: int) -> Optional[dict]:
        peaks = self._find_ma5_peaks(df, n)
        if not peaks:
            return None

        best = None
        best_score = -1

        for peak_idx in peaks:
            pp = float(df.loc[peak_idx, 'close'])
            lookback = min(peak_idx - 5, 80)

            for si in range(peak_idx - 5, peak_idx - lookback, -1):
                if si < 10:
                    continue
                sp = float(df.loc[si, 'close'])
                gain = (pp - sp) / sp
                up_days = peak_idx - si + 1
                if gain < self.uptrend_gain_threshold or up_days < self.uptrend_min_days:
                    continue
                if pp < float(df.loc[si:peak_idx, 'close'].max()):
                    continue

                consol = self._scan_consolidation(df, peak_idx, sp)
                if consol:
                    ei, days = consol
                    efficiency = gain / max(up_days, 1)
                    if efficiency > best_score:
                        best_score = efficiency
                        best = (si, peak_idx, gain, ei, days)
                    break

                og_days = n - 1 - peak_idx
                if og_days >= self.consolidation_days_min:
                    min_c = float(df.loc[peak_idx:n-1, 'close'].min())
                    if (min_c - sp) / sp >= self.min_elevation:
                        efficiency = gain / max(up_days, 1)
                        if efficiency > best_score:
                            best_score = efficiency
                            best = (si, peak_idx, gain, n - 1, og_days)
                        break

        if best:
            si, pi, g, ei, d = best
            return self._build_result(df, si, pi, g, ei, d)
        return None

    def _find_ma5_peaks(self, df: pd.DataFrame, n: int) -> List[int]:
        peaks = []
        for i in range(15, n - self.consolidation_days_min):
            if df.loc[i, 'close'] < df.loc[i, 'ma5']:
                below = 1
                j = i + 1
                while j < min(i + 5, n) and df.loc[j, 'close'] < df.loc[j, 'ma5']:
                    below += 1
                    j += 1
                if below >= 3:
                    start_peak = i - 1
                    actual_peak = start_peak
                    for k in range(start_peak - 1, max(start_peak - 10, 0), -1):
                        if df.loc[k, 'close'] > df.loc[actual_peak, 'close']:
                            actual_peak = k
                    peaks.append(actual_peak)
        return list(sorted(set(peaks)))

    def _scan_uptrend(self, df: pd.DataFrame, start_idx: int,
                      n: int, ma5_threshold: int = 3) -> Optional[Tuple[int, float]]:
        start_price = df.loc[start_idx, 'close']
        peak_idx = start_idx
        peak_price = start_price
        below_ma5 = 0
        max_i = n - self.consolidation_days_min

        for i in range(start_idx + 1, max_i):
            cur = df.loc[i, 'close']
            if cur > peak_price:
                peak_price = cur
                peak_idx = i

            if df.loc[i, 'close'] < df.loc[i, 'ma5']:
                below_ma5 += 1
                if below_ma5 >= ma5_threshold and peak_price > start_price:
                    gain = (peak_price - start_price) / start_price
                    up_days = peak_idx - start_idx + 1
                    if gain >= self.uptrend_gain_threshold and up_days >= self.uptrend_min_days:
                        return peak_idx, gain
                    return None
            else:
                below_ma5 = 0

        return None

    def _scan_consolidation(self, df: pd.DataFrame, start_idx: int,
                            start_price: float) -> Optional[Tuple[int, int]]:
        n = len(df)
        best_i = None
        best_days = 0
        for i in range(start_idx + self.consolidation_days_min, min(start_idx + 180, n)):
            min_c = df.loc[start_idx:i, 'close'].min()
            if (min_c - start_price) / start_price >= self.min_elevation:
                days = i - start_idx
                if days > best_days:
                    best_days = days
                    best_i = i
        if best_i is not None:
            return best_i, best_days
        return None

    def _price_peak_fallback(self, df: pd.DataFrame, n: int) -> Optional[dict]:
        w = 10
        peaks = []
        for i in range(w, n - self.consolidation_days_min - w):
            cur = float(df.loc[i, 'close'])
            if cur > float(df.loc[i-w:i-1, 'close'].max()) and \
               cur > float(df.loc[i+1:i+w, 'close'].max()):
                peaks.append(i)

        best = None
        best_eff = -1

        for pi in peaks:
            pp = float(df.loc[pi, 'close'])
            lookback = min(pi - 5, 80)
            for si in range(pi - 5, pi - lookback, -1):
                if si < 10:
                    continue
                sp = float(df.loc[si, 'close'])
                gain = (pp - sp) / sp
                up_days = pi - si + 1
                if gain < self.uptrend_gain_threshold or up_days < self.uptrend_min_days:
                    continue
                if pp < float(df.loc[si:pi, 'close'].max()):
                    continue

                consol = self._scan_consolidation(df, pi, sp)
                if consol:
                    ei, days = consol
                    efficiency = gain / max(up_days, 1)
                    if efficiency > best_eff:
                        best_eff = efficiency
                        best = (si, pi, gain, ei, days)
                    break

                og_days = n - 1 - pi
                if og_days >= self.consolidation_days_min:
                    min_c = float(df.loc[pi:n-1, 'close'].min())
                    if (min_c - sp) / sp >= self.min_elevation:
                        efficiency = gain / max(up_days, 1)
                        if efficiency > best_eff:
                            best_eff = efficiency
                            best = (si, pi, gain, n - 1, og_days)
                        break

        if best:
            si, pi, g, ei, d = best
            return self._build_result(df, si, pi, g, ei, d)
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
