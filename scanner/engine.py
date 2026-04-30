import threading
import time
from data.fetcher import DataFetcher
from pattern.recognizer import PatternRecognizer
from _config import FACTORY_PATTERN, SCAN


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

    def start(self, limit: int = 0, max_days_back: int = None) -> str:
        with self._lock:
            if self._running:
                return self._task_id
            self._running = True
            self._progress = 0
            self._results = []
            self._errors = 0
            self._current_code = ''
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
            }

    def results(self) -> list:
        with self._lock:
            return sorted(list(self._results), key=lambda x: x.get('pattern_score', 0), reverse=True)

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
                    pattern['stock_code'] = code
                    pattern['stock_name'] = name
                    with self._lock:
                        self._results.append(pattern)
            except Exception as e:
                with self._lock:
                    self._errors += 1

            with self._lock:
                self._progress += 1

        with self._lock:
            self._running = False
