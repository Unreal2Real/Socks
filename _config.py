import os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

TDX_PATH = os.environ.get('TDX_PATH', 'C:/zd_zsone')
CACHE_DIR = os.path.join(PROJECT_ROOT, 'data', 'cache')

FACTORY_PATTERN = {
    'uptrend_gain': 0.10,
    'consolidation_days_min': 10,
    'consolidation_days_max': 40,
    'bandwidth': 0.30,
    'volatility': 0.30,
    'volume_ratio': 0.8,
    'ma_periods': [5, 10, 20, 60],
    'bb_period': 20,
    'bb_std_dev': 2,
    'volume_ma_period': 20,
    'uptrend_min_days': 5,
}

SCAN = {
    'default_days': 250,
    'min_days': 60,
    'max_days_back': 180,
    'default_limit': 200,
    'max_pattern_age_days': 30,
}

MAIN_BOARD_PREFIXES = {
    'sh': ['600', '601', '603', '605'],
    'sz': ['000', '001', '002', '003'],
}

EXCLUDED_PREFIXES = ['300', '301', '688', '8', '4']

INDEX_KEYWORDS = [
    '指数', '基金', '国债', '企债', '上证', '深证', '综指',
    '成指', 'A股', 'B股', '等权', '基本', '全指', '全R',
    '沪公司', '沪企', '周期', '非周', '债', '成长', '价值',
    '民企', '国企', '海外', '中盘', '小盘', '中小', '380',
    '180', '50', '消费80', '高端', '主题', '服务',
    '食品饮料', '医药生物', '细分', '有色', '中证', '银河',
    '投资品', '消费品', '产业', '装备',
]
