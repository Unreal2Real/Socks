from abc import ABC, abstractmethod
from typing import List, Tuple
import pandas as pd


class DataProvider(ABC):
    @abstractmethod
    def get_daily_data(self, stock_code: str, days: int = 250) -> pd.DataFrame:
        pass

    @abstractmethod
    def get_daily_data_in_range(self, stock_code: str,
                                 start_date: str, end_date: str) -> pd.DataFrame:
        pass

    @abstractmethod
    def get_stock_list_with_names(self) -> List[Tuple[str, str]]:
        pass

    @abstractmethod
    def get_stock_info(self, stock_code: str) -> dict:
        pass

    @abstractmethod
    def close(self):
        pass