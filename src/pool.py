# -*- coding: utf-8 -*-
"""pool.py —— 组合级「仓位管理」引擎（固定风险比例法 / Fixed-Fractional Risk）

设计目标
--------
把原来「每笔固定 1 手」的逐笔回测，升级成**按账户权益动态定手数**的组合回测：

  1. 单笔风险预算    risk_yuan = 权益 × RISK
  2. 每手最大风险    risk_per_lot = |入场价 − 初始止损价| × 合约乘数
  3. 风险允许手数    lots_risk = floor(risk_yuan / risk_per_lot)
  4. 保证金允许手数  lots_margin = floor((权益×MGTOT − 已占用保证金) / 单手保证金)
  5. 实际手数        lots = min(lots_risk, lots_margin, MAXLOT)   —— 不足 1 手则跳过（或保底 1 手）
  6. 组合约束        同时持仓数 ≤ MAXPOS；同一时间总保证金占用 ≤ 权益 × MGTOT
  7. 权益推进        equity += 净盈亏；复利（COMPOUND）或固定本金基准

之所以选「固定风险比例法」而不是「固定手数」或「固定资金比例」：
  · 每笔按止损距离定手数 → 无论波动大小，单笔最大亏损都锚定在权益的固定百分比，
    波动大的品种自动减手、波动小的自动加手，风险敞口在横截面上是"平价"的；
  · 止损距离 = SW0×ATR 已经隐含波动信息，不需要额外再估计波动率；
  · 组合层面用「总保证金占用上限」兜底，防止四品种同时开仓时满仓。
"""
import sys, os, json, math
sys.path.insert(0, r'C:/Users/Administrator/gh-cli')
import numpy as np
import mainspec as MS
from bt_main import load_main, run_one, P0

# ---------------------------------------------------------------- 默认参数
PM0 = dict(
    CAP0=300000.0,   # 初始资金（元）—— 30 万可让四品种日线全部可开仓
    RISK=0.01,       # 单笔风险预算（占当前权益比例）
    MGTOT=0.60,      # 组合总保证金占用上限（占当前权益比例）
    MAXLOT=50,       # 单笔最大手数
    MAXPOS=4,        # 同时持仓上限（品种数）
    MIN1=False,      # 不足 1 手时是否按 1 手保底开仓
    COMPOUND=True,   # 是否复利（False = 始终按 CAP0 计算风险预算）
    DDTHR=0.0,       # 回撤节流阈值（当前回撤/峰值 ≥ 该值时降档）；0=关闭
    DDSCALE=0.5,     # 触发节流后的风险预算系数（0 = 暂停开仓）
)


# ---------------------------------------------------------------- 取数
def collect(tf, P=None, slip='real', prods=None):
    """合并四品种全部交易（每笔 1 手口径），按开仓时间排序"""
    P = dict(P0 if P is None else P)
    tr = []
    for p in (prods or MS.PROD):
        d = load_main(p, tf)
        if d is None:
            continue
        tr += run_one(d, P, slip=slip)
    tr.sort(key=lambda x: (x['et'], x['xt'], MS.PROD.index(x['prod'])))
    return tr


# ---------------------------------------------------------------- 含浮亏的市值回撤
def mtm_curve(taken, cap0):
    """按「已实现权益 + 在持仓浮盈浮亏」逐事件点计算市值权益曲线。

    事件点 = 所有开仓与平仓时点；持仓浮亏取该时刻之前最近一根K线的收盘浮动盈亏。
    这样得到的回撤包含持仓浮亏（比只算已实现回撤更接近真实账户体验）。
    """
    if not taken:
        return [(cap0, cap0)]
    times = sorted(set([t['et'] for t in taken] + [t['xt'] for t in taken]))
    by_xt = sorted(taken, key=lambda t: t['xt'])
    # 已实现权益（按 xt 结算）
    res = {}
    eq = cap0; i = 0
    for tm in times:
        while i < len(by_xt) and by_xt[i]['xt'] <= tm:
            eq += by_xt[i]['pnl']; i += 1
        res[tm] = eq
    out = []
    for tm in times:
        u = 0.0
        for t in taken:
            if t['et'] <= tm < t['xt']:
                v = None
                for pt, pu in t.get('path', ()):
                    if pt <= tm:
                        v = pu
                    else:
                        break
                if v is not None:
                    u += v * t['lots'] * t['mult']
        out.append((tm, res[tm] + u))
    return out


