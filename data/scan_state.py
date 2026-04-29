import sqlite3
import json
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), 'scan_state.db')

STATUS_NO_PATTERN = 'no_pattern'
STATUS_WATCHING_UPTREND = 'watching_uptrend'
STATUS_WATCHING_CONSOLIDATION = 'watching_consolidation'
STATUS_MATCHED = 'matched'
STATUS_ERROR = 'error'

_SCAN_INTERVALS = {
    STATUS_NO_PATTERN: 7,
    STATUS_WATCHING_UPTREND: 3,
    STATUS_WATCHING_CONSOLIDATION: 1,
    STATUS_MATCHED: 5,
    STATUS_ERROR: 1,
}


class ScanState:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS scan_state (
                    stock_code TEXT PRIMARY KEY,
                    stock_name TEXT DEFAULT '',
                    status TEXT DEFAULT 'no_pattern',
                    last_scan_date TEXT,
                    next_scan_date TEXT,
                    scan_count INTEGER DEFAULT 0,
                    max_score REAL DEFAULT 0,
                    notes TEXT DEFAULT '',
                    pattern_data TEXT DEFAULT ''
                )
            ''')
            conn.commit()
        finally:
            conn.close()

    def get_stock(self, stock_code: str) -> dict:
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute(
                'SELECT * FROM scan_state WHERE stock_code = ?', (stock_code,))
            row = cur.fetchone()
            if row:
                cols = [d[0] for d in cur.description]
                return dict(zip(cols, row))
            return {}
        finally:
            conn.close()

    def update_stock(self, stock_code: str, stock_name: str = '',
                     status: str = STATUS_NO_PATTERN, score: float = 0,
                     notes: str = '', pattern_data: dict = None):
        today = datetime.now().strftime('%Y-%m-%d')
        interval = _SCAN_INTERVALS.get(status, 7)
        next_scan = (datetime.now() + timedelta(days=interval)).strftime('%Y-%m-%d')

        existing = self.get_stock(stock_code)
        scan_count = (existing.get('scan_count', 0) or 0) + 1
        max_score = max(existing.get('max_score', 0) or 0, score)

        pattern_json = json.dumps(pattern_data, ensure_ascii=False) if pattern_data else ''

        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute('''
                INSERT OR REPLACE INTO scan_state
                (stock_code, stock_name, status, last_scan_date, next_scan_date,
                 scan_count, max_score, notes, pattern_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (stock_code, stock_name, status, today, next_scan,
                  scan_count, max_score, notes, pattern_json))
            conn.commit()
        finally:
            conn.close()

    def needs_scan(self, stock_code: str) -> bool:
        existing = self.get_stock(stock_code)
        if not existing:
            return True
        next_scan = existing.get('next_scan_date', '')
        if not next_scan:
            return True
        try:
            return datetime.now() >= datetime.strptime(next_scan, '%Y-%m-%d')
        except ValueError:
            return True

    def get_stocks_by_status(self, status: str) -> list:
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute(
                'SELECT stock_code, stock_name FROM scan_state WHERE status = ?',
                (status,))
            rows = cur.fetchall()
            return [{'code': r[0], 'name': r[1]} for r in rows]
        finally:
            conn.close()

    def get_stats(self) -> dict:
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute('''
                SELECT status, COUNT(*) as cnt FROM scan_state GROUP BY status
            ''')
            rows = cur.fetchall()
            stats = {r[0]: r[1] for r in rows}
            stats['total'] = sum(stats.values())
            return stats
        finally:
            conn.close()

    def get_daily_scan_list(self, all_stocks: list) -> list:
        """从全量股票中筛选出今天需要扫描的股票"""
        today = datetime.now().strftime('%Y-%m-%d')
        scan_list = []

        conn = sqlite3.connect(self.db_path)
        try:
            for code, name in all_stocks:
                cur = conn.execute(
                    'SELECT next_scan_date, status FROM scan_state WHERE stock_code = ?',
                    (code,))
                row = cur.fetchone()
                if row is None:
                    scan_list.append((code, name))
                else:
                    next_scan, status = row
                    if status == STATUS_WATCHING_CONSOLIDATION:
                        scan_list.append((code, name))
                    elif next_scan and next_scan <= today:
                        scan_list.append((code, name))
            return scan_list
        finally:
            conn.close()

    def batch_update_status(self, updates: list):
        """批量更新状态 [{code, name, status, score, notes, pattern_data}]"""
        today = datetime.now().strftime('%Y-%m-%d')
        conn = sqlite3.connect(self.db_path)
        try:
            for item in updates:
                code = item['code']
                name = item.get('name', '')
                status = item.get('status', STATUS_NO_PATTERN)
                score = item.get('score', 0)
                notes = item.get('notes', '')
                pattern_data = item.get('pattern_data')

                interval = _SCAN_INTERVALS.get(status, 7)
                next_scan = (datetime.now() + timedelta(days=interval)).strftime('%Y-%m-%d')

                existing = conn.execute(
                    'SELECT scan_count, max_score FROM scan_state WHERE stock_code = ?',
                    (code,)).fetchone()
                scan_count = (existing[0] if existing else 0) + 1
                max_score = max((existing[1] if existing else 0), score)

                pattern_json = json.dumps(pattern_data, ensure_ascii=False) if pattern_data else ''

                conn.execute('''
                    INSERT OR REPLACE INTO scan_state
                    (stock_code, stock_name, status, last_scan_date, next_scan_date,
                     scan_count, max_score, notes, pattern_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (code, name, status, today, next_scan,
                      scan_count, max_score, notes, pattern_json))
            conn.commit()
        finally:
            conn.close()

    def get_watch_list(self) -> list:
        """获取观察列表（watching_uptrend + watching_consolidation）"""
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute('''
                SELECT stock_code, stock_name, status, max_score, notes
                FROM scan_state
                WHERE status IN (?, ?)
                ORDER BY
                    CASE WHEN status = ? THEN 0 ELSE 1 END,
                    max_score DESC
            ''', (STATUS_WATCHING_CONSOLIDATION, STATUS_WATCHING_UPTREND,
                  STATUS_WATCHING_CONSOLIDATION))
            rows = cur.fetchall()
            return [{'code': r[0], 'name': r[1], 'status': r[2],
                     'score': r[3], 'notes': r[4]} for r in rows]
        finally:
            conn.close()

    def print_summary(self):
        stats = self.get_stats()
        print(f"\n{'='*50}")
        print(f"扫描状态汇总")
        print(f"{'='*50}")
        print(f"  总记录数:       {stats.get('total', 0)}")
        print(f"  ✅ 不匹配:      {stats.get(STATUS_NO_PATTERN, 0)}")
        print(f"  🔼 上涨观察中:  {stats.get(STATUS_WATCHING_UPTREND, 0)}")
        print(f"  🔍 盘整观察中:  {stats.get(STATUS_WATCHING_CONSOLIDATION, 0)}")
        print(f"  🎯 已匹配:      {stats.get(STATUS_MATCHED, 0)}")
        print(f"  ❌ 错误:        {stats.get(STATUS_ERROR, 0)}")

        watch_list = self.get_watch_list()
        if watch_list:
            print(f"\n观察列表（{len(watch_list)} 只):")
            for i, s in enumerate(watch_list[:10], 1):
                label = "盘整" if s['status'] == STATUS_WATCHING_CONSOLIDATION else "上涨"
                print(f"  {i}. {s['code']} ({s['name']}) [{label}] score={s['score']:.2f}")
            if len(watch_list) > 10:
                print(f"  ... 还有 {len(watch_list) - 10} 只")
        print(f"{'='*50}")
