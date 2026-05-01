import sys; sys.path.insert(0,'.')
from data.fetcher import DataFetcher
f = DataFetcher()
tests = [('510050', '华夏上证50ETF'), ('159919', '沪深300ETF'), ('601398', '工商银行'), ('000001', '平安银行'), ('110029', '深证成指')]
for code, name in tests:
    result = f._is_main_board(code, name or code)
    print(code, name, "PASS" if result else "FILTERED")
f.close()
