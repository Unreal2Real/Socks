import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, jsonify, request, render_template
from data.fetcher import DataFetcher
from pattern.recognizer import PatternRecognizer
from scanner.engine import ScanEngine
from _config import FACTORY_PATTERN, SCAN

app = Flask(__name__, template_folder='templates', static_folder='.')

fetcher = DataFetcher()
recognizer = PatternRecognizer(FACTORY_PATTERN)
engine = ScanEngine(fetcher, recognizer)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/health')
def api_health():
    return jsonify({'status': 'ok'})


@app.route('/api/stock/list')
def api_stock_list():
    try:
        stocks = fetcher.stock_list()
        if not stocks:
            raise Exception('无法获取股票列表，请稍后重试')
        return jsonify({'code': 0, 'data': [{'code': c, 'name': n} for c, n in stocks]})
    except Exception as e:
        return jsonify({'code': 1, 'msg': str(e)})


@app.route('/api/stock/<code>')
def api_stock(code):
    if code == 'list':
        return api_stock_list()
    days = int(request.args.get('days', 250))
    df = fetcher.daily_data(code, days=days)
    if df.empty:
        return jsonify({'code': 1, 'msg': '无数据'})

    data = []
    for _, row in df.iterrows():
        d = row['date']
        data.append({
            'time': d.strftime('%Y-%m-%d') if hasattr(d, 'strftime') else str(d)[:10],
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
            'volume': float(row['volume']),
        })

    pattern = recognizer.find_pattern(df, max_days_back=SCAN.get('max_days_back'))

    return jsonify({
        'code': 0,
        'data': data,
        'pattern': pattern,
    })


@app.route('/api/scan/start', methods=['POST'])
def api_scan_start():
    body = request.get_json(force=True, silent=True) or {}
    limit = body.get('limit', SCAN.get('default_limit', 200))
    task_id = engine.start(limit=limit)
    return jsonify({'code': 0, 'task_id': task_id})


@app.route('/api/scan/progress')
def api_scan_progress():
    return jsonify({'code': 0, 'data': engine.progress()})


@app.route('/api/scan/results')
def api_scan_results():
    return jsonify({'code': 0, 'data': engine.results()})


@app.route('/api/scan/last')
def api_scan_last():
    return jsonify({'code': 0, 'data': engine.last_scan()})


@app.route('/api/scan/stop', methods=['POST'])
def api_scan_stop():
    engine.stop()
    return jsonify({'code': 0})


@app.route('/api/cache/stats')
def api_cache_stats():
    return jsonify({'code': 0, 'data': fetcher.cache_stats()})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5555))
    print(f"服务地址: http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, threaded=True, debug=False)
