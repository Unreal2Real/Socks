diff --git a/pattern/recognizer.py b/pattern/recognizer.py
index 4513e9b..63852ba 100644
--- a/pattern/recognizer.py
+++ b/pattern/recognizer.py
@@ -1,8 +1,7 @@
 import pandas as pd
 import numpy as np
-from typing import Optional, Tuple
-import sys
-import os
+from typing import Optional, Tuple, List
+import sys, os
 
 sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
 from indicators.technical import TechnicalIndicators
@@ -11,10 +10,10 @@ from indicators.technical import TechnicalIndicators
 class PatternRecognizer:
 
     def __init__(self, config: dict):
-        self.uptrend_gain_threshold = config.get('uptrend_gain', 0.15)
+        self.uptrend_gain_threshold = config.get('uptrend_gain', 0.06)
         self.consolidation_days_min = config.get('consolidation_days_min', 10)
         self.uptrend_min_days = config.get('uptrend_min_days', 5)
-        self.min_elevation = config.get('min_elevation', 0.10)
+        self.min_elevation = config.get('min_elevation', 0.08)
 
     def find_pattern(self, df: pd.DataFrame,
                      max_days_back: int = None) -> Optional[dict]:
@@ -26,125 +25,158 @@ class PatternRecognizer:
             df = df.tail(max_days_back + 60).reset_index(drop=True)
 
         df = TechnicalIndicators.calculate_all(df.ffill().bfill())
-
         n = len(df)
-        start = n - self.consolidation_days_min - 1
-        end = 20
 
-        for i in range(start, end, -1):
-            if not self._is_uptrend_start(df, i):
+        gc_starts = self._golden_crosses(df, n)
+        gc_candidates = []
+        for start_idx in gc_starts:
+            result = self._trace_uptrend(df, start_idx, n)
+            if result is None:
                 continue
+            peak_idx, gain = result
+            ci = self._check_consolidation(df, start_idx, peak_idx, gain, n)
+            if ci:
+                gc_candidates.append(ci)
 
-            uptrend_result = self._scan_uptrend(df, i)
-            if not uptrend_result:
-                continue
+        fb_candidates = self._fallback_scan(df, n)
 
-            uptrend_end_idx, uptrend_gain = uptrend_result
-            start_price = df.loc[i, 'close']
-
-            last_idx = n - 1
-            ongoing_days = last_idx - uptrend_end_idx
-            if ongoing_days >= self.consolidation_days_min and \
-               self._is_elevated(df, uptrend_end_idx, last_idx, start_price):
-                consolidation_end_idx = last_idx
-                consolidation_days = ongoing_days
-            else:
-                consol = self._scan_consolidation(df, uptrend_end_idx, start_price)
-                if consol:
-                    consolidation_end_idx, consolidation_days = consol
-                else:
-                    continue
+        all_raw = gc_candidates + (fb_candidates if fb_candidates else [])
+        if not all_raw:
+            return None
 
-            return {
-                'uptrend_start_idx': i,
-                'uptrend_start_date': str(df.loc[i, 'date'])[:10],
-                'uptrend_end_idx': uptrend_end_idx,
-                'uptrend_end_date': str(df.loc[uptrend_end_idx, 'date'])[:10],
-                'uptrend_gain': round(uptrend_gain, 4),
-                'consolidation_start_idx': uptrend_end_idx,
-                'consolidation_start_date': str(df.loc[uptrend_end_idx, 'date'])[:10],
-                'consolidation_end_idx': consolidation_end_idx,
-                'consolidation_end_date': str(df.loc[consolidation_end_idx, 'date'])[:10],
-                'consolidation_days': consolidation_days,
-                'pattern_score': self._calculate_score(i, uptrend_end_idx,
-                                                       consolidation_end_idx, df),
-                'type': 'factory',
-            }
+        best_by_peak = {}
+        for c in all_raw:
+            pi = c['pi']
+            if pi not in best_by_peak or c['si'] > best_by_peak[pi]['si']:
+                best_by_peak[pi] = c
 
-        return None
+        all_candidates = list(best_by_peak.values())
 
