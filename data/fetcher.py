import json
import signal
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

from _config import TDX_PATH, CACHE_DIR, INDEX_KEYWORDS
from data.cache import DataCache


def _with_timeout(func, timeout=10):
    """在子线程中执行函数，主线程等待超时后返回默认值"""
    result = []
    exception = []
    def target():
        try:
            result.append(func())
        except Exception as e:
            exception.append(e)
    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        return []
    if exception:
        return []
    return result[0] if result else []


class DataFetcher:
    def __init__(self):
        self._cache = DataCache(CACHE_DIR)
        self._tdx_reader = None
        self._bs = None
        self._bs_logged_in = False
        self._lock = threading.Lock()
        self._stock_list_cache = None

    def _init_tdx(self):
        if self._tdx_reader is None:
            try:
                from mootdx.reader import Reader
                self._tdx_reader = Reader.factory(
                    market='std', tdxdir=TDX_PATH)
            except Exception:
                self._tdx_reader = None

    def _init_bs(self):
        if not self._bs_logged_in:
            try:
                import baostock as bs
                self._bs = bs
                lg = bs.login()
                self._bs_logged_in = (lg.error_code == '0')
            except Exception:
                self._bs = None
                self._bs_logged_in = False

    def _from_tdx(self, code: str) -> pd.DataFrame:
        self._init_tdx()
        if self._tdx_reader is None:
            return pd.DataFrame()
        try:
            df = self._tdx_reader.daily(symbol=code)
            if df is not None and not df.empty:
                if df.index.name == 'date' or not pd.api.types.is_datetime64_any_dtype(df.index):
                    df = df.reset_index()
                if 'date' not in df.columns:
                    for col in df.columns:
                        if 'date' in str(col).lower() or 'time' in str(col).lower():
                            df.rename(columns={col: 'date'}, inplace=True)
                            break
                if 'date' not in df.columns:
                    date_col = str(df.index.name or '')
                    if 'date' in date_col.lower():
                        df = df.reset_index()
                if 'date' in df.columns:
                    if not pd.api.types.is_datetime64_any_dtype(df['date']):
                        df['date'] = pd.to_datetime(df['date'])
                    df = df.sort_values('date').reset_index(drop=True)
                    return df
        except Exception:
            pass
        return pd.DataFrame()

    def _from_cache(self, code: str) -> pd.DataFrame:
        return self._cache.get(code, max_age_days=1)

    def _from_api(self, code: str, days: int = 250) -> pd.DataFrame:
        self._init_bs()
        if not self._bs_logged_in:
            return pd.DataFrame()

        plain = str(code).zfill(6)
        bs_code = f"sh.{plain}" if plain.startswith('6') else f"sz.{plain}"

        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days * 2)).strftime('%Y-%m-%d')

        for attempt in range(3):
            try:
                rs = self._bs.query_history_k_data_plus(
                    bs_code,
                    "date,open,high,low,close,volume",
                    start_date=start_date, end_date=end_date,
                    frequency="d", adjustflag="2"
                )
                if rs.error_code != '0':
                    if attempt < 2:
                        time.sleep(2 ** attempt)
                        continue
                    return pd.DataFrame()

                rows = []
                while rs.next():
                    row = rs.get_row_data()
                    rows.append([
                        '0' if v == '' or v is None else v
                        for v in row
                    ])

                if len(rows) < 30:
                    return pd.DataFrame()

                df = pd.DataFrame(rows, columns=['date', 'open', 'high', 'low', 'close', 'volume'])
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                df = df.dropna(subset=['open', 'high', 'low', 'close', 'volume'])
                df['date'] = pd.to_datetime(df['date'])
                df = df.sort_values('date').reset_index(drop=True)
                return df

            except Exception:
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                return pd.DataFrame()

        return pd.DataFrame()

    def daily_data(self, code: str, days: int = 250) -> pd.DataFrame:
        """三层数据源：TDX → 缓存 → API"""
        df = self._from_tdx(code)
        if not df.empty and len(df) >= days:
            return df.tail(days).reset_index(drop=True)

        df = self._from_cache(code)
        if not df.empty:
            if len(df) >= days:
                return df.tail(days).reset_index(drop=True)
            if len(df) >= 30:
                self._merge_and_update(code, df, days)
                return self._cache.get(code).tail(days).reset_index(drop=True)

        df = self._from_api(code, days)
        if not df.empty:
            self._cache.set(code, df)
        return df.tail(days).reset_index(drop=True) if len(df) > days else df

    def _merge_and_update(self, code: str, cached: pd.DataFrame, days: int):
        cached_last = cached['date'].max()
        today = datetime.now().date()
        if cached_last.date() >= today:
            return

        new_data = self._from_api(code, days=60)
        if new_data.empty:
            return

        merged = pd.concat([cached, new_data]).drop_duplicates(
            subset='date', keep='last').sort_values('date').reset_index(drop=True)
        self._cache.set(code, merged)

    def stock_list(self) -> list:
        if self._stock_list_cache:
            return self._stock_list_cache

        cache_path = self._cache.cache_dir / '_stock_list.json'
        if cache_path.exists():
            try:
                data = json.loads(cache_path.read_text())
                age = time.time() - data.get('ts', 0)
                if age < 86400:
                    self._stock_list_cache = data['stocks']
                    return self._stock_list_cache
            except Exception:
                pass

        stocks = _with_timeout(self._from_tdx_stock_list, timeout=15)
        if stocks:
            self._stock_list_cache = stocks
            self._save_stock_list_cache(stocks)
            return stocks

        stocks = _with_timeout(self._from_api_stock_list, timeout=30)
        if stocks:
            self._stock_list_cache = stocks
            self._save_stock_list_cache(stocks)
            return stocks

        stocks = self._from_cache_files()
        if stocks:
            self._stock_list_cache = stocks
            self._save_stock_list_cache(stocks)
            return stocks

        return []

    def _from_cache_files(self) -> list:
        try:
            result = []
            for f in sorted(self._cache.cache_dir.glob('*.csv')):
                code = f.stem
                if len(code) == 6 and code.isdigit():
                    if self._is_main_board(code, ''):
                        result.append((code, code))
            return result
        except Exception:
            return []

    def _save_stock_list_cache(self, stocks: list):
        try:
            cache_path = self._cache.cache_dir / '_stock_list.json'
            cache_path.write_text(json.dumps({
                'ts': time.time(),
                'count': len(stocks),
                'stocks': stocks,
            }))
        except Exception:
            pass

    def _from_tdx_stock_list(self) -> list:
        self._init_tdx()
        if self._tdx_reader is None:
            return []
        try:
            raw = self._tdx_reader.stocks()
            if raw is None:
                return []
            result = []
            for code, name in raw.items():
                if self._is_main_board(str(code), name):
                    result.append((str(code), name))
            return result
        except Exception:
            return []

    def _from_api_stock_list(self) -> list:
        self._init_bs()
        if not self._bs_logged_in:
            return []

        for i in range(10):
            date_str = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            try:
                rs = self._bs.query_all_stock(day=date_str)
                if rs.error_code != '0':
                    continue
                data = rs.data
                if not data or len(data) == 0:
                    continue
                result = []
                for row in data:
                    if len(row) < 3:
                        continue
                    code = row[0]
                    type_flag = row[1]
                    name = row[2]
                    if type_flag != '1':
                        continue
                    plain = code.split('.')[-1]
                    if self._is_main_board(plain, name):
                        result.append((plain, name))
                if result:
                    return result
            except Exception:
                continue
        return []

    @staticmethod
    def _is_main_board(code: str, name: str) -> bool:
        plain = code.split('.')[-1] if '.' in code else code.zfill(6)

        if not plain.isdigit() or len(plain) != 6:
            return False

        if plain.startswith('5') or plain.startswith('1'):
            return False

        for kw in INDEX_KEYWORDS:
            if kw in name:
                return False
        if any(kw in name for kw in ['指数', '基金', '债', '购', '沽']):
            return False

        return True

    def cache_stats(self) -> dict:
        return self._cache.stats()

    def close(self):
        if self._bs and self._bs_logged_in:
            try:
                self._bs.logout()
            except Exception:
                pass
            self._bs_logged_in = False
