import os
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
import json


class DataCache:
    def __init__(self, cache_dir: str = None):
        if cache_dir is None:
            cache_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'cache')
        self.cache_dir = cache_dir
        self.meta_file = os.path.join(self.cache_dir, 'metadata.json')
        os.makedirs(self.cache_dir, exist_ok=True)
        self._metadata = self._load_metadata()

    def _load_metadata(self) -> dict:
        if os.path.exists(self.meta_file):
            try:
                with open(self.meta_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_metadata(self):
        try:
            with open(self.meta_file, 'w', encoding='utf-8') as f:
                json.dump(self._metadata, f, ensure_ascii=False, indent=2, default=str)
        except Exception:
            pass

    def get_cache_path(self, stock_code: str) -> str:
        return os.path.join(self.cache_dir, f'{stock_code}.csv')

    def get(self, stock_code: str, max_age_days: int = 1) -> Optional[pd.DataFrame]:
        cache_path = self.get_cache_path(stock_code)

        if not os.path.exists(cache_path):
            return None

        meta = self._metadata.get(stock_code)
        if meta is None:
            return None

        last_update_str = meta.get('last_update')
        if last_update_str:
            last_update = pd.to_datetime(last_update_str)
            if (datetime.now() - last_update).days > max_age_days:
                return None

        try:
            df = pd.read_csv(cache_path, parse_dates=['date'])
            return df
        except Exception:
            return None

    def set(self, stock_code: str, df: pd.DataFrame):
        if df is None or df.empty:
            return

        cache_path = self.get_cache_path(stock_code)
        df = df.copy()
        if 'date' in df.columns:
            df = df.sort_values('date').reset_index(drop=True)
            latest_date = df['date'].max()
        else:
            latest_date = None

        try:
            df.to_csv(cache_path, index=False, encoding='utf-8')

            self._metadata[stock_code] = {
                'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'record_count': len(df),
                'latest_date': latest_date.strftime('%Y-%m-%d') if latest_date else None
            }
            self._save_metadata()
        except Exception:
            pass

    def get_latest_date(self, stock_code: str) -> Optional[str]:
        meta = self._metadata.get(stock_code)
        if meta is None:
            return None
        return meta.get('latest_date')

    def clear(self, stock_code: str = None):
        if stock_code is None:
            for f in os.listdir(self.cache_dir):
                if f.endswith('.csv'):
                    os.remove(os.path.join(self.cache_dir, f))
            self._metadata = {}
            self._save_metadata()
        else:
            cache_path = self.get_cache_path(stock_code)
            if os.path.exists(cache_path):
                os.remove(cache_path)
            if stock_code in self._metadata:
                del self._metadata[stock_code]
                self._save_metadata()

    def get_stats(self) -> dict:
        total = len(self._metadata)
        total_records = sum(m.get('record_count', 0) for m in self._metadata.values())
        return {
            'total_stocks': total,
            'total_records': int(total_records),
            'cache_dir': self.cache_dir
        }