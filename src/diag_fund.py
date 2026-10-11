# -*- coding: utf-8 -*-
"""diag_fund.py —— 单品种 30 万「资金使用效率」诊断

固定口径（用户指定）：60 分钟 · D 方案 风险 3% · ★优选配置（GATEW=0 + 滑点 0.5 跳）· 每品种独立 30 万
诊断内容：
  1. 保证金占用：平均占用率 / 峰值占用率 / 资金闲置率
  2. 是否被约束卡住：MGTOT（保证金上限）vs 风险预算，谁在主导手数
  3. 跳过笔数与原因
  4. 手数分布与 MAXLOT 触顶次数
  5. MGTOT × MAXLOT 扫描，看收益/回撤/资金利用率如何变化
"""
import sys, os, json
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
_C = {}


def T(p):
    if p not in _C:
        d = MD.load_main(p, TF)
        _C[p] = None if d is None else run_one(d, dict(P0, GATEW=GW), slip=SL)
    return _C[p]


def run(p, mgtot, maxlot, risk=RISK, cap0=CAP0):
    tr = T(p)
    if not tr:
        return None, None
    tr = [dict(x) for x in tr]
    r = portfolio(tr, dict(PM0, CAP0=cap0, RISK=risk, MGTOT=mgtot, MAXLOT=maxlot,
                           COMPOUND=True))
    return r['stat'], r


def main():
    print('=' * 140)
    print('单品种 30 万 · 资金使用效率诊断   （60 分钟 · D 方案 3% · ★优选：零闸门 + 0.5 跳）')
    print('=' * 140)

    # ---------- 0. 每手保证金 / 每手风险（用于判断谁在约束手数）
    print(f'\n{"品种":6s}{"合约":9s}{"乘数":>5s}{"单手保证金":>11s}{"每手风险(元)":>13s}'
          f'{"风险预算":>10s}{"保证金上限":>11s}{"风险允许手":>11s}{"保证金允许手":>13s}{"约束方":>8s}')
    info = {}
    for p in MS.PROD:
        tr = T(p)
        if not tr:
            continue
        mult = MS.SPEC[p]['mult']
        mgs = [x['margin'] for x in tr]
        rks = [x['risk0'] * mult for x in tr]
        med_mg = float(np.median(mgs)); med_rk = float(np.median(rks))
        rb = CAP0 * RISK; mgb = CAP0 * PM0['MGTOT']
        lr = rb / med_rk; lm = mgb / med_mg
        info[p] = dict(med_mg=med_mg, med_rk=med_rk)
        who = '风险预算' if lr < lm else '保证金'
        print(f'{MS.NAME[p]:6s}{tr[0]["code"]:9s}{mult:>5.0f}{med_mg:>11,.0f}{med_rk:>13,.0f}'
              f'{rb:>10,.0f}{mgb:>11,.0f}{lr:>11.1f}{lm:>13.1f}{who:>8s}')

    # ---------- 1. 当前配置（MGTOT=0.60, MAXLOT=50）资金使用情况
    print(f'\n\n{"="*140}\n### 当前默认参数（MGTOT=60% / MAXLOT=50）下的资金使用\n{"="*140}')
    print(f'{"品种":6s}{"成交":>6s}{"跳/信号":>9s}{"均手":>8s}{"最大手":>8s}'
          f'{"均风险%":>9s}{"均保证金占用%":>13s}{"峰值保证金占用%":>15s}{"资金闲置%":>11s}'
          f'{"MAXLOT触顶":>11s}{"跳过原因":>22s}')
    base = {}
    for p in MS.PROD:
        s, r = run(p, PM0['MGTOT'], PM0['MAXLOT'])
        if not s:
            continue
        tr = T(p)
        lots = [t['lots'] for t in r['taken']]
        n_maxlot = sum(1 for t in r['taken'] if t['lots'] >= PM0['MAXLOT'])
        skip = s['skip_why']
        sk = ','.join(f'{k}×{v}' for k, v in skip.items()) or '无'
        base[p] = (s, r)
        print(f'{MS.NAME[p]:6s}{s["n"]:>6d}{s["n"]:>7d}/{len(tr):<3d}{s["avg_lots"]:>8.2f}'
              f'{max(lots):>8d}{s["avg_risk_pct"]:>9.2f}{s["avg_pos_pct"]:>13.2f}'
              f'{s["mg_peak_pct"]:>15.2f}{100.0-s["avg_pos_pct"]:>11.1f}'
              f'{n_maxlot:>11d}{sk:>22s}')

    # ---------- 2. MGTOT × MAXLOT 扫描
    print(f'\n\n{"="*140}\n### 扫描：保证金上限 MGTOT × 单笔最大手数 MAXLOT（D 方案 3% 不变）\n{"="*140}')
    for p in MS.PROD:
        tr = T(p)
        if not tr:
            continue
        print(f'\n--- {MS.NAME[p]}（{tr[0]["code"]}）---')
        print(f'{"MGTOT":>7s}{"MAXLOT":>8s}{"成交":>7s}{"胜率":>8s}{"均手":>8s}'
              f'{"均风险%":>9s}{"均保证金%":>11s}{"峰值保证金%":>13s}'
              f'{"收益%":>10s}{"年化%":>10s}{"含浮亏回撤%":>13s}{"Calmar":>8s}{"终值":>13s}')
        for mg in (0.60, 0.70, 0.80, 0.90, 1.00):
            for ml in (50, 100, 200):
                s, r = run(p, mg, ml)
                if not s:
                    continue
                mark = ''
                print(f'{mg:>7.2f}{ml:>8d}{s["n"]:>7d}{s["win"]:>7.1f}%{s["avg_lots"]:>8.2f}'
                      f'{s["avg_risk_pct"]:>9.2f}{s["avg_pos_pct"]:>11.2f}'
                      f'{s["mg_peak_pct"]:>13.2f}{s["ret_pct"]:>+10.1f}%'
                      f'{s["ann_pct"]:>+10.1f}%{s["mdd_mtm_pct"]:>12.2f}%'
                      f'{s["calmar"]:>8.2f}{s["eq_end"]:>13,.0f}')

    # ---------- 3. 建议手数 vs 实际手数（看资金是否被浪费）
    print(f'\n\n{"="*140}\n### 逐笔手数构成（默认参数）：风险允许手数 vs 实际开仓手数\n{"="*140}')
    for p in MS.PROD:
        s, r = run(p, PM0['MGTOT'], PM0['MAXLOT'])
        if not s:
            continue
        lim = []
        for t in r['taken']:
            mult = t['mult']; rk = t['risk0'] * mult; mg = t['margin']
            lr = int((t['base_eq'] * RISK) // rk) if rk > 0 else 0
            lm = int((t['base_eq'] * PM0['MGTOT']) // mg) if mg > 0 else 0
            lim.append((lr, lm, t['lots'], 'MIN' if lm < lr else '风险'))
        lr_ = [x[0] for x in lim]; lm_ = [x[1] for x in lim]; ac = [x[2] for x in lim]
        bind_mg = sum(1 for x in lim if x[2] < x[0])       # 实际手数 < 风险允许 → 被保证金/MAXLOT 卡
        print(f'{MS.NAME[p]:6s} 风险允许手数 均{np.mean(lr_):6.1f}/中位{np.median(lr_):5.0f} | '
              f'保证金允许手数 均{np.mean(lm_):6.1f}/中位{np.median(lm_):5.0f} | '
              f'实际开仓 均{np.mean(ac):6.1f} | 被保证金/MAXLOT 压制的笔数 {bind_mg}/{len(ac)}')


if __name__ == '__main__':
    main()
