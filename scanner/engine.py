import json
import os
import threading
import time
from datetime import datetime, timedelta, date as date_type
from data.fetcher import DataFetcher
from pattern.recognizer import PatternRecognizer
from _config import FACTORY_PATTERN, SCAN, PROJECT_ROOT

RESULTS_DIR = os.path.join(PROJECT_ROOT, 'results')


class ScanEngine:

    def __init__(self, fetcher: DataFetcher, recognizer: PatternRecognizer):
        self.fetcher = fetcher
        self.recognizer = recognizer
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        self._task_id = None
        self._progress = 0
        self._total = 0
        self._results = []
        self._errors = 0
        self._current_code = ''
        self._last_scan_time = None
        self._scan_limit = 0
        os.makedirs(RESULTS_DIR, exist_ok=True)

    def start(self, limit: int = 0, max_days_back: int = None) -> str:
        with self._lock:
            if self._running:
                return self._task_id
            self._running = True
            self._progress = 0
            self._results = []
            self._errors = 0
            self._current_code = ''
            self._scan_limit = limit
            import uuid
            self._task_id = uuid.uuid4().hex[:8]

        self._thread = threading.Thread(
            target=self._run, args=(limit, max_days_back), daemon=True)
        self._thread.start()
        return self._task_id

    def stop(self):
        with self._lock:
            self._running = False

    def progress(self) -> dict:
        with self._lock:
            pct = (self._progress / self._total * 100) if self._total > 0 else 0
            return {
                'running': self._running,
                'task_id': self._task_id,
                'progress': self._progress,
                'total': self._total,
                'percent': round(pct, 1),
                'matched': len(self._results),
                'errors': self._errors,
                'current': self._current_code,
                'last_scan': self._last_scan_time,
            }

    def results(self) -> list:
        with self._lock:
            return sorted(list(self._results),
                          key=lambda x: x.get('pattern_score', 0), reverse=True)

    def _save_results(self):
        with self._lock:
            results = list(self._results)
            scan_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            total_scanned = self._progress
            scan_limit = self._scan_limit

        if not results:
            return

        save_data = {
            'scan_time': scan_time,
            'total_scanned': total_scanned,
            'limit': scan_limit,
            'matched': len(results),
            'results': results,
        }

        path = os.path.join(RESULTS_DIR, 'latest_scan.json')
        tmp = path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)

        ts_file = os.path.join(RESULTS_DIR, f"scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(ts_file, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)

        self._last_scan_time = scan_time

    def last_scan(self) -> dict:
        with self._lock:
            results = list(self._results)
            last_scan = self._last_scan_time

        prev_results = {}
        path = os.path.join(RESULTS_DIR, 'latest_scan.json')
        if os.path.exists(path) and not results:
            try:
                prev_data = json.loads(open(path, 'r', encoding='utf-8').read())
                last_scan = prev_data.get('scan_time', '')
                for r in prev_data.get('results', []):
                    prev_results[r['stock_code']] = r
            except Exception:
                pass

        current_codes = set()
        for r in results:
            code = r['stock_code']
            current_codes.add(code)
            prev = prev_results.get(code)
            if prev is None:
                r['status'] = 'new'
            elif prev.get('pattern_score', 0) == r.get('pattern_score', 0):
                r['status'] = 'kept'
            else:
                r['status'] = 'changed'

        for code, r in prev_results.items():
            if code not in current_codes:
                r['status'] = 'exited'
                results.append(r)

        return {
            'last_scan': last_scan,
            'data': sorted(results,
                           key=lambda x: (0 if x.get('status') != 'exited' else 1,
                                          x.get('pattern_score', 0)),
                           reverse=(len([r for r in results if r.get('status') != 'exited']) > 0)),
        }

    def _run(self, limit: int, max_days_back: int):
        stocks = self.fetcher.stock_list()
        if not stocks:
            with self._lock:
                self._running = False
            return

        if limit > 0:
            stocks = stocks[:limit]

        with self._lock:
            self._total = len(stocks)

        for code, name in stocks:
            with self._lock:
                if not self._running:
                    return
                self._current_code = code

            try:
                df = self.fetcher.daily_data(
                    code, days=SCAN['default_days'])
                if df.empty or len(df) < SCAN['min_days']:
                    with self._lock:
                        self._progress += 1
                    continue

                pattern = self.recognizer.find_pattern(
                    df, max_days_back=max_days_back or SCAN.get('max_days_back'))

                if pattern:
                    max_age = SCAN.get('max_pattern_age_days', 30)
                    end_date_str = pattern.get('consolidation_end_date', '')
                    if max_age and end_date_str:
                        try:
                            end_date = date_type.fromisoformat(str(end_date_str)[:10])
                            if (date_type.today() - end_date).days > max_age:
                                pattern = None
                        except Exception:
                            pass

                if pattern:
                    pattern['stock_code'] = code
                    pattern['stock_name'] = name
                    with self._lock:
                        self._results.append(pattern)
            except Exception as e:
                with self._lock:
                    self._errors += 1

            with self._lock:
                self._progress += 1

        self._save_results()

        with self._lock:
            self._running = False
