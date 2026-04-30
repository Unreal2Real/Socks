import os
import sys
import json
import time
import socket
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, Response
from flask_cors import CORS

socket.setdefaulttimeout(15)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data.providers.factory import create_provider_with_fallback
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


@app.route('/')
def index():
    return app.send_static_file('ui_prototype.html')


@app.route('/api/health')
def health():
    return jsonify({'status': 'ok', 'time': datetime.now().isoformat()})


@app.route('/api/stock/list')
def stock_list():
    try:
        provider = create_provider_with_fallback()
        try:
            stocks = provider.get_stock_list_with_names()
            return jsonify({'code': 0, 'data': [{'code': c, 'name': n} for c, n in stocks]})
        finally:
            provider.close()
    except Exception as e:
        return jsonify({'code': 1, 'msg': f'获取股票列表失败: {str(e)}'})


@app.route('/api/stock/daily')
def stock_daily():
    code = request.args.get('code', '').strip()
    days = int(request.args.get('days', 250))
    if not code:
        return jsonify({'code': 1, 'msg': '缺少code参数'})

    provider = create_provider_with_fallback()
    try:
        df = provider.get_daily_data(code, days=days)
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
        provider.close()


@app.route('/api/stock/intraday')
def stock_intraday():
    code = request.args.get('code', '').strip()
    date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    if not code:
        return jsonify({'code': 1, 'msg': '缺少code参数'})

    provider = create_provider_with_fallback()
    try:
        df = provider.get_minute_data(code, count=100)
        if df.empty:
            return jsonify({'code': 1, 'msg': '无分时数据'})

        data = []
        for _, row in df.iterrows():
            data.append({
                'time': str(row.get('time', '')),
                'open': float(row.get('open', 0)),
                'high': float(row.get('high', 0)),
                'low': float(row.get('low', 0)),
                'close': float(row.get('close', 0)),
                'volume': float(row.get('volume', 0)),
            })
        return jsonify({'code': 0, 'data': data})
    finally:
        provider.close()


@app.route('/api/stock/realtime')
def stock_realtime():
    code = request.args.get('code', '').strip()
    if not code:
        return jsonify({'code': 1, 'msg': '缺少code参数'})

    provider = create_provider_with_fallback()
    try:
        quote = provider.get_realtime_quote(code)
        if not quote:
            return jsonify({'code': 1, 'msg': '无法获取实时报价'})

        return jsonify({'code': 0, 'data': quote})
    finally:
        provider.close()


@app.route('/api/scan/progress')
def scan_progress():
    limit = int(request.args.get('limit', 0))
    
    def generate_scan(limit_val):
        config = make_config({})

        provider = create_provider_with_fallback()
        try:
            all_stocks = provider.get_stock_list_with_names()
            total_stocks = len(all_stocks)
            
            if limit_val > 0:
                stocks = all_stocks[:limit_val]
            else:
                stocks = all_stocks

            matched = []
            count = 0
            last_log_time = time.time()
            log_interval = 0.3
            start_time = time.time()
            scan_total = len(stocks)

            yield f"event: start\ndata: {{'type':'start','total':{scan_total},'total_stocks':{total_stocks},'limit':{limit_val}}}\n\n"

            for code, name in stocks:
                try:
                    df = provider.get_daily_data(code, days=config.get('min_days', 60))
                    if df.empty or len(df) < config.get('min_days', 60):
                        count += 1
                        continue

                    recognizer = FactoryPatternRecognizer(config)
                    pattern = recognizer.find_pattern(df)

                    if pattern:
                        matched.append({
                            'code': code,
                            'name': name,
                            'score': pattern.get('score', 0),
                            'type': pattern.get('type', ''),
                            'days': len(df),
                            'latest_date': df['date'].max().strftime('%Y-%m-%d'),
                            'uptrend_gain': pattern.get('uptrend_gain', 0),
                            'consolidation_days': pattern.get('consolidation_days', 0),
                            'uptrend_start_date': pattern.get('uptrend_start_date', ''),
                            'uptrend_end_date': pattern.get('uptrend_end_date', ''),
                            'consolidation_end_date': pattern.get('consolidation_end_date', '')
                        })
                        yield f"event: match\ndata: {{'type':'match','code':'{code}','name':'{name}','score':{pattern.get('score', 0)}}}\n\n"

                    count += 1

                    current_time = time.time()
                    if current_time - last_log_time >= log_interval:
                        progress = (count / scan_total) * 100 if scan_total > 0 else 0
                        elapsed = current_time - start_time
                        speed = count / elapsed if elapsed > 0 else 0
                        yield f"event: progress\ndata: {{'type':'progress','count':{count},'total':{scan_total},'matched':{len(matched)},'progress':{progress:.1f},'code':'{code}','speed':{speed:.1f}}}\n\n"
                        last_log_time = current_time

                except Exception as e:
                    count += 1
                    continue

            elapsed = time.time() - start_time
            yield f"event: done\ndata: {{'type':'done','count':{count},'total':{scan_total},'matched':{len(matched)},'elapsed':{elapsed:.1f}}}\n\n"

        finally:
            provider.close()

    return Response(generate_scan(limit), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no'
    })


