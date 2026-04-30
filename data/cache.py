import os
import json
import threading
from datetime import datetime
from pathlib import Path
import pandas as pd


class DataCache:
    def __init__(self, cache_dir: str):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._meta_path = self.cache_dir / 'metadata.json'
        self._meta = self._load_meta()

    def _load_meta(self) -> dict:
        if self._meta_path.exists():
            try:
                return json.loads(self._meta_path.read_text())
            except Exception:
                return {}
        return {}

    def _save_meta(self):
        with self._lock:
            self._meta_path.write_text(json.dumps(self._meta))

    def get(self, stock_code: str, max_age_days: int = 1) -> pd.DataFrame:
        file_path = self.cache_dir / f'{stock_code}.csv'
        if not file_path.exists():
            return pd.DataFrame()

        with self._lock:
            if stock_code in self._meta:
                last_update = self._meta[stock_code].get('last_update', '')
                if last_update:
                    age = (datetime.now() - datetime.strptime(
                        last_update, '%Y-%m-%d %H:%M:%S')).days
                    if age > max_age_days:
                        return pd.DataFrame()

        try:
            df = pd.read_csv(file_path)
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
            return df
        except Exception:
            return pd.DataFrame()

    def set(self, stock_code: str, df: pd.DataFrame):
        if df.empty:
            return
        file_path = self.cache_dir / f'{stock_code}.csv'
        with self._lock:
            try:
                df.to_csv(file_path, index=False)
            except Exception:
                return
            self._meta[stock_code] = {
                'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'record_count': len(df),
                'latest_date': (df['date'].max().strftime('%Y-%m-%d')
                                if 'date' in df.columns else ''),
            }
        self._save_meta()

    def stats(self) -> dict:
        with self._lock:
            files = list(self.cache_dir.glob('*.csv'))
            total_records = sum(
                self._meta.get(f.stem, {}).get('record_count', 0)
                for f in files)
            return {
                'cache_dir': str(self.cache_dir),
                'total_stocks': len(files),
                'total_records': total_records,
            }

    def clear(self, stock_code: str = None):
        if stock_code:
            path = self.cache_dir / f'{stock_code}.csv'
            path.unlink(missing_ok=True)
            self._meta.pop(stock_code, None)
        else:
            for f in self.cache_dir.glob('*.csv'):
                f.unlink(missing_ok=True)
            self._meta.clear()
        self._save_meta()
