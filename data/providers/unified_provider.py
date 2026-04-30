from . import DataProvider
import pandas as pd
from typing import List, Tuple
from .cache import DataCache


class UnifiedProvider(DataProvider):
    def __init__(self, tdx_path: str = 'C:/zd_zsone'):
        self.tdx_path = tdx_path
        self.tdx_reader = None
        self.quotes_client = None
        self.cache = DataCache()
        self._baostock_provider = None

    def _init_tdx_reader(self):
        if self.tdx_reader is None:
            try:
                from mootdx.reader import Reader
                self.tdx_reader = Reader.factory(market='std', tdxdir=self.tdx_path)
            except Exception:
                self.tdx_reader = None

    def _init_baostock(self):
        if self._baostock_provider is None:
            try:
                import baostock as bs
                self._bs = bs
                self._bs.login()
            except Exception:
                self._bs = None

    def _get_from_tdx(self, stock_code: str) -> pd.DataFrame:
        self._init_tdx_reader()
        if self.tdx_reader:
            try:
                df = self.tdx_reader.daily(symbol=stock_code)
                if not df.empty:
                    df['date'] = pd.to_datetime(df['date'])
                    df = df.sort_values('date').reset_index(drop=True)
                    return df
            except Exception:
                pass
        return pd.DataFrame()

    def _get_from_cache(self, stock_code: str, max_age_days: int = 1) -> pd.DataFrame:
        return self.cache.get(stock_code, max_age_days=max_age_days)

    def _get_from_baostock(self, stock_code: str, days: int = 250) -> pd.DataFrame:
        self._init_baostock()
        if self._bs is None:
            return pd.DataFrame()

        try:
            plain = str(stock_code).zfill(6)
            if plain.startswith('6'):
                bs_code = f"sh.{plain}"
            else:
                bs_code = f"sz.{plain}"

            from datetime import datetime, timedelta
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=days * 2)).strftime('%Y-%m-%d')

            rs = self._bs.query_history_k_data_plus(
                bs_code,
                "date,open,high,low,close,volume",
                start_date=start_date,
                end_date=end_date,
                frequency="d",
                adjustflag="2"
            )

            if rs.error_code != '0':
                return pd.DataFrame()

            rows = []
            while rs.next():
                row = rs.get_row_data()
                row = ['0' if v == 'None' else v for v in row]
                rows.append(row)

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
            return pd.DataFrame()

    def get_daily_data(self, stock_code: str, days: int = 250) -> pd.DataFrame:
        plain = str(stock_code).zfill(6)

        df = self._get_from_tdx(plain)
        if not df.empty and len(df) >= days:
            return df.tail(days).reset_index(drop=True)

        df = self._get_from_cache(plain, max_age_days=1)
        if df is not None and not df.empty:
            if len(df) >= days:
                return df.tail(days).reset_index(drop=True)
            if len(df) >= 30:
                return df.reset_index(drop=True)

        df = self._get_from_baostock(plain, days)
        if not df.empty:
            self.cache.set(plain, df)

        if len(df) > days:
            df = df.tail(days).reset_index(drop=True)
        return df

    def get_daily_data_in_range(self, stock_code: str,
                                 start_date: str, end_date: str) -> pd.DataFrame:
        df = self.get_daily_data(stock_code, days=500)
        if df.empty:
            return df
        mask = (df['date'] >= start_date) & (df['date'] <= end_date)
        return df[mask].reset_index(drop=True)

    def get_minute_data(self, stock_code: str, count: int = 100) -> pd.DataFrame:
        self._init_quotes_client()
        if self.quotes_client:
            try:
                data = self.quotes_client.bars(symbol=stock_code, frequency=9, count=count)
                if isinstance(data, pd.DataFrame) and not data.empty:
                    return data
            except Exception:
                pass
        return pd.DataFrame()

    def get_realtime_quote(self, stock_code: str) -> dict:
        self._init_quotes_client()
        if self.quotes_client:
            try:
                quote = self.quotes_client.quote(symbol=stock_code)
                if quote:
                    return quote
            except Exception:
                pass
        return {}

    def get_stock_list_with_names(self) -> List[Tuple[str, str]]:
        self._init_tdx_reader()
        if self.tdx_reader:
            try:
                stocks = self.tdx_reader.stocks()
                if stocks is not None:
                    filtered = []
                    for code, name in stocks.items():
                        if self._is_main_board_stock(str(code), name):
                            filtered.append((str(code), name))
                    if filtered:
                        return filtered
            except Exception:
                pass

        return self._get_stock_list_from_baostock()

    def _get_stock_list_from_baostock(self) -> List[Tuple[str, str]]:
        self._init_baostock()
        if self._bs is None:
            return []

        from datetime import datetime, timedelta
        for i in range(10):
            date_str = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            try:
                rs = self._bs.query_all_stock(day=date_str)
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
                    if not self._is_main_board_stock(code, name):
                        continue

                    plain_code = code.split('.')[-1]
                    stock_list.append((plain_code, name))

                if stock_list:
                    return stock_list
            except Exception:
                continue

        return []

    def get_stock_info(self, stock_code: str) -> dict:
        self._init_quotes_client()
        if self.quotes_client:
            try:
                quote = self.quotes_client.quote(symbol=stock_code)
                if quote and isinstance(quote, dict):
                    return {
                        'code': stock_code,
                        'name': quote.get('name', ''),
                        'price': quote.get('price', 0),
                        'change': quote.get('change', 0)
                    }
            except Exception:
                pass
        return {'code': stock_code, 'name': ''}

    def get_cache_stats(self) -> dict:
        return {**self.cache.get_stats(), 'enabled': True}

    def clear_cache(self, stock_code: str = None):
        self.cache.clear(stock_code)

    def close(self):
        if self.quotes_client:
            try:
                self.quotes_client.close()
            except Exception:
                pass
        if self._bs:
            try:
                self._bs.logout()
            except Exception:
                pass

    @staticmethod
    def _is_main_board_stock(code: str, name: str) -> bool:
        plain = code.split('.')[-1] if '.' in code else code.zfill(6)

        if plain.startswith('600') or plain.startswith('601') or plain.startswith('603') or plain.startswith('605'):
            return True
        if plain.startswith('688'):
            return False
        if plain.startswith('300') or plain.startswith('301'):
            return False
        if plain.startswith('8') or plain.startswith('4'):
            return False

        if plain.startswith('000') or plain.startswith('001') or plain.startswith('002'):
            index_keywords = ['指数', '基金', '国债', '企债', '上证', '深证', '综指',
                              '成指', 'A股', 'B股', '等权', '基本', '全指', '全R',
                              '沪公司', '沪企', '周期', '非周', '债', '成长', '价值',
                              '民企', '国企', '海外', '中盘', '小盘', '中小', '380',
                              '180', '50', '全指', '消费80', '高端', '主题', '服务',
                              '食品饮料', '医药生物', '细分', '有色', '中证', '银河',
                              '投资品', '消费品', '产业', '装备']
            for keyword in index_keywords:
                if keyword in name:
                    return False
            if len(name) <= 4 and ('A' in name or 'B' in name):
                return True
            if any(kw in name for kw in ['ST', '*ST', '退']):
                return True
            if len(name) >= 2 and not any(kw in name for kw in ['指数', '基金', '债']):
                return True
            return False

        return False