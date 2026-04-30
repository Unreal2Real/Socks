import os
import sys
import json
import argparse
import pandas as pd
from datetime import datetime
from multiprocessing import Pool
from config.settings import FACTORY_PATTERN_CONFIG, TRADING_CONFIG

BATCH_SIZE = 80


def _process_single_stock(provider, stock_code, stock_name):
    if 'ST' in stock_name or '*ST' in stock_name:
        return {'code': stock_code, 'name': stock_name,
                'status': 'no_pattern', 'score': 0,
                'notes': 'ST'}, None

    try:
        df = provider.get_daily_data(stock_code, days=TRADING_CONFIG['data_days'])
        if len(df) < 60:
            return {'code': stock_code, 'name': stock_name,
                    'status': 'no_pattern', 'score': 0,
                    'notes': '数据不足'}, None

        stock_info = {'name': stock_name}
        from filters.stock_filter import StockFilter
        if not StockFilter.apply_filters(df, stock_info=stock_info):
            return {'code': stock_code, 'name': stock_name,
                    'status': 'no_pattern', 'score': 0,
                    'notes': '过滤淘汰'}, None

        from indicators.technical import TechnicalIndicators
        df = TechnicalIndicators.calculate_all(df)

        from patterns.factory_pattern import FactoryPatternRecognizer
        recognizer = FactoryPatternRecognizer(FACTORY_PATTERN_CONFIG)
        pattern = recognizer.find_pattern(df)

        if pattern:
            pattern['stock_code'] = stock_code
            pattern['stock_name'] = stock_name
            for key in ['uptrend_start_date', 'uptrend_end_date',
                        'consolidation_start_date', 'consolidation_end_date']:
                if key in pattern and hasattr(pattern[key], 'strftime'):
                    pattern[key] = str(pattern[key])
            return {'code': stock_code, 'name': stock_name,
                    'status': 'matched', 'score': pattern.get('pattern_score', 0),
                    'notes': f'涨幅{pattern.get("uptrend_gain",0):.1%} 盘整{pattern.get("consolidation_days",0)}天',
                    'pattern_data': pattern}, pattern

        proximity = recognizer.classify_pattern_proximity(df)
        return {'code': stock_code, 'name': stock_name,
                'status': proximity['status'],
                'score': proximity.get('score', 0),
                'notes': proximity.get('notes', '')}, None

    except Exception as e:
        return {'code': stock_code, 'name': stock_name,
                'status': 'error', 'score': 0,
                'notes': str(e)[:80]}, None


def _scan_batch(args):
    batch_id, stocks, source_type = args
    from data.providers.factory import create_provider
    provider = create_provider(source_type)
    try:
        state_updates = []
        matches = []
        for stock_code, stock_name in stocks:
            state_info, pattern = _process_single_stock(provider, stock_code, stock_name)
            state_updates.append(state_info)
            if pattern:
                matches.append(pattern)
        return batch_id, matches, state_updates
    except Exception:
        return batch_id, [], [{'code': c, 'name': n, 'status': 'error',
                                'score': 0, 'notes': 'batch error'} for c, n in stocks]
    finally:
        try:
            provider.close()
        except Exception:
            pass


def save_results(results: list, output_dir: str = 'results', prefix: str = 'patterns'):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    json_path = os.path.join(output_dir, f'{prefix}_{timestamp}.json')
    csv_path = os.path.join(output_dir, f'{prefix}_{timestamp}.csv')

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)

    if results:
        pd.DataFrame(results).to_csv(csv_path, index=False, encoding='utf-8-sig')

    print(f"\n结果已保存:")
    print(f"  JSON: {json_path}")
    print(f"  CSV: {csv_path}")
    return json_path


