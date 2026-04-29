import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.patches as mpatches
import matplotlib.font_manager as fm
import pandas as pd
import numpy as np
from typing import Optional


def _setup_zh_font():
    try:
        plt.rcParams['font.sans-serif'] = ['PingFang HK', 'PingFang SC', 'Heiti SC',
                                            'STHeiti', 'Microsoft YaHei', 'Apple SD Gothic Neo']
        plt.rcParams['axes.unicode_minus'] = False
    except Exception:
        pass


_setup_zh_font()


def plot_candlestick(ax, df, start_idx, end_idx):
    plot_df = df.iloc[start_idx:end_idx]
    dates = mdates.date2num(plot_df['date'].values)
    width = 0.6

    for i in range(len(plot_df)):
        d = dates[i]
        o, h, l, c = (plot_df.iloc[i]['open'],
                       plot_df.iloc[i]['high'],
                       plot_df.iloc[i]['low'],
                       plot_df.iloc[i]['close'])

        color = 'red' if c >= o else 'green'
        ax.plot([d, d], [l, h], color=color, linewidth=1)
        ax.bar(d, abs(c - o), bottom=min(o, c), width=width,
               color=color, edgecolor=color, linewidth=0.5)


def _ensure_datetime(val):
    if isinstance(val, str):
        return pd.to_datetime(val)
    return val


def plot_factory_pattern(df: pd.DataFrame, pattern: dict, save_path: Optional[str] = None):
    if pattern is None:
        print("No pattern to plot")
        return

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10),
                                    gridspec_kw={'height_ratios': [3, 1]})

    pad = 30
    start_idx = max(0, pattern['uptrend_start_idx'] - pad)
    end_idx = min(len(df), pattern['consolidation_end_idx'] + 10)
    plot_df = df.iloc[start_idx:end_idx].copy()

    plot_candlestick(ax1, df, start_idx, end_idx)

    for ma_name, color, lw in [('ma5', '#FF6B35', 1.5),
                                 ('ma10', '#004EFF', 1.5),
                                 ('ma20', '#8B4513', 1.5)]:
        if ma_name in plot_df.columns:
            ax1.plot(plot_df['date'], plot_df[ma_name],
                     label=ma_name.upper(), linewidth=lw, color=color, alpha=0.9)

    if 'bb_upper' in plot_df.columns:
        ax1.plot(plot_df['date'], plot_df['bb_upper'],
                 linewidth=0.8, linestyle='--', alpha=0.4, color='gray')
        ax1.plot(plot_df['date'], plot_df['bb_lower'],
                 linewidth=0.8, linestyle='--', alpha=0.4, color='gray')
        ax1.plot(plot_df['date'], plot_df['bb_middle'],
                 linewidth=0.8, linestyle=':', alpha=0.4, color='gray')

    uptrend_start = _ensure_datetime(pattern['uptrend_start_date'])
    uptrend_end = _ensure_datetime(pattern['uptrend_end_date'])
    consolidation_end = _ensure_datetime(pattern['consolidation_end_date'])

    ax1.axvline(x=uptrend_start, color='#00AA00', linestyle='--',
                alpha=0.8, linewidth=1.5, label='上涨起点')
    ax1.axvline(x=uptrend_end, color='#FF4444', linestyle='--',
                alpha=0.8, linewidth=1.5, label='上涨终点')
    ax1.axvline(x=consolidation_end, color='#4444FF', linestyle='--',
                alpha=0.8, linewidth=1.5, label='盘整终点')

    ymin, ymax = ax1.get_ylim()
    ax1.fill_between(plot_df['date'], ymin, ymax,
                     where=(plot_df['date'] >= uptrend_start)
                           & (plot_df['date'] <= uptrend_end),
                     color='green', alpha=0.06)
    ax1.fill_between(plot_df['date'], ymin, ymax,
                     where=(plot_df['date'] > uptrend_end)
                           & (plot_df['date'] <= consolidation_end),
                     color='orange', alpha=0.06)

    mid_x = uptrend_start + (uptrend_end - uptrend_start) / 2
    ax1.annotate('上涨段\n' + f"{pattern['uptrend_gain']:.1%}",
                 xy=(mid_x, ymax), fontsize=11, color='#00AA00',
                 ha='center', va='bottom', fontweight='bold',
                 bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.8))

    mid_cx = uptrend_end + (consolidation_end - uptrend_end) / 2
    ax1.annotate('横盘整理\n' + f"{pattern['consolidation_days']}天",
                 xy=(mid_cx, ymax), fontsize=11, color='#FF8C00',
                 ha='center', va='bottom', fontweight='bold',
                 bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.8))

    score = pattern['pattern_score']
    score_color = '#00AA00' if score >= 0.25 else '#FF8C00' if score >= 0.15 else '#FF4444'
    code = pattern.get('stock_code', '')
    name = pattern.get('stock_name', '')
    ax1.set_title(f"「厂」字形态 — {code} ({name})    评分: {score:.2f}    "
                  f"涨幅: {pattern['uptrend_gain']:.1%}    盘整: {pattern['consolidation_days']}天",
                  fontsize=14, fontweight='bold', color='#333')
    ax1.set_ylabel('价格')
    ax1.legend(loc='upper left', fontsize=8, ncol=3)
    ax1.grid(True, alpha=0.2)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)

    ax2.bar(plot_df['date'], plot_df['volume'], label='成交量',
            color='#4A90D9', alpha=0.5, width=1)
    if 'volume_ma' in plot_df.columns:
        ax2.plot(plot_df['date'], plot_df['volume_ma'],
                 label='成交量均线(20)', color='#FF6B35', linewidth=1.5)

    ax2.set_ylabel('成交量')
    ax2.legend(loc='upper left', fontsize=8)
    ax2.grid(True, alpha=0.2)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"  Chart saved to {save_path}")
    else:
        plt.show()

    plt.close()


