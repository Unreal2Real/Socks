"""
Fundamental data fetcher using baostock API.
Fetches financial indicators for A-share stocks.
"""
import baostock as bs
import pandas as pd
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _year_quarter(quarter_offset: int = 0) -> tuple:
    import datetime
    now = datetime.date.today()
    total_quarter = now.year * 4 + (now.month - 1) // 3
    total_quarter += quarter_offset
    y = total_quarter // 4
    q = (total_quarter % 4) + 1
    return str(y), str(q)


class FundamentalData:
    def __init__(self, bs_instance=None):
        self._bs = bs_instance

    def _ensure_login(self):
        if self._bs is None:
            bs.login()
            self._bs = bs
        return self._bs

    def _bs_code(self, code: str) -> str:
        plain = str(code).zfill(6)
        return 'sh.' + plain if plain.startswith('6') else 'sz.' + plain

    @staticmethod
    def _safe_float(v):
        try:
            return float(v) if v and v != '' and v != 'None' else None
        except (ValueError, TypeError):
            return None

    def _fetch_fields(self, query_fn, code: str, year: str, quarter: str,
                      field_map: dict) -> dict:
        bs_code = self._bs_code(code)
        bs_inst = self._ensure_login()
        try:
            rs = query_fn(bs_inst, bs_code, year, quarter)
            if rs.error_code != '0':
                return {}
            while rs.next():
                row = rs.get_row_data()
                label = ''
                for i, f in enumerate(rs.fields):
                    if f in ('statDate',):
                        label = row[i] if i < len(row) else ''
                if not label:
                    label = year + 'Q' + quarter
                entry = {}
                for field_name, col_name in field_map.items():
                    for i, f in enumerate(rs.fields):
                        if f == col_name:
                            entry[field_name] = self._safe_float(row[i] if i < len(row) else '')
                            break
                return entry
        except Exception as e:
            pass
        return {}

    def growth_data(self, code: str) -> dict:
        result = {}
        for offset in range(4):
            y, q = _year_quarter(-offset - 1)
            entry = self._fetch_fields(
                lambda bs_inst, c, y, q: bs_inst.query_growth_data(code=c, year=y, quarter=q),
                code, y, q,
                {'profit_yoy': 'YOYNI', 'eps_yoy': 'YOYEPSBasic',
                 'equity_yoy': 'YOYEquity', 'asset_yoy': 'YOYAsset'}
            )
            if entry:
                label = y + 'Q' + q
                result[label] = entry
        return result

    def profit_data(self, code: str) -> dict:
        result = {}
        for offset in range(4):
            y, q = _year_quarter(-offset - 1)
            entry = self._fetch_fields(
                lambda bs_inst, c, y, q: bs_inst.query_profit_data(code=c, year=y, quarter=q),
                code, y, q,
                {'roe': 'roeAvg', 'net_margin': 'npMargin',
                 'gross_margin': 'gpMargin', 'eps': 'epsTTM'}
            )
            if entry:
                label = y + 'Q' + q
                result[label] = entry
        return result

    def balance_data(self, code: str) -> dict:
        result = {}
        for offset in range(4):
            y, q = _year_quarter(-offset - 1)
            entry = self._fetch_fields(
                lambda bs_inst, c, y, q: bs_inst.query_balance_data(code=c, year=y, quarter=q),
                code, y, q,
                {'current_ratio': 'currentRatio', 'quick_ratio': 'quickRatio',
                 'debt_ratio': 'liabilityToAsset'}
            )
            if entry:
                label = y + 'Q' + q
                result[label] = entry
        return result

    def stock_industry(self, code: str) -> dict:
        bs_code = self._bs_code(code)
        bs_inst = self._ensure_login()
        try:
            rs = bs_inst.query_stock_industry(code=bs_code)
            if rs.error_code != '0':
                return {}
            while rs.next():
                row = rs.get_row_data()
                return {
                    'industry': row[3] if len(row) > 3 else '',
                    'industry_type': row[2] if len(row) > 2 else '',
                }
        except Exception:
            pass
        return {}

    def get_fundamental_summary(self, code: str) -> dict:
        latest_growth = self.growth_data(code)
        latest_profit = self.profit_data(code)
        latest_balance = self.balance_data(code)
        industry = self.stock_industry(code)

        growth_latest = list(latest_growth.values())[0] if latest_growth else {}
        profit_latest = list(latest_profit.values())[0] if latest_profit else {}
        balance_latest = list(latest_balance.values())[0] if latest_balance else {}

        return {
            'growth': growth_latest,
            'profit': profit_latest,
            'balance': balance_latest,
            'industry': industry,
        }

    def close(self):
        pass