-    def _is_uptrend_start(self, df: pd.DataFrame, idx: int) -> bool:
-        bull_count = 0
-        for j in range(idx - 4, idx + 1):
-            if TechnicalIndicators.is_bullish_arrangement(df, j):
-                bull_count += 1
-        return bull_count >= 2
+        if not all_candidates:
+            return None
 
-    def _scan_uptrend(self, df: pd.DataFrame,
-                      start_idx: int) -> Optional[Tuple[int, float]]:
-        start_price = df.loc[start_idx, 'close']
+        best = max(all_candidates, key=lambda c: c['score'])
+        return {
+            'uptrend_start_idx': best['si'],
+            'uptrend_start_date': best['sd'],
+            'uptrend_end_idx': best['pi'],
+            'uptrend_end_date': best['pd'],
+            'uptrend_gain': round(best['gain'], 4),
+            'consolidation_start_idx': best['pi'],
+            'consolidation_start_date': best['pd'],
+            'consolidation_end_idx': best['ei'],
+            'consolidation_end_date': best['ed'],
+            'consolidation_days': best['days'],
+            'pattern_score': round(best['gain'], 2),
+            'type': 'factory',
+        }
+
+    def _golden_crosses(self, df: pd.DataFrame, n: int) -> List[int]:
+        crosses = []
+        for i in range(10, n - self.consolidation_days_min - self.uptrend_min_days):
+            ma5p = float(df.loc[i-1, 'ma5']); ma10p = float(df.loc[i-1, 'ma10'])
+            ma5n = float(df.loc[i, 'ma5']); ma10n = float(df.loc[i, 'ma10'])
+            if ma5p <= ma10p and ma5n > ma10n:
+                crosses.append(i)
+        return crosses
+
+    def _trace_uptrend(self, df: pd.DataFrame, start_idx: int, n: int) -> Optional[Tuple[int, float]]:
+        sp = float(df.loc[start_idx, 'close'])
         peak_idx = start_idx
-        peak_price = start_price
-        below_ma5_streak = 0
-
-        max_i = len(df) - self.consolidation_days_min
-        for i in range(start_idx + 1, max_i):
-            current_price = df.loc[i, 'close']
+        pp = sp
 
-            if current_price > peak_price:
-                peak_price = current_price
+        limit = n - self.consolidation_days_min
+        for i in range(start_idx + 1, limit):
+            cur = float(df.loc[i, 'close'])
+            if cur > pp:
+                pp = cur
                 peak_idx = i
 
             if df.loc[i, 'close'] < df.loc[i, 'ma5']:
-                below_ma5_streak += 1
-                if below_ma5_streak >= 2 and peak_price > start_price:
-                    current_gain = (peak_price - start_price) / start_price
-                    if current_gain >= self.uptrend_gain_threshold:
-                        uptrend_days = peak_idx - start_idx + 1
-                        if uptrend_days >= self.uptrend_min_days:
-                            return peak_idx, (peak_price - start_price) / start_price
-            else:
-                below_ma5_streak = 0
-
+                below = 1
+                for j in range(i + 1, min(i + 4, n)):
+                    if df.loc[j, 'close'] < df.loc[j, 'ma5']:
+                        below += 1
+                    else:
+                        break
+                if below >= 3:
+                    gain = (pp - sp) / sp
+                    up_days = peak_idx - start_idx + 1
+                    if gain >= self.uptrend_gain_threshold and up_days >= self.uptrend_min_days:
+                        return peak_idx, gain
+                    return None
+
+        gain = (pp - sp) / sp
+        up_days = peak_idx - start_idx + 1
+        if gain >= self.uptrend_gain_threshold and up_days >= self.uptrend_min_days:
+            return peak_idx, gain
         return None
 
