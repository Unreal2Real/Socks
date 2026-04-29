import pandas as pd
import numpy as np


class TechnicalIndicators:
    @staticmethod
    def calculate_ma(df: pd.DataFrame, periods: list = None) -> pd.DataFrame:
        if periods is None:
            periods = [5, 10, 20, 60]

        for period in periods:
            df[f'ma{period}'] = df['close'].rolling(window=period).mean()

        return df

    @staticmethod
    def calculate_bollinger_bands(df: pd.DataFrame, period: int = 20, std_dev: int = 2) -> pd.DataFrame:
        df['bb_middle'] = df['close'].rolling(window=period).mean()
        df['bb_std'] = df['close'].rolling(window=period).std()
        df['bb_upper'] = df['bb_middle'] + std_dev * df['bb_std']
        df['bb_lower'] = df['bb_middle'] - std_dev * df['bb_std']
        df['bb_bandwidth'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
        df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])

        return df

    @staticmethod
    def calculate_volume_ma(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
        df['volume_ma'] = df['volume'].rolling(window=period).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma']

        return df

    @staticmethod
    def calculate_all(df: pd.DataFrame, config: dict = None) -> pd.DataFrame:
        if config is None:
            config = {
                'ma_periods': [5, 10, 20, 60],
                'bb_period': 20,
                'bb_std_dev': 2,
                'volume_ma_period': 20
            }

        df = TechnicalIndicators.calculate_ma(df, config.get('ma_periods', [5, 10, 20, 60]))
        df = TechnicalIndicators.calculate_bollinger_bands(df,
                                                            config.get('bb_period', 20),
                                                            config.get('bb_std_dev', 2))
        df = TechnicalIndicators.calculate_volume_ma(df, config.get('volume_ma_period', 20))

        return df

    @staticmethod
    def is_bullish_arrangement(df: pd.DataFrame, idx: int) -> bool:
        if idx < 20:
            return False

        ma5 = df.loc[idx, 'ma5'] if 'ma5' in df.columns else None
        ma10 = df.loc[idx, 'ma10'] if 'ma10' in df.columns else None
        ma20 = df.loc[idx, 'ma20'] if 'ma20' in df.columns else None

        if ma5 is None or ma10 is None or ma20 is None:
            return False

        return ma5 > ma10 > ma20

    @staticmethod
    def calculate_volatility(df: pd.DataFrame, start_idx: int, end_idx: int) -> float:
        if start_idx >= end_idx:
            return 0.0

        period_data = df.loc[start_idx:end_idx-1]
        high_price = period_data['high'].max()
        low_price = period_data['low'].min()
        start_price = period_data.iloc[0]['close']

        if start_price == 0:
            return 0.0

        return (high_price - low_price) / start_price

    @staticmethod
    def calculate_price_change(df: pd.DataFrame, start_idx: int, end_idx: int) -> float:
        if start_idx >= end_idx:
            return 0.0

        start_price = df.loc[start_idx, 'close']
        end_price = df.loc[end_idx - 1, 'close']

        if start_price == 0:
            return 0.0

        return (end_price - start_price) / start_price