def plot_pattern_grid(df_dict, patterns, save_path: str):
    n = len(patterns)
    if n == 0:
        return

    cols = 3
    rows = (n + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(18, rows * 5))
    axes = axes.flatten() if rows * cols > 1 else [axes]

    for i, pattern in enumerate(patterns):
        ax = axes[i]
        stock_code = pattern.get('stock_code', '')
        name = pattern.get('stock_name', '')
        df = df_dict.get(stock_code)
        if df is None or len(df) == 0:
            ax.text(0.5, 0.5, f"{stock_code}\nNo data", ha='center', va='center')
            continue

        pad = 20
        si = max(0, pattern['uptrend_start_idx'] - pad)
        ei = min(len(df), pattern['consolidation_end_idx'] + 5)

        plot_candlestick(ax, df, si, ei)

        for ma_name, color in [('ma5', '#FF6B35'), ('ma10', '#004EFF')]:
            if ma_name in df.columns:
                ax.plot(df.iloc[si:ei]['date'], df.iloc[si:ei][ma_name],
                        linewidth=1, color=color, alpha=0.8)

        uts = _ensure_datetime(pattern['uptrend_start_date'])
        ute = _ensure_datetime(pattern['uptrend_end_date'])
        ce = _ensure_datetime(pattern['consolidation_end_date'])
        ax.axvline(x=ute, color='#FF4444', linestyle='--', alpha=0.6, linewidth=1)

        ymin, ymax = ax.get_ylim()
        ax.fill_between(df.iloc[si:ei]['date'], ymin, ymax,
                        where=(df.iloc[si:ei]['date'] >= uts)
                              & (df.iloc[si:ei]['date'] <= ute),
                        color='green', alpha=0.05)
        ax.fill_between(df.iloc[si:ei]['date'], ymin, ymax,
                        where=(df.iloc[si:ei]['date'] > ute)
                              & (df.iloc[si:ei]['date'] <= ce),
                        color='orange', alpha=0.05)

        score = pattern.get('pattern_score', 0)
        ax.set_title(f"{stock_code} {name}\n{pattern.get('uptrend_gain', 0):.1%} | "
                     f"{pattern.get('consolidation_days', 0)}天 | {score:.2f}",
                     fontsize=9, fontweight='bold')
        ax.grid(True, alpha=0.15)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, fontsize=7)

    for j in range(i + 1, len(axes)):
        axes[j].axis('off')

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    print(f"Grid chart saved to {save_path}")
    plt.close()


def plot_stock_with_indicators(df: pd.DataFrame, stock_code: str = "",
                                save_path: Optional[str] = None):
    if len(df) == 0:
        print("No data to plot")
        return

    fig, axes = plt.subplots(3, 1, figsize=(15, 12),
                              gridspec_kw={'height_ratios': [3, 1, 1]})

    ax1 = axes[0]
    plot_candlestick(ax1, df, 0, len(df))

    for ma_name, color in [('ma5', '#FF6B35'), ('ma10', '#004EFF'),
                            ('ma20', '#8B4513'), ('ma60', '#888888')]:
        if ma_name in df.columns:
            ax1.plot(df['date'], df[ma_name],
                     label=ma_name.upper(), linewidth=1, color=color)

    if 'bb_upper' in df.columns:
        ax1.fill_between(df['date'], df['bb_lower'], df['bb_upper'],
                         alpha=0.08, color='gray')
        ax1.plot(df['date'], df['bb_upper'], linestyle='--',
                 alpha=0.4, color='gray', linewidth=0.5)
        ax1.plot(df['date'], df['bb_lower'], linestyle='--',
                 alpha=0.4, color='gray', linewidth=0.5)

    ax1.set_title(f'{stock_code} — 日K线图', fontsize=14, fontweight='bold')
    ax1.set_ylabel('价格')
    ax1.legend(loc='upper left', fontsize=8)
    ax1.grid(True, alpha=0.2)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)

    ax2 = axes[1]
    if 'bb_bandwidth' in df.columns:
        ax2.plot(df['date'], df['bb_bandwidth'],
                 label='布林带宽度', color='purple', linewidth=1)
        ax2.axhline(y=0.15, color='red', linestyle='--', alpha=0.5)
        ax2.set_ylabel('带宽')
        ax2.legend(loc='upper left')
        ax2.grid(True, alpha=0.2)
        ax2.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
        plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45)

    ax3 = axes[2]
    ax3.bar(df['date'], df['volume'], label='成交量',
            color='#4A90D9', alpha=0.5, width=1)
    if 'volume_ma' in df.columns:
        ax3.plot(df['date'], df['volume_ma'],
                 label='均量线(20)', color='red', linewidth=1.5)
    ax3.set_ylabel('成交量')
    ax3.legend(loc='upper left')
    ax3.grid(True, alpha=0.2)
    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"  Chart saved to {save_path}")
    else:
        plt.show()

    plt.close()
