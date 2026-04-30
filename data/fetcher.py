import threading
import baostock as bs
import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta
from typing import Optional


CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data_cache', 'daily')


class DataFetcher:
    _bs_lock = threading.RLock()
    _logged_in = False

    def __init__(self):
        self.bs = bs
        self._ensure_cache_dir()

    @staticmethod
    def _ensure_cache_dir():
        os.makedirs(CACHE_DIR, exist_ok=True)

    def _get_cache_path(self, stock_code: str) -> str:
        return os.path.join(CACHE_DIR, f'{stock_code}.csv')

    def _read_cache(self, stock_code: str, days: int) -> pd.DataFrame:
        path = self._get_cache_path(stock_code)
        if not os.path.exists(path):
            return pd.DataFrame()
        try:
            df = pd.read_csv(path, parse_dates=['date'])
            if not df.empty:
                last_date = df['date'].max()
                if hasattr(last_date, 'strftime'):
                    last_date = last_date.strftime('%Y-%m-%d')
                min_date = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
                if last_date >= min_date:
                    if len(df) <= days * 3:
                        return df
            return pd.DataFrame()
        except Exception:
            return pd.DataFrame()

    def _write_cache(self, stock_code: str, df: pd.DataFrame):
        if df.empty:
            return
        path = self._get_cache_path(stock_code)
        try:
            df.to_csv(path, index=False)
        except Exception:
            pass

    def _ensure_login(self):
        with DataFetcher._bs_lock:
            if not DataFetcher._logged_in:
                lg = self.bs.login()
                if lg.error_code == '0':
                    DataFetcher._logged_in = True
                else:
                    print(f"Baostock login warning: {lg.error_msg}")

    def _query(self, bs_code: str, fields: str, start_date: str, end_date: str, frequency: str):
        with DataFetcher._bs_lock:
            self._ensure_login()
            return self.bs.query_history_k_data_plus(
                bs_code, fields, start_date=start_date, end_date=end_date,
                frequency=frequency, adjustflag="2")

    def close(self):
        with DataFetcher._bs_lock:
            if DataFetcher._logged_in:
                try:
                    self.bs.logout()
                except Exception:
                    pass
                DataFetcher._logged_in = False

    def get_daily_data_in_range(self, stock_code: str,
                                 start_date: str, end_date: str) -> pd.DataFrame:
        """获取指定日期范围内的日线数据（不截断，适用于回测）"""
        self._ensure_login()
        stock_code = self._format_stock_code(stock_code)
        bs_code = self._to_bs_code(stock_code)

        try:
            rs = self._query(
                bs_code,
                "date,open,high,low,close,volume",
                start_date=start_date,
                end_date=end_date,
                frequency="d"
            )

            if rs.error_code != '0':
                return pd.DataFrame()

            rows = []
            while rs.next():
                row = rs.get_row_data()
                row = ['0' if v == 'None' else v for v in row]
                rows.append(row)

            if len(rows) < 10:
                return pd.DataFrame()

            df = pd.DataFrame(rows, columns=['date', 'open', 'high', 'low', 'close', 'volume'])

            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            df = df.dropna(subset=['open', 'high', 'low', 'close', 'volume'])
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date').reset_index(drop=True)

            return df

        except Exception:
            return pd.DataFrame()

    def get_daily_data(self, stock_code: str, days: int = 250) -> pd.DataFrame:
        stock_code = self._format_stock_code(stock_code)

        cached = self._read_cache(stock_code, days)
        if not cached.empty:
            return cached

        self._ensure_login()
        bs_code = self._to_bs_code(stock_code)
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days * 2)).strftime('%Y-%m-%d')

        try:
            rs = self._query(
                bs_code,
                "date,open,high,low,close,volume",
                start_date=start_date,
                end_date=end_date,
                frequency="d"
            )

            if rs.error_code != '0':
                return pd.DataFrame()

            rows = []
            while rs.next():
                row = rs.get_row_data()
                row = ['0' if v == 'None' else v for v in row]
                rows.append(row)

            if len(rows) < min(days, 10):
                return pd.DataFrame()

            df = pd.DataFrame(rows, columns=['date', 'open', 'high', 'low', 'close', 'volume'])

            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            df = df.dropna(subset=['open', 'high', 'low', 'close', 'volume'])
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date').reset_index(drop=True)

            self._write_cache(stock_code, df)

            if len(df) > days:
                df = df.tail(days).reset_index(drop=True)
            return df

        except Exception:
            return pd.DataFrame()

    def get_stock_list(self, market: str = 'all') -> list:
        stocks_with_names = self.get_stock_list_with_names()
        return [code for code, name in stocks_with_names]

    def get_stock_list_with_names(self) -> list:
        with DataFetcher._bs_lock:
            self._ensure_login()
            trading_dates = []
            d = datetime.now()
            for _ in range(10):
                trading_dates.append(d.strftime('%Y-%m-%d'))
                d -= timedelta(days=1)

            for date_str in trading_dates:
                try:
                    rs = self.bs.query_all_stock(day=date_str)
                    if rs.error_code != '0':
                        continue

                    data = rs.data
                    if not data or len(data) == 0:
                        continue

                    stock_list = []
                    for row in data:
                        code = row[0]
                        type_flag = row[1]
                        name = row[2] if len(row) > 2 else ''

                        if type_flag != '1':
                            continue
                        if not self._is_stock_code(code):
                            continue

                        plain_code = self._from_bs_code(code)
                        stock_list.append((plain_code, name))

                    if stock_list:
                        print(f"获取到 {len(stock_list)} 只股票 (数据日期: {date_str})")
                        return stock_list

                except Exception:
                    continue

            return []

    def get_stock_info(self, stock_code: str) -> dict:
        self._ensure_login()
        stock_code = self._format_stock_code(stock_code)
        bs_code = self._to_bs_code(stock_code)

        try:
            rs = self.bs.query_stock_basic(bs_code)
            if rs.error_code != '0':
                return {}

            if rs.next():
                row = rs.get_row_data()
                return {
                    'code': stock_code,
                    'name': row[1],
                }
            return {}
        except Exception:
            return {}

    def _to_bs_code(self, stock_code: str) -> str:
        if stock_code.startswith('6'):
            return f"sh.{stock_code}"
        else:
            return f"sz.{stock_code}"

    @staticmethod
    def _from_bs_code(bs_code: str) -> str:
        return bs_code.split('.')[-1]

    @staticmethod
    def _is_stock_code(code: str) -> bool:
        plain = code.split('.')[-1]
        if plain.startswith('600') or plain.startswith('601') or plain.startswith('603') or plain.startswith('605'):
            return True
        if plain.startswith('688'):
            return True
        if plain.startswith('000') or plain.startswith('001') or plain.startswith('002'):
            return True
        if plain.startswith('300') or plain.startswith('301'):
            return True
        return False

    @staticmethod
    def _format_stock_code(stock_code: str) -> str:
        return str(stock_code).zfill(6)

    def generate_factory_pattern_data(self, base_price: float = 10.0) -> pd.DataFrame:
        self._ensure_login()
        dates = [datetime.now() - timedelta(days=i) for i in range(150)]
        dates.reverse()

        uptrend_days = 60
        consolidation_days = 30
        total_days = len(dates)

        prices = np.zeros(total_days)
        prices[0] = base_price

        for i in range(1, uptrend_days):
            daily_return = np.random.normal(0.008, 0.015)
            prices[i] = prices[i-1] * (1 + daily_return)

        peak_price = prices[uptrend_days - 1]

        for i in range(uptrend_days, uptrend_days + consolidation_days):
            daily_return = np.random.normal(0, 0.005)
            prices[i] = peak_price * (1 + daily_return)

        for i in range(uptrend_days + consolidation_days, total_days):
            daily_return = np.random.normal(0, 0.008)
            prices[i] = prices[i-1] * (1 + daily_return)

        open_prices = prices * (1 + np.random.normal(0, 0.003, total_days))
        high_prices = np.maximum(prices, open_prices) * (1 + np.random.uniform(0, 0.01, total_days))
        low_prices = np.minimum(prices, open_prices) * (1 - np.random.uniform(0, 0.01, total_days))

        volume_base = 10000000
        volumes = np.zeros(total_days)
        for i in range(total_days):
            if i < uptrend_days:
                volumes[i] = volume_base * (1 + np.random.normal(0.8, 0.2))
            elif i < uptrend_days + consolidation_days:
                volumes[i] = volume_base * (1 + np.random.normal(-0.6, 0.1))
            else:
                volumes[i] = volume_base * (1 + np.random.normal(0, 0.1))

        df = pd.DataFrame({
            'date': dates,
            'open': open_prices,
            'high': high_prices,
            'low': low_prices,
            'close': prices,
            'volume': volumes
        })

        return df

    def generate_normal_data(self, base_price: float = 10.0) -> pd.DataFrame:
        self._ensure_login()
        dates = [datetime.now() - timedelta(days=i) for i in range(150)]
        dates.reverse()

        total_days = len(dates)
        prices = np.zeros(total_days)
        prices[0] = base_price

        for i in range(1, total_days):
            daily_return = np.random.normal(0, 0.01)
            prices[i] = prices[i-1] * (1 + daily_return)

        open_prices = prices * (1 + np.random.normal(0, 0.003, total_days))
        high_prices = np.maximum(prices, open_prices) * (1 + np.random.uniform(0, 0.01, total_days))
        low_prices = np.minimum(prices, open_prices) * (1 - np.random.uniform(0, 0.01, total_days))

        volume_base = 10000000
        volumes = volume_base * (1 + np.random.normal(0, 0.2, total_days))

        df = pd.DataFrame({
            'date': dates,
            'open': open_prices,
            'high': high_prices,
            'low': low_prices,
            'close': prices,
            'volume': volumes
        })

        return df
