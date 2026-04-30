from . import DataProvider
import pandas as pd
from typing import List, Tuple


class HybridProvider(DataProvider):
    def __init__(self, tdx_path: str = 'C:/zd_zsone'):
        self.tdx_path = tdx_path
        self.tdx_reader = None
        self.quotes_client = None

    def _init_tdx_reader(self):
        if self.tdx_reader is None:
            try:
                from mootdx.reader import Reader
                self.tdx_reader = Reader.factory(market='std', tdxdir=self.tdx_path)
            except Exception:
                self.tdx_reader = None

    def _init_quotes_client(self):
        if self.quotes_client is None:
            try:
                from mootdx.quotes import Quotes
                self.quotes_client = Quotes.factory(market='std', timeout=10, retry=3)
            except Exception:
                self.quotes_client = None

    def get_daily_data(self, stock_code: str, days: int = 250) -> pd.DataFrame:
        self._init_tdx_reader()
        
        if self.tdx_reader:
            try:
                df = self.tdx_reader.daily(symbol=stock_code)
                if not df.empty:
                    df['date'] = pd.to_datetime(df['date'])
                    df = df.sort_values('date').reset_index(drop=True)
                    return df.tail(days)
            except Exception:
                pass
        
        return pd.DataFrame()

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
        
        from .baostock_provider import BaostockProvider
        fallback = BaostockProvider()
        try:
            result = fallback.get_stock_list_with_names()
            fallback.close()
            return result
        except Exception:
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

    @staticmethod
    def _is_main_board_stock(code: str, name: str) -> bool:
        plain = code.zfill(6)
        
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

    def close(self):
        if self.quotes_client:
            try:
                self.quotes_client.close()
            except Exception:
                pass