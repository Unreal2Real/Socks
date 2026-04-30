from . import DataProvider
import pandas as pd
import os
from datetime import datetime
from typing import List, Tuple


class TDXProvider(DataProvider):
    def __init__(self, data_path: str = 'C:/zd_zsone/T0002/hq_cache'):
        self.data_path = data_path
        self.stock_list = self._load_stock_list()

    def _load_stock_list(self) -> List[Tuple[str, str]]:
        stocks = []
        dbf_path = os.path.join(self.data_path, 'base.dbf')
        
        if os.path.exists(dbf_path):
            try:
                import dbfread
                table = dbfread.DBF(dbf_path, encoding='gbk')
                for record in table:
                    code = record.get('code', '').strip()
                    name = record.get('name', '').strip()
                    if code and self._is_valid_code(code):
                        stocks.append((code, name))
                return stocks
            except Exception:
                pass
        
        return self._parse_tnf_stock_list()

    def _parse_tnf_stock_list(self) -> List[Tuple[str, str]]:
        stocks = []
        for market in ['sh', 'sz']:
            tnf_path = os.path.join(self.data_path, f'{market}s.tnf')
            if os.path.exists(tnf_path):
                stocks.extend(self._extract_stocks_from_tnf(tnf_path))
        return stocks

    def _extract_stocks_from_tnf(self, tnf_path: str) -> List[Tuple[str, str]]:
        stocks = []
        try:
            with open(tnf_path, 'rb') as f:
                f.read(4)
                stock_count = int.from_bytes(f.read(4), 'little')
                
                for _ in range(stock_count):
                    code_bytes = f.read(6)
                    code = code_bytes.decode('ascii').strip()
                    name_bytes = f.read(8)
                    name = name_bytes.decode('gbk', errors='ignore').strip()
                    if code:
                        stocks.append((code, name))
        except Exception:
            pass
        return stocks

    def get_daily_data(self, stock_code: str, days: int = 250) -> pd.DataFrame:
        market = 'sh' if stock_code.startswith('6') else 'sz'
        tnf_path = os.path.join(self.data_path, f'{market}s.tnf')
        
        if not os.path.exists(tnf_path):
            return pd.DataFrame()
        
        return self._parse_tnf_daily_data(tnf_path, stock_code, days)

    def _parse_tnf_daily_data(self, tnf_path: str, stock_code: str, days: int) -> pd.DataFrame:
        records = []
        
        try:
            with open(tnf_path, 'rb') as f:
                f.seek(8)
                stock_count = int.from_bytes(f.read(4), 'little')
                index_block_size = 20
                
                target_pos = None
                target_count = None
                
                for i in range(stock_count):
                    f.seek(8 + 4 + i * index_block_size)
                    code_bytes = f.read(6)
                    code = code_bytes.decode('ascii').strip()
                    
                    if code == stock_code:
                        f.seek(8 + 4 + i * index_block_size + 12)
                        data_pos = int.from_bytes(f.read(4), 'little')
                        data_count = int.from_bytes(f.read(4), 'little')
                        target_pos = data_pos
                        target_count = data_count
                        break
                
                if target_pos is None:
                    return pd.DataFrame()
                
                f.seek(target_pos)
                daily_record_size = 32
                
                read_count = min(target_count, days)
                for _ in range(read_count):
                    date_int = int.from_bytes(f.read(4), 'little')
                    open_price = int.from_bytes(f.read(4), 'little') / 100.0
                    high_price = int.from_bytes(f.read(4), 'little') / 100.0
                    low_price = int.from_bytes(f.read(4), 'little') / 100.0
                    close_price = int.from_bytes(f.read(4), 'little') / 100.0
                    volume = int.from_bytes(f.read(4), 'little')
                    amount = int.from_bytes(f.read(4), 'little')
                    f.seek(f.tell() + 4)
                    
                    year = date_int // 10000
                    month = (date_int // 100) % 100
                    day = date_int % 100
                    
                    if year >= 2000 and month <= 12 and day <= 31:
                        date_str = f"{year}-{month:02d}-{day:02d}"
                        records.append({
                            'date': date_str,
                            'open': open_price,
                            'high': high_price,
                            'low': low_price,
                            'close': close_price,
                            'volume': volume
                        })
                
                df = pd.DataFrame(records)
                df['date'] = pd.to_datetime(df['date'])
                df = df.sort_values('date').reset_index(drop=True)
                
                return df
            
        except Exception:
            return pd.DataFrame()

    def get_daily_data_in_range(self, stock_code: str,
                                 start_date: str, end_date: str) -> pd.DataFrame:
        df = self.get_daily_data(stock_code, days=500)
        if df.empty:
            return df
        mask = (df['date'] >= start_date) & (df['date'] <= end_date)
        return df[mask].reset_index(drop=True)

    def get_stock_list_with_names(self) -> List[Tuple[str, str]]:
        return self.stock_list

    def get_stock_info(self, stock_code: str) -> dict:
        for code, name in self.stock_list:
            if code == stock_code:
                return {'code': code, 'name': name}
        return {}

    def _is_valid_code(self, code: str) -> bool:
        prefixes = ['600', '601', '603', '605', '688', '000', '001', '002', '300', '301']
        return any(code.startswith(p) for p in prefixes)

    def close(self):
        pass