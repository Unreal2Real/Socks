import pandas as pd
import numpy as np
from typing import Optional, Tuple, List
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from indicators.technical import TechnicalIndicators


class PatternRecognizer:

    def __init__(self, config: dict):
        self.uptrend_gain_threshold = config.get('uptrend_gain', 0.06)
        self.consolidation_days_min = config.get('consolidation_days_min', 10)
        self.uptrend_min_days = config.get('uptrend_min_days', 5)
        self.min_elevation = config.get('min_elevation', 0.08)

    def find_pattern(self, df: pd.DataFrame,
                     max_days_back: int = None) -> Optional[dict]:

        if len(df) < 60:
            return None

        if max_days_back and len(df) > max_days_back + 60:
            df = df.tail(max_days_back + 60).reset_index(drop=True)

        df = TechnicalIndicators.calculate_all(df.ffill().bfill())
        n = len(df)

        gc_starts = self._golden_crosses(df, n)
        all_candidates = []

        for start_idx in gc_starts:
            result = self._trace_uptrend(df, start_idx, n)
            if result is None:
                continue
            peak_idx, gain = result
            ci = self._check_consolidation(df, start_idx, peak_idx, gain, n)
            if ci:
                all_candidates.append(ci)

        if not all_candidates:
            fallback = self._fallback_scan(df, n)
            all_candidates = fallback if fallback else []

        if not all_candidates:
            return None

        best = max(all_candidates, key=lambda c: c['score'])
        return {
            'uptrend_start_idx': best['si'],
            'uptrend_start_date': best['sd'],
            'uptrend_end_idx': best['pi'],
            'uptrend_end_date': best['pd'],
            'uptrend_gain': round(best['gain'], 4),
            'consolidation_start_idx': best['pi'],
            'consolidation_start_date': best['pd'],
            'consolidation_end_idx': best['ei'],
            'consolidation_end_date': best['ed'],
            'consolidation_days': best['days'],
            'pattern_score': round(best['gain'], 2),
            'type': 'factory',
        }

    def _golden_crosses(self, df: pd.DataFrame, n: int) -> List[int]:
        crosses = []
        for i in range(10, n - self.consolidation_days_min - self.uptrend_min_days):
            ma5p = float(df.loc[i-1, 'ma5']); ma10p = float(df.loc[i-1, 'ma10'])
            ma5n = float(df.loc[i, 'ma5']); ma10n = float(df.loc[i, 'ma10'])
            if ma5p <= ma10p and ma5n > ma10n:
                crosses.append(i)
        return crosses

    def _trace_uptrend(self, df: pd.DataFrame, start_idx: int, n: int) -> Optional[Tuple[int, float]]:
        sp = float(df.loc[start_idx, 'close'])
        peak_idx = start_idx
        pp = sp

        limit = n - self.consolidation_days_min
        for i in range(start_idx + 1, limit):
            cur = float(df.loc[i, 'close'])
            if cur > pp:
                pp = cur
                peak_idx = i

            if df.loc[i, 'close'] < df.loc[i, 'ma5']:
                below = 1
                for j in range(i + 1, min(i + 4, n)):
                    if df.loc[j, 'close'] < df.loc[j, 'ma5']:
                        below += 1
                    else:
                        break
                if below >= 3:
                    gain = (pp - sp) / sp
                    up_days = peak_idx - start_idx + 1
                    if gain >= self.uptrend_gain_threshold and up_days >= self.uptrend_min_days:
                        return peak_idx, gain
                    return None

        gain = (pp - sp) / sp
        up_days = peak_idx - start_idx + 1
        if gain >= self.uptrend_gain_threshold and up_days >= self.uptrend_min_days:
            return peak_idx, gain
        return None

    def _check_consolidation(self, df: pd.DataFrame, si: int, pi: int,
                             gain: float, n: int) -> Optional[dict]:
        sp = float(df.loc[si, 'close'])

        for ei in range(pi + self.consolidation_days_min, min(pi + 180, n)):
            min_c = float(df.loc[pi:ei, 'close'].min())
            if (min_c - sp) / sp >= self.min_elevation:
                age = n - 1 - ei
                recency = 1.0 / (1.0 + age / 30.0)
                return {
                    'si': si, 'pi': pi, 'ei': ei,
                    'sd': str(df.loc[si, 'date'])[:10],
                    'pd': str(df.loc[pi, 'date'])[:10],
                    'ed': str(df.loc[ei, 'date'])[:10],
                    'gain': gain, 'days': ei - pi,
                    'score': gain * recency,
                }

        og_days = n - 1 - pi
        if og_days >= self.consolidation_days_min:
            min_c = float(df.loc[pi:n-1, 'close'].min())
            if (min_c - sp) / sp >= self.min_elevation:
                return {
                    'si': si, 'pi': pi, 'ei': n - 1,
                    'sd': str(df.loc[si, 'date'])[:10],
                    'pd': str(df.loc[pi, 'date'])[:10],
                    'ed': str(df.loc[n-1, 'date'])[:10],
                    'gain': gain, 'days': og_days,
                    'score': gain * 1.0,
                }
        return None

    def _fallback_scan(self, df: pd.DataFrame, n: int) -> List[dict]:
        """If golden cross fails, scan backward from price peaks"""
        results = []
        for peak_idx in self._find_ma5_peaks(df, n):
            pp = float(df.loc[peak_idx, 'close'])
            for si in range(peak_idx - 5, max(peak_idx - 80, 10), -1):
                sp = float(df.loc[si, 'close'])
                gain = (pp - sp) / sp
                up_days = peak_idx - si + 1
                if gain < self.uptrend_gain_threshold or up_days < self.uptrend_min_days:
                    continue
                if pp < float(df.loc[si:peak_idx, 'close'].max()):
                    continue
                ci = self._check_consolidation(df, si, peak_idx, gain, n)
                if ci:
                    results.append(ci)
                    break
        return results

    def _find_ma5_peaks(self, df: pd.DataFrame, n: int) -> List[int]:
        peaks = set()
        for i in range(15, n - self.consolidation_days_min):
            if df.loc[i, 'close'] < df.loc[i, 'ma5']:
                below = 1
                for j in range(i + 1, min(i + 5, n)):
                    if df.loc[j, 'close'] < df.loc[j, 'ma5']:
                        below += 1
                    else:
                        break
                if below >= 3:
                    pk = i - 1
                    for k in range(i - 2, max(i - 10, 0), -1):
                        if df.loc[k, 'close'] > df.loc[pk, 'close']:
                            pk = k
                    peaks.add(pk)
        return sorted(peaks)
