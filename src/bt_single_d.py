# -*- coding: utf-8 -*-
"""bt_single_d.py —— 「60D 单品种独立版」最终测试

用户指定口径（只此一个，不再给其他方案/周期/配置）：
  · 方案：D 固定比例风险 3%          （不要 C 方案）
  · 周期：60 分钟                    （不要 15/30/日）
  · 配置：★优选（GATEW=0 + 出场滑点 0.5 跳）（不要 OLD / CON）
  · 资金：纯碱/红枣/花生/烧碱 各一个独立 30 万账户

本轮（续11）新增「放开高低阈」：
  高低阈 = 上轨 UPB=CEN+KB*WV / 下轨 DNB=CEN-KB*WV，KB 原为 2.5。
  扫描 KB 2.5→0 后按用户选择「温和放开至 KB=2.0」。
  资金参数沿用上一轮结论 MGTOT=0.80 / MAXLOT=100，并保留 0.60/50 对照。
"""
import sys, os, json, math
sys.path.insert(0, r'C:/Users/Administrator/gh-cli')
import numpy as np
import mainspec as MS
import maindata as MD
from bt_main import run_one, P0
from pool import portfolio, mtm_curve, PM0

OUT = r'C:/Users/Administrator/gh-cli/single_d_result.json'
CAP0 = 300000.0
TF = '60分钟'
RISK = 0.03                      # D 固定比例风险 3%
GW, SL = 0.0, 0.5                # ★优选：零闸门 + 0.5 跳
KBV = 2.0                        # ★放开后的高低阈轨道宽度（原 2.5）
FUNDS = [
    ('OLD', 0.60, 50, '优化前：保证金上限 60% + 单笔最大 50 手'),
    ('NEW', 0.80, 100, '★推荐：保证金上限 80% + 单笔最大 100 手'),
]
_C = {}


def T(p):
    if p not in _C:
        d = MD.load_main(p, TF)
        _C[p] = None if d is None else run_one(d, dict(P0, GATEW=GW, KB=KBV), slip=SL)
    return _C[p]


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


def extra(taken):
    if not taken:
        return dict(sl=0.0, trl=0.0, tp=0.0, long=0.0, fee_yuan=0.0, slip_yuan=0.0,
                    cost_yuan=0.0, cost_pct_of_wv=0.0, exp_r=0.0, avg_wv=0.0)
    n = len(taken); m = taken[0]['mult']
    return dict(
        sl=100.0 * sum(1 for t in taken if t['reason'] == '初始止损') / n,
        trl=100.0 * sum(1 for t in taken if t['reason'] == '移动止盈') / n,
        tp=100.0 * sum(1 for t in taken if t['reason'] == '到达目标') / n,
        long=100.0 * sum(1 for t in taken if t['dir'] > 0) / n,
        fee_yuan=float(np.mean([t['fee'] * m for t in taken])),
        slip_yuan=float(np.mean([t['slip'] * m for t in taken])),
        cost_yuan=float(np.mean([t['cost'] * m for t in taken])),
        cost_pct_of_wv=float(np.mean([t['cost'] / t['wv'] for t in taken])) * 100.0,
        exp_r=float(np.mean([t['net_r'] for t in taken])),
        avg_wv=float(np.mean([t['wv'] for t in taken])),
    )


def monthly(curve):
    bym = {}
    for t, v in curve:
        bym[str(t)[:7]] = v
    out = []; prev = CAP0
    for k in sorted(bym):
        v = bym[k]
        out.append(dict(month=k, eq=v, ret_pct=100.0 * (v / prev - 1.0) if prev else 0.0))
        prev = v
    return out


def streaks(taken):
    w = l = bw = bl = 0
    for t in taken:
        if t['pnl'] > 0:
            w += 1; l = 0
        else:
            l += 1; w = 0
        bw = max(bw, w); bl = max(bl, l)
    return bw, bl


def slim(t, keep_path=False):
    o = {k: v for k, v in t.items() if k != 'path'}
    if keep_path:
        o['path'] = t.get('path', [])
    for k, v in list(o.items()):
        if isinstance(v, (np.floating, np.integer)):
            o[k] = float(v)
    o.pop('pm', None)
    return o


