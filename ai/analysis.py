"""
AI-powered fundamental analysis engine.
Uses rule-based scoring for instant results, with optional LLM enhancement.
"""
from data.fundamental import FundamentalData
from typing import Optional
import json

_fundamental = None


def _get_fundamental():
    global _fundamental
    if _fundamental is None:
        _fundamental = FundamentalData()
    return _fundamental


def analyze(code: str, stock_name: str = '') -> dict:
    fd = _get_fundamental()
    summary = fd.get_fundamental_summary(code)

    growth = summary.get('growth', {})
    profit = summary.get('profit', {})
    balance = summary.get('balance', {})
    industry = summary.get('industry', {})

    signals = []
    score = 0
    max_score = 0

    profit_yoy = growth.get('profit_yoy')

    if profit_yoy is not None:
        max_score += 2
        pct = profit_yoy * 100
        if profit_yoy > 0.5:
            signals.append({'type': 'positive', 'text': f'利润高速增长 {pct:.1f}%', 'weight': 2})
            score += 2
        elif profit_yoy > 0.15:
            signals.append({'type': 'positive', 'text': f'利润稳健增长 {pct:.1f}%', 'weight': 1})
            score += 1
        elif profit_yoy > 0:
            signals.append({'type': 'neutral', 'text': f'利润微增 {pct:.1f}%', 'weight': 0})
        elif profit_yoy > -0.1:
            signals.append({'type': 'neutral', 'text': f'利润小幅下滑 {pct:.1f}%', 'weight': 0})
        else:
            signals.append({'type': 'negative', 'text': f'利润大幅下滑 {pct:.1f}%', 'weight': -1})

    roe = profit.get('roe')
    if roe is not None:
        max_score += 2
        roe_pct = roe * 100
        if roe > 0.20:
            signals.append({'type': 'positive', 'text': f'ROE优秀 {roe_pct:.1f}%', 'weight': 2})
            score += 2
        elif roe > 0.10:
            signals.append({'type': 'positive', 'text': f'ROE良好 {roe_pct:.1f}%', 'weight': 1})
            score += 1
        elif roe > 0.05:
            signals.append({'type': 'neutral', 'text': f'ROE一般 {roe_pct:.1f}%', 'weight': 0})
        else:
            signals.append({'type': 'negative', 'text': f'ROE偏低 {roe_pct:.1f}%', 'weight': -1})

    gross_margin = profit.get('gross_margin')
    if gross_margin is not None:
        max_score += 1
        gm_pct = gross_margin * 100
        if gross_margin > 0.40:
            signals.append({'type': 'positive', 'text': f'毛利率高 {gm_pct:.1f}%', 'weight': 1})
            score += 1
        elif gross_margin > 0.20:
            signals.append({'type': 'neutral', 'text': f'毛利率 {gm_pct:.1f}%', 'weight': 0})
        else:
            signals.append({'type': 'negative', 'text': f'毛利率低 {gm_pct:.1f}%', 'weight': -1})

    debt_ratio = balance.get('debt_ratio')
    if debt_ratio is not None:
        max_score += 1
        dr_pct = debt_ratio * 100
        if debt_ratio > 0.70:
            signals.append({'type': 'negative', 'text': f'负债率高 {dr_pct:.1f}%', 'weight': -1})
        elif debt_ratio > 0.40:
            signals.append({'type': 'neutral', 'text': f'负债率 {dr_pct:.1f}%', 'weight': 0})
        else:
            signals.append({'type': 'positive', 'text': f'负债率低 {dr_pct:.1f}%', 'weight': 1})
            score += 1

    current_ratio = balance.get('current_ratio')
    if current_ratio is not None:
        max_score += 1
        if current_ratio < 1:
            signals.append({'type': 'negative', 'text': '流动比率不足 %.2f' % current_ratio, 'weight': -1})
        elif current_ratio > 2:
            signals.append({'type': 'positive', 'text': '流动性充裕 %.2f' % current_ratio, 'weight': 1})
            score += 1
        else:
            signals.append({'type': 'neutral', 'text': '流动比率 %.2f' % current_ratio, 'weight': 0})

    eps = profit.get('eps')
    if eps is not None:
        max_score += 1
        if eps > 1:
            signals.append({'type': 'positive', 'text': 'EPS %.2f (盈利能力好)' % eps, 'weight': 1})
            score += 1
        elif eps > 0.2:
            signals.append({'type': 'neutral', 'text': 'EPS %.2f' % eps, 'weight': 0})
        elif eps > 0:
            signals.append({'type': 'negative', 'text': 'EPS极低 %.3f' % eps, 'weight': -1})
        else:
            signals.append({'type': 'negative', 'text': '亏损 EPS %.2f' % eps, 'weight': -2})

    bps = profit.get('bps')
    if bps is not None and eps is not None and eps > 0:
        if bps > 0:
            pe = bps / eps if eps > 0 else 0
            signals.append({'type': 'info', 'text': '每股净资产 %.2f (PB约%.1f)' % (bps, pe), 'weight': 0})

    ind_name = industry.get('industry', '')
    if ind_name:
        signals.append({'type': 'info', 'text': '行业: ' + ind_name, 'weight': 0})

    ratio = (score / max_score * 100) if max_score > 0 else 50
    if ratio >= 75:
        grade = 'A'
        verdict = '基本面优秀，建议重点关注'
        icon = '🟢'
    elif ratio >= 55:
        grade = 'B'
        verdict = '基本面良好，可以适当关注'
        icon = '🟡'
    elif ratio >= 35:
        grade = 'C'
        verdict = '基本面一般，需结合技术面判断'
        icon = '🟠'
    else:
        grade = 'D'
        verdict = '基本面偏弱，建议谨慎'
        icon = '🔴'

    positive = [s for s in signals if s['type'] == 'positive']
    negative = [s for s in signals if s['type'] == 'negative']
    neutral = [s for s in signals if s['type'] == 'neutral']
    info = [s for s in signals if s['type'] == 'info']

    analysis_text = '【%s %s】%s\n' % (stock_name or code, '基本面评级: ' + grade, verdict)
    analysis_text += '\n✅ 亮点:\n'
    for s in positive:
        analysis_text += '  · ' + s['text'] + '\n'
    if not positive:
        analysis_text += '  (无明显亮点)\n'
    analysis_text += '\n⚠️ 风险:\n'
    for s in negative:
        analysis_text += '  · ' + s['text'] + '\n'
    if not negative:
        analysis_text += '  (无明显风险)\n'
    if info:
        analysis_text += '\nℹ 信息:\n'
        for s in info:
            analysis_text += '  · ' + s['text'] + '\n'

    return {
        'code': code,
        'stock_name': stock_name,
        'grade': grade,
        'score_ratio': round(ratio, 1),
        'score': score,
        'max_score': max_score,
        'verdict': verdict,
        'icon': icon,
        'analysis_text': analysis_text,
        'signals': signals,
        'positive_count': len(positive),
        'negative_count': len(negative),
        'raw_data': {
            'growth': growth,
            'profit': profit,
            'balance': balance,
            'industry': industry,
        },
    }
