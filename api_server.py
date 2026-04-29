import os
import sys
import json
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
from flask_cors import CORS

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data.fetcher import DataFetcher
from indicators.technical import TechnicalIndicators
from patterns.factory_pattern import FactoryPatternRecognizer
from config.settings import FACTORY_PATTERN_CONFIG, TRADING_CONFIG

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)


def make_config(overrides: dict) -> dict:
    cfg = dict(FACTORY_PATTERN_CONFIG)
    for k, v in overrides.items():
        if k in cfg:
            cfg[k] = v
    return cfg


@app.route('/api/health')
def health():
    return jsonify({'status': 'ok', 'time': datetime.now().isoformat()})


@app.route('/api/stock/list')
def stock_list():
    fetcher = DataFetcher()
    try:
        stocks = fetcher.get_stock_list_with_names()
        return jsonify({'code': 0, 'data': [{'code': c, 'name': n} for c, n in stocks]})
    finally:
        fetcher.close()


@app.route('/api/stock/daily')
def stock_daily():
    code = request.args.get('code', '').strip()
    days = int(request.args.get('days', 250))
    if not code:
        return jsonify({'code': 1, 'msg': '缺少code参数'})

    fetcher = DataFetcher()
    try:
        df = fetcher.get_daily_data(code, days=days)
        if df.empty:
            return jsonify({'code': 1, 'msg': '无数据'})

        data = []
        for _, row in df.iterrows():
            d = row['date']
            if hasattr(d, 'strftime'):
                date_str = d.strftime('%Y-%m-%d')
            else:
                date_str = str(d)[:10]
            data.append({
                'time': date_str,
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': float(row['volume']),
            })
        return jsonify({'code': 0, 'data': data})
    finally:
        fetcher.close()


@app.route('/api/stock/intraday')
def stock_intraday():
    code = request.args.get('code', '').strip()
    date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    if not code:
        return jsonify({'code': 1, 'msg': '缺少code参数'})

    fetcher = DataFetcher()
    try:
        bs_code = fetcher._to_bs_code(fetcher._format_stock_code(code))
        rs = fetcher._query(
            bs_code,
            "date,time,open,high,low,close,volume",
            start_date=date,
            end_date=date,
            frequency="5"
        )
        rows = []
        while rs.next():
            rows.append(rs.get_row_data())

        if not rows:
            return jsonify({'code': 0, 'data': []})

        data = []
        for row in rows:
            if len(row) < 6 or not row[1]:
                continue
            try:
                price = float(row[5]) if row[5] not in ('', 'None') else 0
                data.append({
                    'time': f"{row[0]} {row[1][:4]}",
                    'value': price,
                    'open': float(row[2]) if row[2] not in ('', 'None') else price,
                    'high': float(row[3]) if row[3] not in ('', 'None') else price,
                    'low': float(row[4]) if row[4] not in ('', 'None') else price,
                    'close': price,
                    'volume': float(row[6]) if row[6] not in ('', 'None') else 0,
                })
            except (ValueError, TypeError):
                continue

        return jsonify({'code': 0, 'data': data})
    except Exception as e:
        return jsonify({'code': 1, 'msg': str(e)})
    finally:
        fetcher.close()