-    def _scan_consolidation(self, df: pd.DataFrame,
-                            start_idx: int,
-                            start_price: float) -> Optional[Tuple[int, int]]:
-        n = len(df)
-        max_end = min(start_idx + 180, n)
-
-        for i in range(start_idx + self.consolidation_days_min, max_end):
-            days = i - start_idx
-            if self._is_elevated(df, start_idx, i, start_price):
-                return i, days
+    def _check_consolidation(self, df: pd.DataFrame, si: int, pi: int,
+                             gain: float, n: int) -> Optional[dict]:
+        sp = float(df.loc[si, 'close'])
+
+        for ei in range(pi + self.consolidation_days_min, min(pi + 180, n)):
+            min_c = float(df.loc[pi:ei, 'close'].min())
+            if (min_c - sp) / sp >= self.min_elevation:
+                age = n - 1 - ei
+                recency = 1.0 / (1.0 + age / 30.0)
+                return {
+                    'si': si, 'pi': pi, 'ei': ei,
+                    'sd': str(df.loc[si, 'date'])[:10],
+                    'pd': str(df.loc[pi, 'date'])[:10],
+                    'ed': str(df.loc[ei, 'date'])[:10],
+                    'gain': gain, 'days': ei - pi,
+                    'score': gain * recency,
+                }
+
+        og_days = n - 1 - pi
+        if og_days >= self.consolidation_days_min:
+            min_c = float(df.loc[pi:n-1, 'close'].min())
+            if (min_c - sp) / sp >= self.min_elevation:
+                return {
+                    'si': si, 'pi': pi, 'ei': n - 1,
+                    'sd': str(df.loc[si, 'date'])[:10],
+                    'pd': str(df.loc[pi, 'date'])[:10],
+                    'ed': str(df.loc[n-1, 'date'])[:10],
+                    'gain': gain, 'days': og_days,
+                    'score': gain * 1.0,
+                }
         return None
 
-    def _is_elevated(self, df: pd.DataFrame,
-                     start_idx: int, end_idx: int,
-                     uptrend_start_price: float) -> bool:
-        period_df = df.loc[start_idx:end_idx]
-        min_close = period_df['close'].min()
-        elevated_pct = (min_close - uptrend_start_price) / uptrend_start_price
-        return elevated_pct >= self.min_elevation
-
-    def _calculate_score(self, uptrend_start: int, uptrend_end: int,
-                         consolidation_end: int, df: pd.DataFrame) -> float:
-        score = 0.0
-        gain = TechnicalIndicators.calculate_price_change(df, uptrend_start, uptrend_end)
-        if gain >= 0.80: score += 0.4
-        elif gain >= 0.40: score += 0.3
-        elif gain >= 0.15: score += 0.2
-        elif gain >= 0.06: score += 0.1
-
-        start_p = df.loc[uptrend_start, 'close']
-        period = df.loc[uptrend_end:consolidation_end]
-        min_c = period['close'].min()
-        elevation = (min_c - start_p) / start_p
-
-        if elevation >= 0.80: score += 0.6
-        elif elevation >= 0.40: score += 0.4
-        elif elevation >= 0.15: score += 0.2
-        elif elevation >= 0.06: score += 0.1
-
-        return min(score, 1.0)
+    def _fallback_scan(self, df: pd.DataFrame, n: int) -> List[dict]:
+        """If golden cross fails, scan backward from price peaks"""
+        results = []
+        for peak_idx in self._find_ma5_peaks(df, n):
+            pp = float(df.loc[peak_idx, 'close'])
+            for si in range(peak_idx - 5, max(peak_idx - 80, 10), -1):
+                sp = float(df.loc[si, 'close'])
+                gain = (pp - sp) / sp
+                up_days = peak_idx - si + 1
+                if gain < self.uptrend_gain_threshold or up_days < self.uptrend_min_days:
+                    continue
+                if pp < float(df.loc[si:peak_idx, 'close'].max()):
+                    continue
+                ci = self._check_consolidation(df, si, peak_idx, gain, n)
+                if ci:
+                    results.append(ci)
+                    break
+        return results
+
+    def _find_ma5_peaks(self, df: pd.DataFrame, n: int) -> List[int]:
+        peaks = set()
+        for i in range(15, n - self.consolidation_days_min):
+            if df.loc[i, 'close'] < df.loc[i, 'ma5']:
+                below = 1
+                for j in range(i + 1, min(i + 5, n)):
+                    if df.loc[j, 'close'] < df.loc[j, 'ma5']:
+                        below += 1
+                    else:
+                        break
+                if below >= 3:
+                    pk = i - 1
+                    for k in range(i - 2, max(i - 10, 0), -1):
+                        if df.loc[k, 'close'] > df.loc[pk, 'close']:
+                            pk = k
+                    peaks.add(pk)
+        return sorted(peaks)