def cmd_scan(args):
    from data.providers.factory import create_provider_with_fallback
    from data.scan_state import ScanState

    num_workers = args.workers or 3
    state = ScanState()

    print(f"使用数据源: {args.source}")
    provider = create_provider_with_fallback()

    try:
        print("获取股票列表...")
        all_stocks = provider.get_stock_list_with_names()
        print(f"全量股票: {len(all_stocks)} 只")

        if args.limit:
            all_stocks = all_stocks[:args.limit]
            scan_list = all_stocks
        elif args.full:
            scan_list = all_stocks
            print(">>> 全量扫描模式 - 检查所有股票")
        else:
            scan_list = state.get_daily_scan_list(all_stocks)
            skipped = len(all_stocks) - len(scan_list)
            print(f">>> 增量扫描模式 - 需扫描 {len(scan_list)} 只 (跳过 {skipped} 只)")
            state.print_summary()

        if not scan_list:
            print("今天没有需要扫描的股票，休息一下！")
            return

        batches = []
        for i in range(0, len(scan_list), BATCH_SIZE):
            batches.append((i // BATCH_SIZE, scan_list[i:i + BATCH_SIZE], args.source))

        total = len(scan_list)
        print(f"\n开始扫描 (workers: {num_workers}, batch_size: {BATCH_SIZE}, batches: {len(batches)})...")
        print("-" * 60)

        results = []
        all_updates = []
        completed = 0

        with Pool(processes=num_workers) as pool:
            for batch_id, batch_results, batch_updates in pool.imap_unordered(_scan_batch, batches):
                completed += BATCH_SIZE
                completed = min(completed, total)
                print(f"进度: {completed}/{total} ({completed/total*100:.1f}%)")

                for r in batch_results:
                    results.append(r)
                    print(f"  🎯 发现形态: {r.get('stock_code', '?')} ({r.get('stock_name', '')}) "
                          f"- 涨幅: {r.get('uptrend_gain', 0):.2%}, "
                          f"盘整: {r.get('consolidation_days', 0)}天, "
                          f"评分: {r.get('pattern_score', 0):.2f}")
                all_updates.extend(batch_updates)

        state.batch_update_status(all_updates)

        print("-" * 60)
        n_matched = sum(1 for u in all_updates if u['status'] == 'matched')
        n_watch_consol = sum(1 for u in all_updates if u['status'] == 'watching_consolidation')
        n_watch_up = sum(1 for u in all_updates if u['status'] == 'watching_uptrend')
        n_error = sum(1 for u in all_updates if u['status'] == 'error')
        print(f"\n扫描完成! 发现 {len(results)} 只\"厂\"字形态股票.")
        print(f"  新增观察-盘整中: {n_watch_consol} 只")
        print(f"  新增观察-上涨中: {n_watch_up} 只")
        print(f"  错误: {n_error} 只")

        if results:
            json_path = save_results(results, args.output)
            _auto_report(json_path)

        print()
        state.print_summary()

    finally:
        provider.close()


def cmd_backtest(args):
    from backtest import run_backtest

    run_backtest(
        stock_codes=args.stocks,
        from_results=args.from_results,
        start_date=args.start,
        end_date=args.end,
        stride=args.stride,
        data_days=args.data_days,
        num_workers=args.workers or 3,
        limit=args.limit,
        output_dir=args.output,
    )


def cmd_stats(args):
    from data.scan_state import ScanState
    state = ScanState()
    stats = state.get_stats()
    print(f"\n扫描数据库统计:")
    for k, v in stats.items():
        print(f"  {k}: {v}")

    watch_list = state.get_watch_list()
    if watch_list:
        print(f"\n当前观察列表 ({len(watch_list)} 只):")
        for i, s in enumerate(watch_list, 1):
            label = "🔍盘整" if s['status'] == 'watching_consolidation' else "🔼上涨"
            print(f"  {i}. {s['code']} ({s['name']}) {label} score={s['score']:.2f} | {s.get('notes', '')}")


def cmd_watch(args):
    from data.scan_state import ScanState
    ScanState().print_summary()


def cmd_clear(args):
    db_path = os.path.join(os.path.dirname(__file__), 'data', 'scan_state.db')
    val = input(f"确认清空所有扫描状态? (yes/no): ")
    if val == 'yes':
        if os.path.exists(db_path):
            os.remove(db_path)
        print("状态已清空，下次将全量扫描.")


def _auto_report(results_path: str):
    try:
        from report import generate_report
        generate_report(results_path)
    except Exception as e:
        print(f"自动报告生成跳过: {e}")


def main():
    parser = argparse.ArgumentParser(
        description='厂字形态股票分析工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python3 main.py scan                  # 增量扫描（使用默认数据源）
  python3 main.py scan --source baostock # 使用 Baostock API
  python3 main.py scan --source tdx     # 使用本地通达信数据
  python3 main.py scan --full            # 全量扫描
  python3 main.py scan --limit 100       # 调试前100只

  python3 main.py backtest --start 2026-01-01 --end 2026-04-29
  python3 main.py backtest --stocks 603135,301439
  python3 main.py backtest --from results/patterns_xxx.json

  python3 main.py stats                  # 查看状态统计
  python3 main.py watch                  # 查看观察列表
  python3 main.py clear                  # 清空扫描状态
        """
    )
    subparsers = parser.add_subparsers(dest='command', title='子命令')

    p_scan = subparsers.add_parser('scan', help='扫描实时形态')
    p_scan.add_argument('--full', action='store_true', help='全量扫描（默认增量）')
    p_scan.add_argument('--limit', type=int, default=None, help='限制扫描数量')
    p_scan.add_argument('--workers', type=int, default=3, help='并行进程数')
    p_scan.add_argument('--output', default='results', help='输出目录')
    p_scan.add_argument('--source', default='baostock', choices=['baostock', 'tdx'],
                        help='数据源类型: baostock(默认) 或 tdx(本地)')

    p_bt = subparsers.add_parser('backtest', help='历史回测')
    p_bt.add_argument('--start', default=None, help='起始日期 (YYYY-MM-DD)')
    p_bt.add_argument('--end', default=None, help='结束日期 (YYYY-MM-DD)')
    p_bt.add_argument('--stocks', default=None, help='指定股票代码（逗号分隔）')
    p_bt.add_argument('--from', dest='from_results', default=None, help='从结果文件加载股票列表')
    p_bt.add_argument('--stride', type=int, default=5, help='检查步长（交易日）')
    p_bt.add_argument('--data-days', type=int, default=250, help='分析数据窗口')
    p_bt.add_argument('--limit', type=int, default=None, help='限制回测股票数量')
    p_bt.add_argument('--workers', type=int, default=3, help='并行进程数')
    p_bt.add_argument('--output', default='results', help='输出目录')

    p_stats = subparsers.add_parser('stats', help='查看扫描状态统计')
    p_watch = subparsers.add_parser('watch', help='查看观察列表')
    p_clear = subparsers.add_parser('clear', help='清空扫描状态')

    args = parser.parse_args()

    if args.command == 'scan':
        cmd_scan(args)
    elif args.command == 'backtest':
        cmd_backtest(args)
    elif args.command == 'stats':
        cmd_stats(args)
    elif args.command == 'watch':
        cmd_watch(args)
    elif args.command == 'clear':
        cmd_clear(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()