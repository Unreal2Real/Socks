import pandas as pd
from typing import List


class StockFilter:
    @staticmethod
    def filter_by_price(df: pd.DataFrame, min_price: float = 1.0, max_price: float = 500.0) -> bool:
        if len(df) == 0:
            return False

        latest_close = df.iloc[-1]['close']
        return min_price <= latest_close <= max_price

    @staticmethod
    def filter_by_volume(df: pd.DataFrame, min_volume: float = 1000000) -> bool:
        if len(df) == 0:
            return False

        avg_volume = df['volume'].tail(20).mean()
        return avg_volume >= min_volume

    @staticmethod
    def filter_by_market_cap(df: pd.DataFrame, min_market_cap: float = 1e9) -> bool:
        return True

    @staticmethod
    def filter_st_stocks(stock_info: dict) -> bool:
        if not stock_info:
            return True

        name = stock_info.get('name', stock_info.get('股票名称', ''))
        if 'ST' in name or '*ST' in name:
            return False

        return True

    @staticmethod
    def apply_filters(df: pd.DataFrame, stock_info: dict = None, filters: dict = None) -> bool:
        if filters is None:
            filters = {
                'min_price': 1.0,
                'max_price': 500.0,
                'min_volume': 1000000,
                'filter_st': True
            }

        if not StockFilter.filter_by_price(df, filters.get('min_price', 1.0),
                                           filters.get('max_price', 500.0)):
            return False

        if not StockFilter.filter_by_volume(df, filters.get('min_volume', 1000000)):
            return False

        if filters.get('filter_st', True) and stock_info:
            if not StockFilter.filter_st_stocks(stock_info):
                return False

        return True
