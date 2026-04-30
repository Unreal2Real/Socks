from . import DataProvider
import baostock as bs
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Tuple


class BaostockProvider(DataProvider):
    def __init__(self):
        self.bs = bs
        self._logged_in = False

    def _ensure_login(self):
        if not self._logged_in:
            lg = self.bs.login()
            if lg.error_code == '0':
                self._logged_in = True
            else:
                print(f"Baostock login warning: {lg.error_msg}")

    def close(self):
        if self._logged_in:
            try:
                self.bs.logout()
            except Exception:
                pass
            self._logged_in = False

    def _to_bs_code(self, stock_code: str) -> str:
        stock_code = self._format_stock_code(stock_code)
        if stock_code.startswith('6'):
            return f"sh.{stock_code}"
        else:
            return f"sz.{stock_code}"

    @staticmethod
    def _format_stock_code(stock_code: str) -> str:
        return str(stock_code).zfill(6)

    def get_daily_data_in_range(self, stock_code: str,
                                 start_date: str, end_date: str) -> pd.DataFrame:
        self._ensure_login()
        bs_code = self._to_bs_code(stock_code)

        try:
            rs = self.bs.query_history_k_data_plus(
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

            if len(rows) < 10:
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
        self._ensure_login()
        bs_code = self._to_bs_code(stock_code)
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days * 2)).strftime('%Y-%m-%d')

        try:
            rs = self.bs.query_history_k_data_plus(
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

            if len(df) > days:
                df = df.tail(days).reset_index(drop=True)

            return df

        except Exception:
            return pd.DataFrame()

    def get_stock_list_with_names(self) -> List[Tuple[str, str]]:
        self._ensure_login()
        trading_dates = []
        d = datetime.now()
        for _ in range(10):
            trading_dates.append(d.strftime('%Y-%m-%d'))
            d -= timedelta(days=1)

        for date_str in trading_dates:
            try:
                rs = self.bs.query_all_stock(day=date_str)
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
                    print(f"获取到 {len(stock_list)} 只股票 (数据日期: {date_str})")
                    return stock_list

            except Exception:
                continue

        return []

    def get_stock_info(self, stock_code: str) -> dict:
        self._ensure_login()
        bs_code = self._to_bs_code(stock_code)

        try:
            rs = self.bs.query_stock_basic(bs_code)
            if rs.error_code != '0':
                return {}

            if rs.next():
                row = rs.get_row_data()
                return {
                    'code': stock_code,
                    'name': row[1],
                }
            return {}
        except Exception:
            return {}

    @staticmethod
    def _is_main_board_stock(code: str, name: str) -> bool:
        plain = code.split('.')[-1]
        
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