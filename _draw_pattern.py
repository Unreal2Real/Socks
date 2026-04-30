"""Draw clear pattern with zones marked"""
import sys; sys.path.insert(0,'.')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from data.fetcher import DataFetcher
from pattern.recognizer import PatternRecognizer
from _config import FACTORY_PATTERN, SCAN
import pandas as pd
import numpy as np

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei']
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['figure.facecolor'] = '#0f1117'
plt.rcParams['axes.facecolor'] = '#1a1d28'
plt.rcParams['text.color'] = '#d1d4dc'
plt.rcParams['axes.edgecolor'] = '#2a2d3a'
plt.rcParams['xtick.color'] = '#787b86'
plt.rcParams['ytick.color'] = '#787b86'
plt.rcParams['grid.color'] = '#2a2d3a'
plt.rcParams['grid.alpha'] = 0.5

f = DataFetcher()
r = PatternRecognizer(FACTORY_PATTERN)

# Pick stocks with a recent pattern
codes = [
    ('601225', '陕西煤业'),
    ('600971', '恒源煤电'),
]

fig, axes = plt.subplots(len(codes), 1, figsize=(16, 5 * len(codes)))
if len(codes) == 1:
    axes = [axes]

for idx, (code, name) in enumerate(codes):
    ax = axes[idx]
    df = f.daily_data(code, days=500)
    df = df.dropna(subset=['close'])
    df = df.reset_index(drop=True)

    p = r.find_pattern(df, max_days_back=SCAN.get('max_days_back'))

    # Show last 150 days for context
    n = len(df)
    show_start = max(0, n - 150)
    plot_df = df.iloc[show_start:].reset_index(drop=True)
    
    dates = range(len(plot_df))
    ax.plot(dates, plot_df['close'], color='#d1d4dc', linewidth=1.5, zorder=5, label='收盘价')
    ax.fill_between(dates, plot_df['low'], plot_df['high'], color='#d1d4dc', alpha=0.08)
    
    if p:
        p_start_rel = max(0, p['uptrend_start_idx'] - show_start)
        p_peak_rel = max(0, p['uptrend_end_idx'] - show_start)
        p_end_rel = min(len(plot_df)-1, p['consolidation_end_idx'] - show_start)
        
        # Uptrend zone (green background)
        if p_start_rel < len(plot_df) and p_peak_rel < len(plot_df):
            ax.axvspan(p_start_rel, p_peak_rel, alpha=0.12, color='#22c55e', zorder=1)
            ax.text((p_start_rel+p_peak_rel)/2, ax.get_ylim()[0] + (ax.get_ylim()[1]-ax.get_ylim()[0])*0.03,
                    '⬆ 上涨段', ha='center', fontsize=11, color='#22c55e', fontweight='bold')

        # Consolidation zone (blue background)
        if p_peak_rel < len(plot_df) and p_end_rel >= p_peak_rel:
            ax.axvspan(p_peak_rel, p_end_rel, alpha=0.12, color='#3b82f6', zorder=1)
            ax.text((p_peak_rel+p_end_rel)/2, ax.get_ylim()[1] - (ax.get_ylim()[1]-ax.get_ylim()[0])*0.03,
                    '⬛ 盘整段', ha='center', fontsize=11, color='#3b82f6', fontweight='bold')
        
        # Peak marker
        if p_peak_rel < len(plot_df):
            peak_price = plot_df['close'].iloc[p_peak_rel]
            ax.scatter([p_peak_rel], [peak_price], color='#f59e0b', s=80, zorder=10, marker='D')
            ax.annotate(f'峰顶 {peak_price:.1f}', (p_peak_rel, peak_price),
                       xytext=(10, 15), textcoords='offset points', color='#f59e0b',
                       fontsize=10, fontweight='bold',
                       arrowprops=dict(arrowstyle='->', color='#f59e0b', alpha=0.7))
            
            # Draw horizontal line at peak price through consolidation zone
            ax.axhline(y=peak_price, xmin=(p_peak_rel)/len(dates), xmax=(p_end_rel)/len(dates),
                      color='#f59e0b', linewidth=1, linestyle='--', alpha=0.5)
            
            # Retrace line
            consol_data = plot_df['close'].iloc[p_peak_rel:p_end_rel+1]
            min_in_consol = consol_data.min()
            min_idx = p_peak_rel + consol_data.values.argmin()
            
            if min_in_consol < peak_price:
                ax.annotate('', xy=(min_idx, min_in_consol), xytext=(min_idx, peak_price),
                          arrowprops=dict(arrowstyle='<->', color='#ef4444', lw=1.5, alpha=0.8))
                retrace_pct = (peak_price - min_in_consol) / peak_price * 100
                ax.text(min_idx + 2, (peak_price + min_in_consol) / 2,
                       f'回撤 {retrace_pct:.1f}%', fontsize=10, color='#ef4444', fontweight='bold',
                       va='center')
                ax.scatter([min_idx], [min_in_consol], color='#ef4444', s=50, zorder=10)

        # Start marker
        if p_start_rel < len(plot_df):
            ax.scatter([p_start_rel], [plot_df['close'].iloc[p_start_rel]], 
                      color='#22c55e', s=60, zorder=10, marker='^')
        
        # End marker
        if p_end_rel < len(plot_df):
            ax.scatter([p_end_rel], [plot_df['close'].iloc[p_end_rel]], 
                      color='#c084fc', s=60, zorder=10, marker='^')

        # Score box
        is_ongoing = p_end_rel == len(plot_df) - 1
        status_text = '🔄 横盘中' if is_ongoing else '✓ 已完成'
        score_text = f'评分: {p["pattern_score"]:.2f}\n涨幅: +{p["uptrend_gain"]*100:.1f}%\n{status_text}'
        ax.text(0.02, 0.98, score_text, transform=ax.transAxes, fontsize=10,
               verticalalignment='top', color='#d1d4dc',
               bbox=dict(boxstyle='round', facecolor='#1a1d28', edgecolor='#2a2d3a', alpha=0.9))

    # Formatting
    ax.set_title(f'{code} {name}', fontsize=14, color='#fff', fontweight='bold', pad=10)
    ax.grid(True, alpha=0.3)

    # X-axis labels (dates)
    tick_step = max(1, len(plot_df) // 8)
    tick_positions = list(range(0, len(plot_df), tick_step))
    tick_labels = [plot_df.iloc[i]['date'].strftime('%m/%d') if hasattr(plot_df.iloc[i]['date'], 'strftime') else str(plot_df.iloc[i]['date'])[:5] for i in tick_positions]
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels, fontsize=9)

fig.tight_layout()
fig.savefig('pattern_diagram.png', dpi=120, bbox_inches='tight', facecolor='#0f1117')
print('Saved: pattern_diagram.png')
f.close()
