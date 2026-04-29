import os
import json
import pandas as pd
from datetime import datetime
from data.fetcher import DataFetcher
from indicators.technical import TechnicalIndicators
from config.settings import TRADING_CONFIG


def generate_report(results_path: str = None):
    if results_path is None:
        results_dir = 'results'
        json_files = [f for f in os.listdir(results_dir) if f.endswith('.json')]
        if not json_files:
            print("No result files found!")
            return
        results_path = os.path.join(results_dir, sorted(json_files)[-1])

    with open(results_path, 'r', encoding='utf-8') as f:
        patterns = json.load(f)

    if not patterns:
        print("No patterns to report.")
        return

    print(f"Loading {len(patterns)} patterns from {results_path}...")
    patterns.sort(key=lambda x: x.get('pattern_score', 0), reverse=True)

    output_dir = 'report'
    os.makedirs(output_dir, exist_ok=True)
    chart_dir = os.path.join(output_dir, 'charts')
    os.makedirs(chart_dir, exist_ok=True)

    from utils.visualizer import plot_factory_pattern, plot_pattern_grid

    fetcher = DataFetcher()

    for i, pattern in enumerate(patterns):
        stock_code = pattern.get('stock_code', '')
        stock_name = pattern.get('stock_name', '')
        print(f"[{i+1}/{len(patterns)}] Fetching {stock_code} ({stock_name})...")

        df = fetcher.get_daily_data(stock_code, days=TRADING_CONFIG['data_days'])
        if len(df) < 60:
            print(f"  Insufficient data for {stock_code}")
            continue

        df = TechnicalIndicators.calculate_all(df)

        chart_path = os.path.join(chart_dir, f'{stock_code}.png')
        plot_factory_pattern(df, pattern, save_path=chart_path)

    fetcher.close()

    df_dict = {}
    for pattern in patterns:
        stock_code = pattern.get('stock_code', '')
        path = os.path.join(chart_dir, f'{stock_code}.png')
        if os.path.exists(path):
            df_dict[stock_code] = path

    grid_path = os.path.join(output_dir, 'grid_overview.png')
    dummy_df_dict = {}
    for pattern in patterns:
        sc = pattern.get('stock_code', '')
        fetcher2 = DataFetcher()
        d = fetcher2.get_daily_data(sc, days=TRADING_CONFIG['data_days'])
        if len(d) >= 60:
            dummy_df_dict[sc] = TechnicalIndicators.calculate_all(d)
        fetcher2.close()

    plot_pattern_grid(dummy_df_dict, patterns, save_path=grid_path)

    _write_html_report(patterns, df_dict, grid_path, output_dir, results_path)

    print(f"\nReport generated: {output_dir}/index.html")