def mtm_mdd(taken, cap0):
    cur = mtm_curve(taken, cap0)
    peak = cap0; mdd = 0.0; mt = None
    for tm, v in cur:
        if v > peak:
            peak = v
        if peak - v > mdd:
            mdd = peak - v; mt = tm
    return mdd, (100.0 * mdd / peak if peak > 0 else 0.0), mt


# ---------------------------------------------------------------- 组合推进
def portfolio(trades, pm=None):
    """按时间推进的组合仓位管理回测。

    返回 dict(taken=[...], skipped=[...], curve=[(time,equity)], stat={...})
    """
    pm = dict(PM0, **(pm or {}))
    CAP0 = pm['CAP0']

    eq = CAP0              # 已实现权益
    used_mg = 0.0          # 已占用保证金合计
    mg_peak = 0.0          # 保证金占用峰值
    mg_peak_pct = 0.0      # 峰值时占「当时权益」比例
    npos_peak = 0          # 同时持仓峰值
    peak = CAP0
    mdd = 0.0; mdd_t = None
    open_slots = []
    taken = []; skipped = []
    curve = [(trades[0]['et'] if trades else '', CAP0)]

    def settle(upto, force=False):
        """结算所有 xt<=upto（或全部）的持仓；按 xt 排序保证权益曲线时间单调"""
        nonlocal eq, used_mg, peak, mdd, mdd_t
        due = [p for p in open_slots if force or p['xt'] <= upto]
        if not due:
            return
        due.sort(key=lambda p: p['xt'])
        ids = set(id(p) for p in due)
        for pos in due:
            eq += pos['pnl']
            used_mg -= pos['mg_used']
            if eq > peak:
                peak = eq
            dd = peak - eq
            if dd > mdd:
                mdd = dd; mdd_t = pos['xt']
            pos['eq_after'] = eq
            pos['dd_after'] = dd
            curve.append((pos['xt'], eq))
        open_slots[:] = [p for p in open_slots if id(p) not in ids]

    for x in trades:
        settle(x['et'])
        base = eq if pm['COMPOUND'] else CAP0
        mult = x['mult']
        risk_pts = x['risk0']
        risk_lot = risk_pts * mult                 # 每手最大亏损（元）
        mg_lot = x['margin']                       # 单手保证金（元）

        if pm['MAXPOS'] and len(open_slots) >= pm['MAXPOS']:
            skipped.append(dict(x=x, why='同时持仓上限')); continue

        # 回撤节流：已实现回撤达到阈值时，按 DDSCALE 缩小风险预算
        scale = 1.0
        if pm['DDTHR'] > 0 and peak > 0 and (peak - eq) / peak >= pm['DDTHR']:
            scale = pm['DDSCALE']
            if scale <= 0:
                skipped.append(dict(x=x, why='回撤节流暂停')); continue

        lots_r = int((base * pm['RISK'] * scale) // risk_lot) if risk_lot > 0 else pm['MAXLOT']
        lots_m = int((base * pm['MGTOT'] - used_mg) // mg_lot) if mg_lot > 0 else 0
        lots = min(lots_r, lots_m, pm['MAXLOT'])

        if lots < 1:
            if pm['MIN1'] and lots_m >= 1:
                lots = 1
            else:
                skipped.append(dict(x=x, why=('保证金不足' if lots_m < 1 else '风险预算不足')))
                continue

        mg_used = lots * mg_lot
        pnl = x['net'] * lots * mult               # net 已含手续费与滑点（点数）
        used_mg += mg_used
        if used_mg > mg_peak:
            mg_peak = used_mg; mg_peak_pct = 100.0 * used_mg / eq if eq > 0 else 0.0
        npos_peak = max(npos_peak, len(open_slots) + 1)
        t = dict(x, lots=lots, mg_used=mg_used, pnl=pnl,
                 risk_used=lots * risk_lot,
                 risk_pct=100.0 * lots * risk_lot / base,
                 pos_pct=100.0 * mg_used / base,
                 base_eq=base, ret_on_mg=100.0 * pnl / mg_used if mg_used else 0.0)
        open_slots.append(t)
        taken.append(t)

    settle(None, force=True)

    # ---------------- 统计
    mdd_mtm, mdd_mtm_pct, mdd_mtm_t = mtm_mdd(taken, CAP0)
    stat = dict(pm=pm, cap0=CAP0, eq_end=eq, pnl=eq - CAP0,
                ret_pct=100.0 * (eq / CAP0 - 1.0),
                mdd=mdd, mdd_pct=100.0 * mdd / peak if peak > 0 else 0.0, mdd_t=mdd_t,
                mdd_mtm=mdd_mtm, mdd_mtm_pct=mdd_mtm_pct, mdd_mtm_t=mdd_mtm_t,
                n=len(taken), n_skip=len(skipped),
                mg_peak=mg_peak, mg_peak_pct=mg_peak_pct,
                npos_peak=npos_peak,
                worst_loss_pct=min([t['pnl'] / t['base_eq'] * 100.0 for t in taken], default=0.0),
                worst_mae_pct=min([t['mae_yuan'] * t['lots'] / t['base_eq'] * 100.0
                                   for t in taken], default=0.0),
                skip_why={w: sum(1 for s in skipped if s['why'] == w)
                          for w in set(s['why'] for s in skipped)} if skipped else {})
    if taken:
        arr = np.array([t['pnl'] for t in taken])
        w = arr[arr > 0]; l = arr[arr <= 0]
        stat.update(
            win=100.0 * len(w) / len(arr),
            pf=(float(w.sum()) / abs(float(l.sum()))) if len(l) and l.sum() != 0 else 0.0,
            avg_lots=float(np.mean([t['lots'] for t in taken])),
            avg_risk_pct=float(np.mean([t['risk_pct'] for t in taken])),
            avg_pos_pct=float(np.mean([t['pos_pct'] for t in taken])),
            avg_pnl=float(arr.mean()),
        )
        # 期间与年化
        t0 = taken[0]['et']; t1 = max(t['xt'] for t in taken)
        try:
            import datetime as _dt
            d0 = _dt.datetime.fromisoformat(str(t0)[:19]); d1 = _dt.datetime.fromisoformat(str(t1)[:19])
            days = max((d1 - d0).total_seconds() / 86400.0, 1.0)
        except Exception:
            days = 365.0
        stat['days'] = days
        stat['ann_pct'] = 100.0 * ((eq / CAP0) ** (365.0 / days) - 1.0) if eq > 0 else -100.0
        stat['calmar'] = stat['ann_pct'] / stat['mdd_pct'] if stat['mdd_pct'] > 0 else 0.0
    else:
        stat.update(win=0.0, pf=0.0, avg_lots=0.0, avg_risk_pct=0.0, avg_pos_pct=0.0,
                    avg_pnl=0.0, days=0.0, ann_pct=0.0, calmar=0.0)
    return dict(taken=taken, skipped=skipped, curve=curve, stat=stat)


# ---------------------------------------------------------------- 交叉验证：组合 vs 逐品种独立
def per_product(trades, pm=None):
    out = {}
    for p in MS.PROD:
        sub = [x for x in trades if x['prod'] == p]
        if not sub:
            continue
        out[p] = portfolio(sub, pm)['stat']
    return out


if __name__ == '__main__':
    print(f'{"周期":8s}{"原始笔数":>9s}{"实际开仓":>9s}{"跳过":>7s}{"胜率":>8s}'
          f'{"平均手数":>9s}{"终值":>12s}{"收益率":>9s}{"最大回撤":>10s}{"回撤%":>8s}')
    for tf in MS.TF:
        tr = collect(tf)
        r = portfolio(tr)
        s = r['stat']
        print(f'{tf:8s}{len(tr):>9d}{s["n"]:>9d}{s["n_skip"]:>7d}{s["win"]:>7.1f}%'
              f'{s["avg_lots"]:>9.2f}{s["eq_end"]:>12,.0f}{s["ret_pct"]:>+8.1f}%'
              f'{s["mdd"]:>10,.0f}{s["mdd_pct"]:>7.1f}%')