def funds_diag(r, taken_raw, risk, mgtot):
    """资金使用诊断：手数被谁约束、实际风险与保证金用到几成"""
    lr = lm = 0.0; bind = 0; n = 0
    for t in r['taken']:
        rk = t['risk0'] * t['mult']; mg = t['margin']; b = t['base_eq']
        a = int((b * risk) // rk) if rk > 0 else 0
        bb = int((b * mgtot) // mg) if mg > 0 else 0
        lr += a; lm += bb; n += 1
        if t['lots'] < a:
            bind += 1
    return dict(
        lots_risk_avg=(lr / n if n else 0.0),
        lots_mgtot_avg=(lm / n if n else 0.0),
        lots_act_avg=float(np.mean([t['lots'] for t in r['taken']])) if n else 0.0,
        bind=int(bind), n=n,
        risk_use_pct=float(np.mean([t['risk_pct'] for t in r['taken']])) if n else 0.0,
        mg_use_pct=float(np.mean([t['pos_pct'] for t in r['taken']])) if n else 0.0,
        mg_peak_pct=r['stat']['mg_peak_pct'],
        min_lots=min([t['lots'] for t in r['taken']], default=0),
        max_lots=max([t['lots'] for t in r['taken']], default=0),
    )


def run_one_cfg(p, mgtot, maxlot):
    tr = T(p)
    if not tr:
        return None
    r = portfolio([dict(x) for x in tr], dict(PM0, CAP0=CAP0, RISK=RISK,
                                              MGTOT=mgtot, MAXLOT=maxlot, COMPOUND=True))
    s = r['stat']; ex = extra(r['taken']); bw, bl = streaks(r['taken'])
    st = dict(s, sharpe=sharpe(r['curve']), max_win_streak=bw, max_loss_streak=bl)
    dg = funds_diag(r, tr, RISK, mgtot)
    return dict(stat=st, extra=ex, diag=dg, r=r, tr=tr)


def main():
    print('=' * 152)
    print('「60D 单品种独立版」· 每品种 30 万独立账户 · 只 D 方案 3% · 只 60 分钟 · 只 ★优选（零闸门+0.5跳）')
    print('=' * 152)
    R = dict(meta=dict(cap0=CAP0, per_cap=CAP0, tf=TF, risk=RISK, gatew=GW, slip=SL,
                       kb=KBV, P0=dict(P0, KB=KBV), compound=True,
                       funds=[dict(k=k, mgtot=m, maxlot=l, label=lb) for k, m, l, lb in FUNDS],
                       nmid=MD.TF4[TF]['NMID'], nav=MD.TF4[TF]['NAV']),
             data={}, res={}, trades={}, diag={})

    for p in MS.PROD:
        nm = MS.NAME[p]; tr = T(p)
        if not tr:
            continue
        d0 = MD.load_main(p, TF)
        R['data'][nm] = dict(code=tr[0]['code'], n=len(d0['c']),
                             rng=f'{str(d0["dt"][0])[:10]}~{str(d0["dt"][-1])[:10]}')
        R['res'][nm] = {}
        print(f'\n{"="*152}\n### {nm}（{tr[0]["code"]}）· 独立账户 本金 30 万 · D 方案 风险 3%\n{"="*152}')
        print(f'{"资金参数":>5s}{"成交":>6s}{"胜率":>8s}{"PF":>7s}{"期望R":>8s}{"均手":>8s}'
              f'{"最大手":>7s}{"实际风险%":>10s}{"均保证金%":>10s}{"峰值保证金%":>12s}'
              f'{"终值":>12s}{"收益%":>10s}{"年化%":>10s}{"含浮亏回撤%":>12s}'
              f'{"Calmar":>8s}{"Sharpe":>8s}')
        for ck, mgtot, maxlot, lab in FUNDS:
            o = run_one_cfg(p, mgtot, maxlot)
            if o is None:
                continue
            s = o['stat']; ex = o['extra']; dg = o['diag']; r = o['r']
            R['res'][nm][ck] = dict(cfg=ck, mgtot=mgtot, maxlot=maxlot, label=lab,
                                    stat=s, extra=ex, diag=dg, curve=r['curve'],
                                    mtm=mtm_curve(r['taken'], CAP0),
                                    monthly=monthly(r['curve']),
                                    taken=[slim(t) for t in r['taken']])
            R['diag'][f'{nm}|{ck}'] = dg
            if ck == 'NEW':
                R['trades'][nm] = [slim(t, keep_path=True) for t in o['tr']]
            print(f'{ck:>5s}{s["n"]:>6d}{s["win"]:>7.1f}%{s["pf"]:>7.2f}{ex["exp_r"]:>+8.3f}'
                  f'{s["avg_lots"]:>8.2f}{dg["max_lots"]:>7d}{dg["risk_use_pct"]:>10.2f}'
                  f'{dg["mg_use_pct"]:>10.2f}{dg["mg_peak_pct"]:>12.2f}{s["eq_end"]:>12,.0f}'
                  f'{s["ret_pct"]:>+10.1f}%{s.get("ann_pct",0):>+10.1f}%'
                  f'{s["mdd_mtm_pct"]:>11.2f}%{s.get("calmar",0):>8.2f}{s["sharpe"]:>8.2f}')

    # ---------------- 资金使用诊断对照
    print(f'\n\n{"="*152}\n### 资金使用诊断：手数被谁约束（优化前 vs 优化后）\n{"="*152}')
    print(f'{"品种":7s}{"参数":>5s}{"风险预算允许手":>14s}{"保证金允许手":>13s}{"实际开仓":>10s}'
          f'{"被压制的笔数":>13s}{"风险用了几成":>13s}{"保证金峰值%":>12s}')
    for p in MS.PROD:
        nm = MS.NAME[p]
        for ck in ('OLD', 'NEW'):
            dg = R['diag'].get(f'{nm}|{ck}')
            if not dg:
                continue
            print(f'{nm:7s}{ck:>5s}{dg["lots_risk_avg"]:>14.1f}{dg["lots_mgtot_avg"]:>13.1f}'
                  f'{dg["lots_act_avg"]:>10.1f}{dg["bind"]:>11d}/{dg["n"]:<3d}'
                  f'{100*dg["risk_use_pct"]/3.0:>12.1f}%{dg["mg_peak_pct"]:>12.2f}')

    # ---------------- 四账户合计
    print(f'\n\n{"="*152}\n### 四账户合计（各 30 万，合计投入 120 万）· D 方案\n{"="*152}')
    for ck in ('OLD', 'NEW'):
        res = [R['res'][MS.NAME[p]][ck] for p in MS.PROD if ck in R['res'].get(MS.NAME[p], {})]
        if not res:
            continue
        tot = CAP0 * 4
        eq = sum(x['stat']['eq_end'] for x in res)
        n = sum(x['stat']['n'] for x in res)
        wins = sum(x['stat']['n'] * x['stat']['win'] / 100.0 for x in res)
        R[f'alloc_{ck}'] = dict(cap_total=tot, eq_end=eq, pnl=eq - tot,
                                ret_pct=100.0 * (eq / tot - 1.0), n=n,
                                win=100.0 * wins / n if n else 0.0,
                                per=[dict(nm=MS.NAME[p], **{
                                    k: R['res'][MS.NAME[p]][ck]['stat'][k]
                                    for k in ('n', 'win', 'pf', 'eq_end', 'ret_pct',
                                              'mdd_mtm_pct', 'calmar', 'sharpe')})
                                    for p in MS.PROD if ck in R['res'].get(MS.NAME[p], {})])
        print(f'{ck:>5s} 合计终值 {eq:>12,.0f}  盈亏 {eq-tot:>+11,.0f}  '
              f'收益率 {100.0*(eq/tot-1.0):>+7.1f}%  笔数 {n}  胜率 {R[f"alloc_{ck}"]["win"]:.1f}%')

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(R, f, ensure_ascii=False, default=float)
    print(f'\n已落盘 {OUT}  大小 {os.path.getsize(OUT)/1024:.0f} KB')


if __name__ == '__main__':
    main()
