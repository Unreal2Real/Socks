"""Deep reflection: diagnose ALL candidates for ALL 8 stocks"""
import sys; sys.path.insert(0,'.')
import pandas as pd
from data.fetcher import DataFetcher
from indicators.technical import TechnicalIndicators
from _config import FACTORY_PATTERN

f = DataFetcher()
config = FACTORY_PATTERN

expected = {
    '603629': ('2026-01-21', '2026-02-12', '2026-04-07'),
    '002008': ('2026-02-12', '2026-03-02', '2026-04-07'),
    '300136': ('2025-12-24', '2026-01-22', '2026-04-13'),
    '002796': ('2025-12-16', '2026-01-28', '2026-02-12'),
    '003036': ('2025-06-16', '2025-08-06', '2026-03-17'),
    '002149': ('2025-12-01', '2026-01-12', '2026-04-14'),
    '002655': ('2026-02-10', '2026-03-02', '2026-04-02'),
    '002980': ('2026-02-25', '2026-03-11', '2026-03-27'),
}

for code, (u_start, u_end, c_end) in expected.items():
    print(f'=== {code} (expected: {u_start}→{u_end}→{c_end}) ===')
    df = f.daily_data(code, days=1000 if code == '003036' else 500)
    df = TechnicalIndicators.calculate_all(df.ffill().bfill())
    n = len(df)
    last_date = df.iloc[-1]['date'].date()

    us_ts = pd.Timestamp(u_start)
    ue_ts = pd.Timestamp(u_end)
    ce_ts = pd.Timestamp(c_end)

    # Find ALL valid uptrend→consolidation candidates
    candidates = []
    for si in range(n - config['consolidation_days_min'] - 1, 20, -1):
        sp = float(df.loc[si, 'close'])
        peak_idx = si
        pp = sp
        below = 0

        for k in range(si + 1, n - config['consolidation_days_min']):
            cur = float(df.loc[k, 'close'])
            if cur > pp:
                pp = cur
                peak_idx = k
            if df.loc[k, 'close'] < df.loc[k, 'ma5']:
                below += 1
                if below >= 3 and pp > sp:
                    gain = (pp - sp) / sp
                    up_days = peak_idx - si + 1
                    if gain >= config['uptrend_gain'] and up_days >= config['uptrend_min_days']:
                        # Check consolidation
                        for ei in range(peak_idx + config['consolidation_days_min'],
                                       min(peak_idx + 180, n)):
                            min_c = float(df.loc[peak_idx:ei, 'close'].min())
                            elev = (min_c - sp) / sp
                            if elev >= config['min_elevation']:
                                sd = df.loc[si, 'date'].date()
                                pd_ = df.loc[peak_idx, 'date'].date()
                                ed = df.loc[ei, 'date'].date()
                                s_off = abs((sd - us_ts.date()).days)
                                p_off = abs((pd_ - ue_ts.date()).days)
                                e_off = abs((ed - ce_ts.date()).days)
                                candidates.append({
                                    'sd': sd, 'pd': pd_, 'ed': ed,
                                    'gain': gain, 'up_days': up_days,
                                    'consol_days': ei - peak_idx,
                                    'efficiency': gain / max(up_days, 1),
                                    's_off': s_off, 'p_off': p_off, 'e_off': e_off,
                                    'si': si, 'pi': peak_idx, 'ei': ei,
                                })
                                break
                    break
            else:
                below = 0

    if not candidates:
        print(f'  ZERO candidates (no valid uptrend+consol)')
    else:
        # Sort by combined distance to user expectation
        candidates.sort(key=lambda x: x['s_off'] + x['p_off'] + x['e_off'])
        
        print(f'  {len(candidates)} candidates. Best 5 by proximity to user:')
        for c in candidates[:5]:
            tot = c['s_off'] + c['p_off'] + c['e_off']
            ok = '✅' if c['s_off'] <= 4 and c['p_off'] <= 2 else ''
            print(f'    {ok} {c["sd"]}→{c["pd"]}→{c["ed"]} '
                  f'gain={c["gain"]:.1%} up={c["up_days"]}d consol={c["consol_days"]}d '
                  f'△start={c["s_off"]}d △peak={c["p_off"]}d △end={c["e_off"]}d '
                  f'total={tot}d')

        # Now sort by current algorithm's efficiency scoring
        candidates.sort(key=lambda x: x['efficiency'], reverse=True)
        best_eff = candidates[0]
        print(f'  Algorithm picks (by efficiency): {best_eff["sd"]}→{best_eff["pd"]}→{best_eff["ed"]} '
              f'eff={best_eff["efficiency"]:.4f} △start={best_eff["s_off"]}d △peak={best_eff["p_off"]}d')

        # Check: is user's exact segment in the candidate list?
        exact = [c for c in candidates if c['sd'] == us_ts.date() and c['pd'] == ue_ts.date()]
        if exact:
            e = exact[0]
            print(f'  User segment IN LIST: eff={e["efficiency"]:.4f} rank by eff={[i for i,c in enumerate(sorted(candidates,key=lambda x:x["efficiency"],reverse=True)) if c["sd"]==us_ts.date() and c["pd"]==ue_ts.date()][0]+1}/{len(candidates)}')
        else:
            # Find closest
            closest = min(candidates, key=lambda x: abs((x['sd'] - us_ts.date()).days) + abs((x['pd'] - ue_ts.date()).days))
            print(f'  User segment NOT in list. Closest: {closest["sd"]}→{closest["pd"]}')

    print()

f.close()
