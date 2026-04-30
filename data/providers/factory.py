from . import DataProvider
from .baostock_provider import BaostockProvider
from .tdx_provider import TDXProvider
from .hybrid_provider import HybridProvider
from .unified_provider import UnifiedProvider
from config.settings import DATA_SOURCE_CONFIG


def create_provider(source_type: str = None) -> DataProvider:
    if source_type is None:
        source_type = DATA_SOURCE_CONFIG.get('default', 'unified')

    if source_type == 'unified':
        tdx_path = DATA_SOURCE_CONFIG.get('tdx_path', 'C:/zd_zsone')
        return UnifiedProvider(tdx_path=tdx_path)
    elif source_type == 'hybrid':
        tdx_path = DATA_SOURCE_CONFIG.get('tdx_path', 'C:/zd_zsone')
        return HybridProvider(tdx_path=tdx_path)
    elif source_type == 'baostock':
        return BaostockProvider()
    elif source_type == 'tdx':
        tdx_path = DATA_SOURCE_CONFIG.get('tdx_path', 'C:/zd_zsone')
        return TDXProvider(data_path=tdx_path)
    else:
        raise ValueError(f"Unknown data source: {source_type}")


def create_provider_with_fallback() -> DataProvider:
    try:
        provider = create_provider()
        stock_list = provider.get_stock_list_with_names()
        if not stock_list:
            raise Exception("数据源验证失败")
        return provider
    except Exception as e:
        if DATA_SOURCE_CONFIG.get('fallback_enabled', False):
            print(f"主数据源失败: {e}, 切换到备用数据源")
            default_type = DATA_SOURCE_CONFIG.get('default', 'unified')
            fallback_type = 'baostock' if default_type != 'baostock' else 'unified'
            return create_provider(fallback_type)
        raise