@app.route('/api/scan', methods=['GET', 'POST'])
def scan():
    if request.method == 'POST':
        data = request.get_json() or {}
        limit = data.get('limit', 0)
        batch_size = data.get('batch_size', 50)
        config_overrides = data.get('config', {})
    else:
        limit = int(request.args.get('limit', 0))
        batch_size = int(request.args.get('batch_size', 50))
        config_overrides = {}

    config = make_config(config_overrides)

    provider = create_provider_with_fallback()
    try:
        stocks = provider.get_stock_list_with_names()
        if limit > 0:
            stocks = stocks[:limit]

        results = []
        count = 0

        for code, name in stocks:
            if count >= batch_size and batch_size > 0:
                break

            try:
                df = provider.get_daily_data(code, days=config.get('min_days', 60))
                if df.empty or len(df) < config.get('min_days', 60):
                    continue

                recognizer = FactoryPatternRecognizer(config)
                pattern = recognizer.find_pattern(df)

                if pattern:
                    results.append({
                        'code': code,
                        'name': name,
                        'score': pattern.get('score', 0),
                        'type': pattern.get('type', ''),
                        'days': len(df),
                        'latest_date': df['date'].max().strftime('%Y-%m-%d'),
                        'uptrend_gain': pattern.get('uptrend_gain', 0),
                        'consolidation_days': pattern.get('consolidation_days', 0),
                        'uptrend_start_date': pattern.get('uptrend_start_date', ''),
                        'uptrend_end_date': pattern.get('uptrend_end_date', ''),
                        'consolidation_end_date': pattern.get('consolidation_end_date', '')
                    })
            except Exception as e:
                pass

            count += 1

        return jsonify({
            'code': 0,
            'data': results,
            'scanned': count,
            'total': len(stocks)
        })
    finally:
        provider.close()


@app.route('/api/stock/pattern')
def stock_pattern():
    code = request.args.get('code', '').strip()
    if not code:
        return jsonify({'code': 1, 'msg': '缺少code参数'})

    provider = create_provider_with_fallback()
    try:
        df = provider.get_daily_data(code, days=500)
        if df.empty:
            return jsonify({'code': 1, 'msg': '无数据'})

        config = make_config({})
        recognizer = FactoryPatternRecognizer(config)
        pattern = recognizer.find_pattern(df)

        if pattern:
            return jsonify({
                'code': 0,
                'data': [{
                    'pattern_type': pattern.get('type', 'factory'),
                    'pattern_score': pattern.get('score', 0),
                    'uptrend_start_date': pattern.get('uptrend_start_date', ''),
                    'uptrend_end_date': pattern.get('uptrend_end_date', ''),
                    'consolidation_end_date': pattern.get('consolidation_end_date', ''),
                    'breakout_date': pattern.get('breakout_date', ''),
                    'notes': pattern.get('notes', '')
                }]
            })
        else:
            return jsonify({'code': 0, 'data': []})
    finally:
        provider.close()


@app.route('/api/backtest', methods=['GET', 'POST'])
def backtest():
    if request.method == 'POST':
        data = request.get_json() or {}
        stock_code = data.get('code', '')
        start_date = data.get('start', '')
        end_date = data.get('end', '')
    else:
        stock_code = request.args.get('code', '')
        start_date = request.args.get('start', '')
        end_date = request.args.get('end', '')

    if not stock_code:
        return jsonify({'code': 1, 'msg': '缺少code参数'})

    provider = create_provider_with_fallback()
    try:
        if start_date and end_date:
            df = provider.get_daily_data_in_range(stock_code, start_date, end_date)
        else:
            df = provider.get_daily_data(stock_code, days=500)

        if df.empty:
            return jsonify({'code': 1, 'msg': '无数据'})

        indicators = TechnicalIndicators(df)
        df = indicators.add_all()

        result = {
            'code': stock_code,
            'start_date': df['date'].min().strftime('%Y-%m-%d'),
            'end_date': df['date'].max().strftime('%Y-%m-%d'),
            'total_days': len(df),
            'total_return': ((df['close'].iloc[-1] - df['close'].iloc[0]) / df['close'].iloc[0] * 100),
            'max_drawdown': 0,
            'data': []
        }

        for _, row in df.iterrows():
            result['data'].append({
                'date': row['date'].strftime('%Y-%m-%d'),
                'close': float(row['close']),
                'ma5': float(row.get('ma5', 0)),
                'ma10': float(row.get('ma10', 0)),
                'ma20': float(row.get('ma20', 0)),
                'volume': float(row['volume'])
            })

        return jsonify({'code': 0, 'data': result})
    finally:
        provider.close()


@app.route('/api/cache/stats')
def cache_stats():
    provider = create_provider_with_fallback()
    try:
        stats = provider.get_cache_stats()
        return jsonify({'code': 0, 'data': stats})
    finally:
        provider.close()


@app.route('/api/cache/clear', methods=['POST'])
def cache_clear():
    data = request.get_json() or {}
    stock_code = data.get('code', None)

    provider = create_provider_with_fallback()
    try:
        provider.clear_cache(stock_code)
        return jsonify({'code': 0, 'msg': '缓存已清除'})
    finally:
        provider.close()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5555))
    print(f"启动 API 服务 http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)