def _write_html_report(patterns, chart_dict, grid_path, output_dir, results_path):
    sorted_patterns = sorted(patterns, key=lambda x: x.get('pattern_score', 0), reverse=True)

    score_dist = {}
    for p in patterns:
        s = p.get('pattern_score', 0)
        bucket = int(s * 10) / 10
        score_dist[bucket] = score_dist.get(bucket, 0) + 1

    avg_score = sum(p.get('pattern_score', 0) for p in patterns) / len(patterns)
    avg_gain = sum(p.get('uptrend_gain', 0) for p in patterns) / len(patterns)
    avg_days = sum(p.get('consolidation_days', 0) for p in patterns) / len(patterns)

    rows = []
    for i, p in enumerate(sorted_patterns, 1):
        code = p.get('stock_code', '')
        name = p.get('stock_name', '')
        score = p.get('pattern_score', 0)
        gain = p.get('uptrend_gain', 0)
        days = p.get('consolidation_days', 0)

        score_class = 'score-high' if score >= 0.25 else 'score-mid' if score >= 0.15 else 'score-low'
        gain_class = 'gain-up' if gain >= 0.20 else 'gain-mid' if gain >= 0.15 else 'gain-normal'

        chart_src = f'charts/{code}.png'
        has_chart = os.path.exists(os.path.join(output_dir, chart_src))

        chart_cell = ''
        if has_chart:
            chart_cell = f'<a href="{chart_src}" target="_blank"><img src="{chart_src}" class="chart-thumb" loading="lazy"></a>'

        rows.append(f'''
        <tr>
            <td>{i}</td>
            <td><strong>{code}</strong></td>
            <td>{name}</td>
            <td class="{score_class}">{score:.2f}</td>
            <td class="{gain_class}">{gain:.1%}</td>
            <td>{days}天</td>
            <td>{chart_cell}</td>
        </tr>''')

    rows_html = '\n'.join(rows)

    score_dist_html = ''
    for bucket in sorted(score_dist.keys()):
        cnt = score_dist[bucket]
        pct = cnt / len(patterns) * 100
        bar_w = max(20, pct * 3)
        score_dist_html += f'''
        <div class="dist-bar">
            <span class="dist-label">{bucket:.1f} - {bucket+0.1:.1f}</span>
            <div class="dist-track"><div class="dist-fill" style="width:{bar_w}px">{cnt}</div></div>
        </div>'''

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>「厂」字形态扫描报告</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       background: #f5f6fa; color: #2d3436; padding: 0; }}
.header {{ background: linear-gradient(135deg, #2d3436, #636e72);
           color: white; padding: 30px 40px; }}
.header h1 {{ font-size: 28px; margin-bottom: 5px; }}
.header .subtitle {{ font-size: 14px; opacity: 0.8; }}
.container {{ max-width: 1400px; margin: 0 auto; padding: 20px; }}

.summary-cards {{ display: flex; gap: 16px; margin: 20px 0; flex-wrap: wrap; }}
.card {{ background: white; border-radius: 10px; padding: 20px 24px; flex: 1; min-width: 150px;
         box-shadow: 0 2px 8px rgba(0,0,0,0.06); }}
.card .num {{ font-size: 28px; font-weight: bold; color: #2d3436; }}
.card .label {{ font-size: 13px; color: #636e72; margin-top: 4px; }}
.card .num.green {{ color: #00b894; }}
.card .num.orange {{ color: #e17055; }}
.card .num.blue {{ color: #0984e3; }}

.score-dist {{ background: white; border-radius: 10px; padding: 20px; margin: 20px 0;
               box-shadow: 0 2px 8px rgba(0,0,0,0.06); }}
.dist-bar {{ display: flex; align-items: center; margin: 4px 0; }}
.dist-label {{ width: 60px; font-size: 12px; color: #636e72; }}
.dist-track {{ height: 22px; background: #dfe6e9; border-radius: 4px; }}
.dist-fill {{ height: 22px; background: #0984e3; border-radius: 4px; line-height: 22px;
              padding-left: 8px; font-size: 12px; color: white; }}

table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 10px;
         overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.06); margin: 20px 0; }}
th {{ background: #2d3436; color: white; padding: 12px 16px; text-align: left;
      font-size: 13px; font-weight: 600; white-space: nowrap; }}
td {{ padding: 12px 16px; border-bottom: 1px solid #f1f2f6; font-size: 14px; vertical-align: middle; }}
tr:hover {{ background: #f8f9fa; }}
tr:last-child td {{ border-bottom: none; }}

.chart-thumb {{ width: 200px; height: 120px; object-fit: cover; border-radius: 6px;
                border: 1px solid #dfe6e9; transition: all 0.2s; }}
.chart-thumb:hover {{ transform: scale(1.05); box-shadow: 0 4px 16px rgba(0,0,0,0.15); }}

.score-high {{ color: #00b894; font-weight: bold; }}
.score-mid {{ color: #e17055; font-weight: bold; }}
.score-low {{ color: #636e72; }}
.gain-up {{ color: #d63031; font-weight: bold; }}
.gain-mid {{ color: #e17055; }}
.gain-normal {{ color: #636e72; }}

.grid-section {{ margin: 20px 0; }}
.grid-section img {{ width: 100%; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }}

@media (max-width: 768px) {{
    .container {{ padding: 10px; }}
    .card {{ min-width: 100px; }}
    .chart-thumb {{ width: 120px; height: 72px; }}
    th, td {{ padding: 8px 10px; font-size: 12px; }}
}}
</style>
</head>
<body>
<div class="header">
    <h1>📊 「厂」字形态扫描报告</h1>
    <div class="subtitle">
        扫描时间: {_fmt_time()} &nbsp;|&nbsp;
        数据来源: Baostock &nbsp;|&nbsp;
        扫描结果: {results_path}
    </div>
</div>
<div class="container">
    <div class="summary-cards">
        <div class="card">
            <div class="num blue">{len(patterns)}</div>
            <div class="label">匹配形态数量</div>
        </div>
        <div class="card">
            <div class="num orange">{avg_gain:.1%}</div>
            <div class="label">平均上涨幅度</div>
        </div>
        <div class="card">
            <div class="num blue">{avg_days:.0f}天</div>
            <div class="label">平均盘整天数</div>
        </div>
        <div class="card">
            <div class="num green">{avg_score:.2f}</div>
            <div class="label">平均评分</div>
        </div>
    </div>

    <div class="score-dist">
        <h3>评分分布</h3>
        {score_dist_html}
    </div>

    <div class="grid-section">
        <h3>形态总览</h3>
        <a href="grid_overview.png" target="_blank"><img src="grid_overview.png" alt="总览图"></a>
    </div>

    <h3>详细列表</h3>
    <table>
        <thead>
            <tr>
                <th>#</th>
                <th>代码</th>
                <th>名称</th>
                <th>评分</th>
                <th>涨幅</th>
                <th>盘整</th>
                <th>K线图</th>
            </tr>
        </thead>
        <tbody>
            {rows_html}
        </tbody>
    </table>
</div>
</body>
</html>'''

    index_path = os.path.join(output_dir, 'index.html')
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"HTML report saved to {index_path}")


def _fmt_time():
    return datetime.now().strftime('%Y-%m-%d %H:%M')


if __name__ == '__main__':
    generate_report()