@app.route('/api/stock/pattern')
def stock_pattern():
    code = request.args.get('code', '').strip()
    if not code:
        return jsonify({'code': 1, 'msg': '缺少code参数'})

    overrides = {}
    for k in ['uptrend_gain', 'consolidation_days_min', 'consolidation_days_max',
              'bandwidth', 'volatility', 'volume_ratio']:
        v = request.args.get(k)
        if v is not None:
            try:
                overrides[k] = float(v)
            except ValueError:
                pass

    cfg = make_config(overrides)
    fetcher = DataFetcher()
    try:
        df = fetcher.get_daily_data(code, days=TRADING_CONFIG['data_days'])
        if df.empty or len(df) < 60:
            return jsonify({'code': 1, 'msg': '数据不足'})

        df = TechnicalIndicators.calculate_all(df)
        recognizer = FactoryPatternRecognizer(cfg)
        all_phases = []

        for i in range(20, len(df) - cfg.get('consolidation_days_max', 40) - 1):
            if recognizer._is_uptrend_start(df, i):
                uptrend_result = recognizer._scan_uptrend(df, i)
                if uptrend_result:
                    uptrend_end_idx, uptrend_gain = uptrend_result
                    consolidation_result = recognizer._scan_consolidation(df, uptrend_end_idx)
                    if consolidation_result:
                        consol_end_idx, consol_days = consolidation_result
                        score = recognizer._calculate_pattern_score(
                            df, i, uptrend_end_idx, consol_end_idx)

                        def fmt(idx):
                            d = df.loc[idx, 'date']
                            return d.strftime('%Y-%m-%d') if hasattr(d, 'strftime') else str(d)[:10]

                        all_phases.append({
                            'phase_index': len(all_phases),
                            'uptrend_start': fmt(i),
                            'uptrend_end': fmt(uptrend_end_idx),
                            'consolidation_end': fmt(consol_end_idx),
                            'uptrend_gain': round(uptrend_gain, 4),
                            'consolidation_days': consol_days,
                            'pattern_score': round(score, 4),
                            'uptrend_start_idx': int(i),
                            'uptrend_end_idx': int(uptrend_end_idx),
                            'consolidation_end_idx': int(consol_end_idx),
                        })

        return jsonify({'code': 0, 'data': all_phases})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'code': 1, 'msg': str(e)})
    finally:
        fetcher.close()


@app.route('/api/scan')
def scan():
    from data.scan_state import ScanState
    from multiprocessing import Pool

    fetcher = DataFetcher()
    try:
        all_stocks = fetcher.get_stock_list_with_names()
    finally:
        fetcher.close()

    BATCH_SIZE = 80

    def process_one(item):
        code, name = item
        if 'ST' in name or '*ST' in name:
            return {'code': code, 'name': name, 'status': 'no_pattern', 'score': 0, 'notes': 'ST'}, None
        try:
            f = DataFetcher()
            df = f.get_daily_data(code, days=TRADING_CONFIG['data_days'])
            f.close()
            if len(df) < 60:
                return {'code': code, 'name': name, 'status': 'no_pattern', 'score': 0, 'notes': '数据不足'}, None

            from filters.stock_filter import StockFilter
            if not StockFilter.apply_filters(df, stock_info={'name': name}):
                return {'code': code, 'name': name, 'status': 'no_pattern', 'score': 0, 'notes': '过滤淘汰'}, None

            df = TechnicalIndicators.calculate_all(df)
            recognizer = FactoryPatternRecognizer(FACTORY_PATTERN_CONFIG)
            pattern = recognizer.find_pattern(df)

            if pattern:
                pattern['stock_code'] = code
                pattern['stock_name'] = name
                for key in ['uptrend_start_date', 'uptrend_end_date',
                            'consolidation_start_date', 'consolidation_end_date']:
                    if key in pattern and hasattr(pattern[key], 'strftime'):
                        pattern[key] = str(pattern[key])
                return {'code': code, 'name': name,
                        'status': 'matched', 'score': pattern.get('pattern_score', 0),
                        'notes': f'涨幅{pattern.get("uptrend_gain", 0):.1%} 盘整{pattern.get("consolidation_days", 0)}天',
                        'pattern_data': pattern}, pattern

            proximity = recognizer.classify_pattern_proximity(df)
            return {'code': code, 'name': name,
                    'status': proximity['status'],
                    'score': proximity.get('score', 0),
                    'notes': proximity.get('notes', '')}, None
        except Exception as e:
            return {'code': code, 'name': name, 'status': 'error', 'score': 0, 'notes': str(e)[:80]}, None

    matched = []
    updates = []
    total = len(all_stocks)

    with Pool(processes=3) as pool:
        for r, pat in pool.imap(process_one, all_stocks):
            updates.append(r)
            if pat:
                matched.append(pat)

    return jsonify({
        'code': 0,
        'total': total,
        'matched_count': len(matched),
        'matched': matched,
        'updates': updates,
    })


if __name__ == '__main__':
    print('启动 API 服务 http://localhost:5555')
    app.run(host='0.0.0.0', port=5555, debug=False, threaded=True)
