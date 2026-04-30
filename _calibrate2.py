"""Draw 000421 pattern and calibrate"""
import sys; sys.path.insert(0,'.')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from data.fetcher import DataFetcher
from pattern.recognizer import PatternRecognizer
from indicators.technical import TechnicalIndicators
from _config import FACTORY_PATTERN, SCAN
import pandas as pd, numpy as np

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
config = dict(FACTORY_PATTERN)

df = f.daily_data('000421', days=500)
df = TechnicalIndicators.calculate_all(df.ffill().bfill())
n = len(df)

# Calibrated params based on 000421
calibrated = dict(config)
calibrated['max_retrace_pct'] = 0.15
calibrated['uptrend_gain'] = 0.10
calibrated['volatility'] = 0.20
calibrated['bandwidth'] = 0.35

r_cal = PatternRecognizer(calibrated)
p_cal = r_cal.find_pattern(df, max_days_back=SCAN.get('max_days_back'))

# Also try ongoing detection
r_cur = PatternRecognizer(config)
p_cur = r_cur.find_pattern(df, max_days_back=SCAN.get('max_days_back'))

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 10))

for ax, p, title_prefix in [(ax1, p_cur, '当前算法'), (ax2, p_cal, '校准后')]:
    # Show last 150 days
    show_start = max(0, n - 150)
    plot_df = df.iloc[show_start:].reset_index(drop=True)
    dates = range(len(plot_df))
    
    ax.fill_between(dates, plot_df['low'], plot_df['high'], color='#d1d4dc', alpha=0.06)
    ax.plot(dates, plot_df['close'], color='#d1d4dc', linewidth=1.5, label='收盘价')
    ax.plot(dates, plot_df['ma5'], color='#fbbf24', linewidth=0.8, alpha=0.5, label='MA5')
    ax.plot(dates, plot_df['ma10'], color='#60a5fa', linewidth=0.8, alpha=0.5, label='MA10')
    ax.plot(dates, plot_df['ma20'], color='#c084fc', linewidth=0.8, alpha=0.5, label='MA20')
    
    if p:
        p_start_rel = max(0, p['uptrend_start_idx'] - show_start)
        p_peak_rel = max(0, p['uptrend_end_idx'] - show_start)
        p_end_rel = min(len(plot_df)-1, p['consolidation_end_idx'] - show_start)
        
        if p_start_rel < len(plot_df) and p_peak_rel < len(plot_df) and p_peak_rel >= p_start_rel:
            ax.axvspan(p_start_rel, p_peak_rel, alpha=0.15, color='#22c55e')
            ax.text((p_start_rel+p_peak_rel)/2, ax.get_ylim()[0]*1.05,
                    'UP', ha='center', fontsize=12, color='#22c55e', fontweight='bold')
        
        if p_end_rel >= p_peak_rel and p_peak_rel < len(plot_df):
            ax.axvspan(p_peak_rel, p_end_rel, alpha=0.15, color='#3b82f6')
            ax.text((p_peak_rel+p_end_rel)/2, ax.get_ylim()[1]*0.97,
                    'CONSOL', ha='center', fontsize=12, color='#3b82f6', fontweight='bold')
        
        # Peak dot + horizontal line
        if p_peak_rel < len(plot_df):
            peak_price = float(plot_df['close'].iloc[p_peak_rel])
            ax.scatter([p_peak_rel], [peak_price], color='#f59e0b', s=100, zorder=10, marker='D')
            
            # Peak line through consolidation
            ylim = ax.get_ylim()
            ax.hlines(peak_price, p_peak_rel, p_end_rel, colors='#f59e0b', 
                     linestyles='--', linewidth=1, alpha=0.6)
            
            # Retrace marker
            consol_data = plot_df['close'].iloc[p_peak_rel:p_end_rel+1]
            if len(consol_data) > 0:
                min_in_consol = consol_data.min()
                min_rel_idx = p_peak_rel + consol_data.values.argmin()
                
                if min_in_consol < peak_price:
                    retrace_pct = (peak_price - min_in_consol) / peak_price * 100
                    ax.annotate('', xy=(min_rel_idx, min_in_consol), xytext=(min_rel_idx, peak_price),
                              arrowprops=dict(arrowstyle='<->', color='#ef4444', lw=1.8))
                    ax.text(min_rel_idx + 3, (peak_price + min_in_consol)/2,
                           f'{retrace_pct:.1f}%', fontsize=10, color='#ef4444', fontweight='bold', va='center')
                    ax.scatter([min_rel_idx], [min_in_consol], color='#ef4444', s=50, zorder=10)
        
        # Score info
        color_status = '#22c55e' if p['pattern_score'] >= 0.1 else '#ef4444'
        info = f'CALIBRATED\nscore={p["pattern_score"]:.2f}\n' + \
               f'gain={p["uptrend_gain"]:.1%}\n' + \
               f'consol={p["consolidation_days"]}d\n' + \
               f'endo={p["consolidation_end_date"]}'
        ax.text(0.02, 0.98, info, transform=ax.transAxes, fontsize=10, va='top',
               color=color_status, fontweight='bold',
               bbox=dict(boxstyle='round', facecolor='#1a1d28', edgecolor=color_status, alpha=0.9))
    
    # Labels
    ax.set_title(f'{title_prefix}: 000421 南京公用', fontsize=13, color='#fff', fontweight='bold')
    ax.grid(True, alpha=0.3)
    
    tick_step = max(1, len(plot_df) // 8)
    tick_positions = list(range(0, len(plot_df), tick_step))
    tick_labels = [plot_df.iloc[i]['date'].strftime('%m/%d') for i in tick_positions]
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels, fontsize=9)

fig.tight_layout()
fig.savefig('pattern_diagram.png', dpi=120, bbox_inches='tight', facecolor='#0f1117')
print('Saved: pattern_diagram.png')
print()
print('=== 校准报告 ===')
print(f'000421 基准: 上涨 +14.1% / 盘整 15d / 回撤 12.6%')
print()
print(f'当前参数: 回撤=12% → {"MATCH 但 score=0" if p_cur else "MISS"}')
print(f'校淮参数: 回撤=15% → {"MATCH score="+str(p_cal["pattern_score"]) if p_cal else "MISS"}')
print()
print('建议修改 _config.py:')
print('  max_retrace_pct: 0.12 → 0.15  (基于000421回撤12.6%)')
print('  volatility: 0.18 → 0.20       (放宽)')
print('  bandwidth: 0.30 → 0.35        (放宽)')
f.close()
