import os
import sys
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from multiprocessing import Pool
from typing import Optional

from data.fetcher import DataFetcher
from config.settings import FACTORY_PATTERN_CONFIG, TRADING_CONFIG
from indicators.technical import TechnicalIndicators
from patterns.factory_pattern import FactoryPatternRecognizer


def _backtest_single(args):
    stock_code, stock_name, start_date, end_date, stride, data_days, buffer_days = args

    if 'ST' in stock_name or '*ST' in stock_name:
        return stock_code, []

    try:
        fetch_start = (datetime.strptime(start_date, '%Y-%m-%d') -
                       timedelta(days=buffer_days)).strftime('%Y-%m-%d')

        fetcher = DataFetcher()
        df = fetcher.get_daily_data_in_range(stock_code, fetch_start, end_date)
        fetcher.close()

        if len(df) < 60:
            return stock_code, []

        df = TechnicalIndicators.calculate_all(df)

        in_range = df[(df['date'] >= pd.to_datetime(start_date)) &
                      (df['date'] <= pd.to_datetime(end_date))]

        if len(in_range) < stride:
            return stock_code, []

        check_points = in_range.iloc[::stride]

        recognizer = FactoryPatternRecognizer(FACTORY_PATTERN_CONFIG)
        results = []

        for _, cp_row in check_points.iterrows():
            check_date = cp_row['date']
            cp_idx = df[df['date'] == check_date].index[0]

            start_idx = max(0, cp_idx - data_days + 1)
            window = df.iloc[start_idx:cp_idx + 1].reset_index(drop=True)

            if len(window) < 60:
                continue

            pattern = recognizer.find_pattern(window)

            if pattern:
                results.append({
                    'check_date': str(check_date.date()),
                    'stock_code': stock_code,
                    'stock_name': stock_name,
                    'uptrend_gain': round(float(pattern.get('uptrend_gain', 0)), 4),
                    'consolidation_days': int(pattern.get('consolidation_days', 0)),
                    'pattern_score': round(float(pattern.get('pattern_score', 0)), 4),
                    'uptrend_start_date': str(pattern.get('uptrend_start_date', '')),
                    'uptrend_end_date': str(pattern.get('uptrend_end_date', '')),
                    'consolidation_end_date': str(pattern.get('consolidation_end_date', '')),
                })

        return stock_code, results

    except Exception as e:
        return stock_code, []


def _load_stock_list(stock_source: str = None, stock_codes: str = None,
                     from_results: str = None, limit: int = None):
    fetcher = DataFetcher()

    if from_results:
        with open(from_results, 'r', encoding='utf-8') as f:
            results = json.load(f)
        stocks = [(r['stock_code'], r.get('stock_name', ''))
                   for r in results if 'stock_code' in r]
        fetcher.close()
        if limit:
            stocks = stocks[:limit]
        return stocks

    if stock_codes:
        codes = [c.strip() for c in stock_codes.split(',')]
        fetcher.close()
        return [(c, '') for c in codes]

    all_stocks = fetcher.get_stock_list_with_names()
    fetcher.close()

    if limit:
        all_stocks = all_stocks[:limit]

    return all_stocks


def run_backtest(stock_source: str = None, stock_codes: str = None,
                 from_results: str = None,
                 start_date: str = None, end_date: str = None,
                 stride: int = 5, data_days: int = 250,
                 num_workers: int = 3, limit: int = None,
                 output_dir: str = 'results'):
    if start_date is None:
        start_date = (datetime.now() - timedelta(days=120)).strftime('%Y-%m-%d')
    if end_date is None:
        end_date = datetime.now().strftime('%Y-%m-%d')

    stock_list = _load_stock_list(stock_source, stock_codes, from_results, limit)
    buffer_days = data_days + 120

    print(f"\n{'='*60}")
    print(f"  厂字形态回测")
    print(f"{'='*60}")
    print(f"  时间段:     {start_date} → {end_date}")
    print(f"  检查频率:   每 {stride} 个交易日")
    print(f"  数据窗口:   最近 {data_days} 个交易日")
    print(f"  股票数量:   {len(stock_list)} 只")
    print(f"  并行进程:   {num_workers}")
    print(f"{'='*60}")

    task_args = [(code, name, start_date, end_date, stride, data_days, buffer_days)
                 for code, name in stock_list]

    all_results = []
    completed = 0

    with Pool(processes=num_workers) as pool:
        for stock_code, stock_results in pool.imap_unordered(_backtest_single, task_args):
            completed += 1
            if stock_results:
                all_results.extend(stock_results)
                for r in stock_results:
                    print(f"  ▶ {r['check_date']} {r['stock_code']}({r['stock_name']}) "
                          f"score={r['pattern_score']:.2f} "
                          f"收益={r['uptrend_gain']:.1%} 盘整={r['consolidation_days']}d")
            if completed % 20 == 0:
                print(f"  进度: {completed}/{len(stock_list)} "
                      f"(已发现 {len(all_results)} 次形态)")

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    json_path = os.path.join(output_dir, f'backtest_{timestamp}.json')
    csv_path = os.path.join(output_dir, f'backtest_{timestamp}.csv')
    os.makedirs(output_dir, exist_ok=True)

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2, default=str)

    if all_results:
        df = pd.DataFrame(all_results)
        df.to_csv(csv_path, index=False, encoding='utf-8-sig')

    print(f"\n{'='*60}")
    print(f"  回测完成!")
    print(f"{'='*60}")

    if not all_results:
        print(f"  在指定时间段内未发现任何形态")
        print(f"  结果: {json_path}")
        return []

    df = pd.DataFrame(all_results)

    total_occurrences = len(df)
    unique_stocks = df['stock_code'].nunique()
    print(f"  总匹配次数:    {total_occurrences}")
    print(f"  涉及股票数:    {unique_stocks}")
    print(f"  平均评分:      {df['pattern_score'].mean():.4f}")
    print(f"  最高评分:      {df['pattern_score'].max():.4f}")
    print(f"  平均涨幅:      {df['uptrend_gain'].mean():.2%}")
    print(f"  平均盘整天数:  {df['consolidation_days'].mean():.1f}")

    stock_summary = df.groupby(['stock_code', 'stock_name']).agg(
        出现次数=('check_date', 'count'),
        平均评分=('pattern_score', 'mean'),
        最高评分=('pattern_score', 'max'),
        平均涨幅=('uptrend_gain', 'mean'),
    ).sort_values('出现次数', ascending=False).reset_index()

    print(f"\n  按股票统计 (出现次数前10):")
    for _, r in stock_summary.head(10).iterrows():
        print(f"    {r['stock_code']}({r['stock_name']}) - "
              f"{int(r['出现次数'])}次 "
              f"均分{r['平均评分']:.2f} "
              f"均涨幅{r['平均涨幅']:.2%}")

    date_summary = df.groupby('check_date').size().sort_index()

    print(f"\n  时间分布 (有匹配的日期):")
    for date_val, count in date_summary.items():
        print(f"    {date_val}: {count} 只")

    print(f"\n  结果文件:")
    print(f"    JSON: {json_path}")
    print(f"    CSV:  {csv_path}")

    return all_results
