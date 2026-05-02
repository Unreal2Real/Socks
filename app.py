import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, jsonify, request, render_template
from data.fetcher import DataFetcher
from pattern.recognizer import PatternRecognizer
from scanner.engine import ScanEngine
from _config import FACTORY_PATTERN, SCAN
from ml import labels, trainer, features as ml_features
from ai.analysis import analyze as ai_analyze

app = Flask(__name__, template_folder='templates', static_folder='.')
app.config['TEMPLATES_AUTO_RELOAD'] = True

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


@app.route('/api/ml/label', methods=['POST'])
def api_ml_label():
    body = request.get_json(force=True, silent=True) or {}
    stock_code = body.get('stock_code', '')
    stock_name = body.get('stock_name', '')
    lbl = body.get('label', '')
    correct_start = body.get('correct_start', '')
    correct_peak = body.get('correct_peak', '')
    correct_end = body.get('correct_end', '')

    if lbl not in ('good', 'bad'):
        return jsonify({'code': 1, 'msg': 'label must be good or bad'})

    if not stock_code:
        return jsonify({'code': 1, 'msg': 'stock_code required'})

    feat = body.get('features') or {}
    record = {
        'stock_code': stock_code,
        'stock_name': stock_name,
        'label': lbl,
        'correct_start': correct_start,
        'correct_peak': correct_peak,
        'correct_end': correct_end,
        'features': feat,
    }

    labels.save_label(record)

    all_labels = labels.load_labels()
    _, metrics = trainer.train_from_labels(all_labels)
    stats = labels.get_stats()

    return jsonify({'code': 0, 'stats': stats, 'metrics': metrics})


@app.route('/api/ml/stats')
def api_ml_stats():
    return jsonify({
        'code': 0,
        'labels': labels.get_stats(),
        'model': trainer.get_model_info(),
    })


@app.route('/api/ml/predict', methods=['POST'])
def api_ml_predict():
    body = request.get_json(force=True, silent=True) or {}
    feat = body.get('features') or {}
    if not feat:
        return jsonify({'code': 1, 'msg': 'features required'})

    prob = trainer.predict(feat)
    return jsonify({'code': 0, 'probability': prob})


@app.route('/api/ml/features/<code>')
def api_ml_features(code):
    df = fetcher.daily_data(code, days=500)
    if df.empty:
        return jsonify({'code': 1, 'msg': 'no data'})

    from indicators.technical import TechnicalIndicators
    df = TechnicalIndicators.calculate_all(df.ffill().bfill())
    pattern = recognizer.find_pattern(df, max_days_back=SCAN.get('max_days_back'))

    if not pattern:
        return jsonify({'code': 0, 'pattern': None, 'features': None})

    feat = ml_features.extract_features(
        df, pattern['uptrend_start_idx'],
        pattern['uptrend_end_idx'],
        pattern['consolidation_end_idx']
    )
    ml_prob = trainer.predict(feat)

    return jsonify({
        'code': 0,
        'pattern': pattern,
        'features': feat,
        'ml_probability': ml_prob,
    })


@app.route('/api/ai/analyze/<code>')
def api_ai_analyze(code):
    if len(code) != 6 or not code.isdigit():
        return jsonify({'code': 1, 'msg': '无效代码'})

    stock_name = ''
    try:
        stocks = fetcher.stock_list()
        for c, n in stocks:
            if c == code:
                stock_name = n
                break
    except Exception:
        pass

    if not stock_name:
        df = fetcher.daily_data(code, days=30)
        if not df.empty:
            try:
                pattern = recognizer.find_pattern(df, max_days_back=SCAN.get('max_days_back'))
                if pattern and pattern.get('stock_name'):
                    stock_name = pattern['stock_name']
            except Exception:
                pass

    try:
        result = ai_analyze(code, stock_name)
        return jsonify({'code': 0, 'data': result})
    except Exception as e:
        return jsonify({'code': 1, 'msg': f'分析失败: {str(e)}'})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5555))
    print(f"服务地址: http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, threaded=True, debug=False)
