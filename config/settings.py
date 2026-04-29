FACTORY_PATTERN_CONFIG = {
    'uptrend_gain': 0.15,
    'consolidation_days_min': 10,
    'consolidation_days_max': 40,
    'bandwidth': 0.20,
    'volatility': 0.20,
    'volume_ratio': 0.6,
    'ma_periods': [5, 10, 20, 60],
    'bb_period': 20,
    'bb_std_dev': 2,
    'volume_ma_period': 20,
    'uptrend_min_days': 5,
}

TRADING_CONFIG = {
    'market': 'A股',
    'data_days': 250,
    'output_dir': 'results',
}
