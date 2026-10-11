# -*- coding: utf-8 -*-
"""kb_scan.py —— 高低阈（KB）放开程度扫描

高低阈定义（当前 v9）：
    高阈 UPB = CEN + KB*WV      （触及挂空，博回调）
    低阈 DNB = CEN - KB*WV      （触及挂多，博反弹）
    KB = 2.5 是轨道宽度系数，越大阈值离均线越远、越难被触及 → 信号越少。

"放开高低阈限制" = 把 KB 收窄到 0，此时 UPB = DNB = CEN，
阈值退化为均线本身，不再要求价格先跑到远处轨道。

本脚本在「60 分钟 · 四品种主力 · D 方案 3% · ★优选（GATEW=0 + 滑点 0.5 跳）
· 每品种独立 30 万 · MGTOT=0.80 / MAXLOT=100」口径下扫描 KB。
"""
import sys, os, json, math
sys.path.insert(0, r'C:/Users/Administrator/gh-cli')
import numpy as np
import mainspec as MS
import maindata as MD
from bt_main import run_one, P0
from pool import portfolio, PM0

CAP0 = 300000.0
TF = '60分钟'
RISK = 0.03
GW, SL = 0.0, 0.5
MGTOT, MAXLOT = 0.80, 100
KBS = [2.5, 2.0, 1.5, 1.0, 0.75, 0.5, 0.25]
KBS = [(k, 'win') for k in KBS] + [(0.0, 'win'), (0.0, 'ma')]
OUT = r'C:/Users/Administrator/gh-cli/kb_scan.json'


def sharpe(curve):
    if len(curve) < 3:
        return 0.0
    byday = {}
    for t, v in curve:
        byday[str(t)[:10]] = v
    days = sorted(byday)
    if len(days) < 3:
        return 0.0
    eq = np.array([byday[d] for d in days], float)
    r = np.diff(eq) / eq[:-1]
    sd = r.std(ddof=1)
    return float(r.mean() / sd * math.sqrt(252)) if sd > 0 else 0.0


def merge_curves(curves, cap0):
    curves = [c for c in curves if c]
    if not curves:
        return [(cap0, cap0)]
    ts = sorted(set(t for c in curves for t, _ in c))
    mats = []
    for c in curves:
        d = dict(c); last = cap0; vals = []
        for t in ts:
            if t in d:
                last = d[t]
            vals.append(last)
        mats.append(vals)
    return [(t, sum(m[i] for m in mats)) for i, t in enumerate(ts)]


def curve_mdd(curve):
    peak = curve[0][1] if curve else 0.0
    mdd = 0.0
    for t, v in curve:
        if v > peak:
            peak = v
        if peak - v > mdd:
            mdd = peak - v
    return mdd, (100.0 * mdd / peak if peak > 0 else 0.0)


def one(kb, p, mode='win'):
    d = MD.load_main(p, TF)
    if d is None:
        return None
    tr = run_one(d, dict(P0, GATEW=GW, KB=kb, MODE=mode), slip=SL)
    if not tr:
        return None
    r = portfolio([dict(x) for x in tr], dict(PM0, CAP0=CAP0, RISK=RISK,
                                              MGTOT=MGTOT, MAXLOT=MAXLOT, COMPOUND=True))
    s = r['stat']; pnls = [t['pnl'] for t in r['taken']]
    return dict(sig=len(tr), n=s['n'], skip=len(tr) - s['n'],
                win=s['win'], pf=s['pf'], ret=s['ret_pct'],
                eq=sum(pnls), gw=sum(x for x in pnls if x > 0),
                gl=abs(sum(x for x in pnls if x <= 0)),
                mdd=s['mdd_mtm_pct'], calmar=s['calmar'],
                sharpe=sharpe(r['curve']), curve=r['curve'],
                long_pct=100.0 * sum(1 for t in r['taken'] if t['dir'] > 0) / s['n'] if s['n'] else 0.0,
                exp_r=float(np.mean([t['net_r'] for t in r['taken']])) if s['n'] else 0.0,
                avg_lots=s['avg_lots']) if s['n'] else None


def main():
    rows = []
    print('=' * 138)
    print('高低阈 KB 放开程度扫描 · 60 分钟 · 四品种主力 · D 方案 3% · '
          '★优选(GATEW=0+0.5跳) · 每品种独立 30 万 · MGTOT=0.8/MAXLOT=100')
    print('=' * 138)
    print(f'{"KB":>6s}{"阈值位置":>14s}{"信号":>7s}{"成交":>7s}{"跳过":>7s}{"胜率":>8s}'
          f'{"PF":>7s}{"期望R":>8s}{"均手":>7s}{"四账户盈亏":>13s}{"收益率":>9s}'
          f'{"回撤":>8s}{"Calmar":>8s}{"Sharpe":>8s}')
    for kb, mode in KBS:
        per = {}; sig = n = skip = 0; gw = gl = 0.0; wsum = rsum = 0.0
        curves = []
        for p in MS.PROD:
            o = one(kb, p, mode)
            if o is None:
                continue
            per[MS.NAME[p]] = o
            sig += o['sig']; n += o['n']; skip += o['skip']
            gw += o['gw']; gl += o['gl']
            wsum += o['win'] * o['n']; rsum += o['exp_r'] * o['n']
            curves.append(o['curve'])
        if not n:
            print(f'{kb:>6.2f}{mode:>6s}   —— 无成交')
            continue
        tot = CAP0 * 4
        eq = sum(o['eq'] for o in per.values())
        mg = merge_curves(curves, CAP0)
        _, mdd_pct = curve_mdd(mg)
        ret = 100.0 * eq / tot
        rec = dict(kb=kb, mode=mode, sig=sig, n=n, skip=skip, win=wsum / n, pf=gw / gl if gl else 0.0,
                   ret=ret, eq=eq, exp_r=rsum / n, mdd=mdd_pct,
                   calmar=ret / mdd_pct if mdd_pct > 0 else 0.0,
                   sharpe=sharpe(mg), curve=mg, per=per)
        rows.append(rec)
        pos = ('阈=均线·放开互斥' if mode == 'ma' else ('阈=均线' if kb == 0 else f'均线±{kb}×WV'))
        print(f'{kb:>6.2f}{pos:>14s}{sig:>7d}{n:>7d}{skip:>7d}{wsum/n:>7.1f}%'
              f'{rec["pf"]:>7.2f}{rsum/n:>+8.3f}'
              f'{np.mean([o["avg_lots"] for o in per.values()]):>7.1f}'
              f'{eq:>+13,.0f}{ret:>+8.1f}%{mdd_pct:>7.2f}%{rec["calmar"]:>8.2f}{rec["sharpe"]:>8.2f}')

    print(f'\n{"="*138}\n### 分品种明细（收益率 % / 成交笔数 / 信号数）\n{"="*138}')
    print(f'{"KB":>6s}' + ''.join(f'{MS.NAME[p]:>20s}' for p in MS.PROD) + f'{"合计":>14s}')
    for r in rows:
        s = f'{r["kb"]:>6.2f}{"*" if r["mode"]=="ma" else " "}'
        for p in MS.PROD:
            o = r['per'].get(MS.NAME[p])
            s += f'{o["ret"]:>+9.1f}%/{o["n"]:<3d}/{o["sig"]:<4d}' if o else f'{"—":>20s}'
        s += f'{r["ret"]:>+13.1f}%'
        print(s)

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(rows, f, ensure_ascii=False, default=float)
    print(f'\n已落盘 {OUT}')


if __name__ == '__main__':
    main()
