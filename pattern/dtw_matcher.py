import json
import os
import numpy as np
from typing import List, Dict, Optional, Tuple
from dtaidistance import dtw


class DTWMatcher:
    def __init__(self, templates_root: str = 'templates'):
        self.templates_root = templates_root
        self._libraries: Dict[str, List[dict]] = {}

    def load_library(self, category: str) -> int:
        lib_dir = os.path.join(self.templates_root, category)
        if not os.path.isdir(lib_dir):
            return 0

        templates = []
        for fname in sorted(os.listdir(lib_dir)):
            if not fname.endswith('.json'):
                continue
            path = os.path.join(lib_dir, fname)
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            templates.append({
                'stock_code': data['stock_code'],
                'stock_name': data.get('stock_name', ''),
                'series': np.array(data['series'], dtype=np.float64),
                'start_date': data['start_date'],
                'end_date': data['end_date'],
                'days': data['days'],
            })

        self._libraries[category] = templates
        return len(templates)

    def match(self, candidate: np.ndarray, category: str) -> Optional[dict]:
        templates = self._libraries.get(category)
        if not templates:
            return None

        if len(candidate) < 5:
            return None

        best_distance = float('inf')
        best_template = None

        for tpl in templates:
            t_raw = tpl['series']
            c_raw = self._resample(candidate, len(t_raw))
            t_norm = self._normalize(t_raw)
            c_norm = self._normalize(c_raw)
            distance = dtw.distance_fast(c_norm, t_norm, window=max(3, int(min(len(c_norm), len(t_norm)) * 0.2)))
            if distance < best_distance:
                best_distance = distance
                best_template = tpl

        max_len = max(len(candidate), len(best_template['series']))
        similarity = round(float(1.0 / (1.0 + best_distance / max_len)), 4)

        return {
            'category': category,
            'best_match': best_template['stock_code'],
            'best_name': best_template['stock_name'],
            'dtw_distance': round(float(best_distance), 4),
            'dtw_similarity': similarity,
        }

    @staticmethod
    def _resample(arr: np.ndarray, target_len: int) -> np.ndarray:
        if len(arr) == target_len:
            return arr
        indices = np.linspace(0, len(arr) - 1, target_len)
        return np.interp(indices, np.arange(len(arr)), arr)

    def match_all(self, candidate: np.ndarray,
                  categories: Optional[List[str]] = None) -> List[dict]:
        if categories is None:
            categories = list(self._libraries.keys())

        results = []
        for cat in categories:
            result = self.match(candidate, cat)
            if result:
                results.append(result)

        results.sort(key=lambda x: x['dtw_similarity'], reverse=True)
        return results

    @staticmethod
    def _normalize(arr: np.ndarray) -> np.ndarray:
        min_v = arr.min()
        max_v = arr.max()
        if max_v - min_v < 1e-10:
            return np.zeros_like(arr)
        return (arr - min_v) / (max_v - min_v)

    @property
    def categories(self) -> List[str]:
        return list(self._libraries.keys())


_matcher_instance: Optional[DTWMatcher] = None


def get_matcher(templates_root: str = 'templates',
                auto_load: Optional[List[str]] = None) -> DTWMatcher:
    global _matcher_instance
    if _matcher_instance is None:
        _matcher_instance = DTWMatcher(templates_root)
        if auto_load is None:
            auto_load = ['factory']
        for cat in auto_load:
            n = _matcher_instance.load_library(cat)
            if n > 0:
                print(f"[DTW] loaded {n} templates from '{cat}'")
    return _matcher_instance
