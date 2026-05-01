import sys; sys.path.insert(0,'.')
from data.fetcher import DataFetcher
f = DataFetcher()
tests = [('510050','ETF'),('159919','指数'),('300750','创业板'),('300136','创业板'),('601398','主板'),('000001','主板'),('002008','中小板')]
for code, name in tests:
    ok = f._is_main_board(code, name)
    print(code, name, 'PASS' if ok else 'FILTERED')
f.close()
