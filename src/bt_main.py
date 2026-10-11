# -*- coding: utf-8 -*-
"""bt_main.py —— 四品种【当前主力合约】用【GitHub 真实手续费+保证金】重新测试

引擎口径 = 落盘 XTRD「赢益共振_v9」的价格窗口锁存 + 阶梯锁盈动态止损（逐点一致）
成本口径 = chenzhuanxin/futures-sim-trading-terminal 品种参数.json
           （东方财富期货「公司手续费标准」+「公司保证金比例」）

三种滑点口径（其余参数一致）：
  A  none —— 限价成交，无滑点（理想上界）
  B  real —— 开仓限价(0滑点) / 止损与移动止盈出场按市价(1跳) / 目标出场限价(0滑点)  ← 主口径
  C  both —— 开平双边各 1 跳（保守下界）
"""
import sys, os, json, math, glob, copy
sys.path.insert(0, r'C:/Users/Administrator/gh-cli')
import numpy as np
from v9np import signals, load_csv
import mainspec as MS

BASE = r'D:/360安全浏览器下载/赢益共振/回测4'
P0 = dict(KB=2.5, SW0=1.25, DYNM=1, LSTP=1.0, TGTW=3.0, GATEW=0.30)


def load_main(prod, tf):
    pat, nmid, nav = MS.TF[tf]
    f = os.path.join(BASE, MS.MAIN[prod] + pat)
    if not os.path.exists(f):
        return None
    D, O, H, L, C = load_csv(f)
    return dict(code=MS.MAIN[prod], prod=prod, dt=D, o=O, h=H, l=L, c=C,
                NMID=nmid, NAV=nav)


# 滑点档位 → (开仓跳数, 止损/移动止盈出场跳数, 到达目标出场跳数)
_SLIP_SET = {
    'none':  (0.0, 0.0, 0.0),   # 理想上界：全部限价成交
    'real':  (0.0, 1.0, 0.0),   # 主口径：开仓挂单限价 / 止损·移动止盈市价 1 跳 / 目标限价
    'both':  (1.0, 1.0, 1.0),   # 保守下界：开平双边各 1 跳
}


def _slip_set(slip):
    """把 slip 解析为 (开仓跳数, 止损出场跳数, 目标出场跳数)

    支持三种写法：
      · 字符串：'none' / 'real' / 'both'（向后兼容）
      · 数值  ：出场跳数（开仓 0 跳、目标 0 跳）—— 例如 0.5 / 1 / 2
      · dict  ：{'en':开仓跳数, 'ex':止损跳数, 'tgt':目标跳数}
    """
    if isinstance(slip, str):
        return _SLIP_SET[slip]
    if isinstance(slip, dict):
        return (float(slip.get('en', 0.0)), float(slip.get('ex', 1.0)),
                float(slip.get('tgt', 0.0)))
    if isinstance(slip, (int, float)):
        return (0.0, float(slip), 0.0)
    v = tuple(float(x) for x in slip)
    return (v + (0.0, 0.0, 0.0))[:3]


def run_one(d, P, slip='real', both='stop'):
    """按落盘 XTRD 语义逐根推进；成本按每笔真实开平仓价 + 成交方式滑点计算"""
    prod = d['prod']; mult = MS.SPEC[prod]['mult']; tick = MS.SPEC[prod]['tick']
    med = float(np.median(d['c']))
    en_slip0, ex_stop0, ex_tgt0 = _slip_set(slip)
    # 闸门用的常数成本：往返滑点 ≈ 开仓 + 一次市价出场
    sl_gate = en_slip0 + ex_stop0
    c_gate, _, _ = MS.roundtrip_cost(prod, med, med, sl_gate)
    dd = dict(d); dd['cost'] = c_gate
    Pp = dict(P, NMID=d['NMID'], NAV=d['NAV'])
    s = signals(dd, Pp)
    n = s['n']; O, H, L = s['O'], s['H'], s['L']
    out = []
    pos = 0; ep = 0.0; wv = 0.0; eb = -1
    for i in range(n):
        if pos == 0:
            dirn = 1 if s['BUY'][i] else (-1 if s['SELL'][i] else 0)
            if dirn:
                anch = s['EL'][i] if dirn > 0 else s['ES'][i]
                if not (anch > 0):          # 排除暖机边界的无效锚（MA 未成形）
                    continue
                wv = (s['WVL'][i] if dirn > 0 else s['WVS'][i]) or 1e-9
                if not (wv > 0):
                    continue
                eb = i; ep = anch; pos = dirn
        if pos == 0 or i < eb:
            continue

        def close(xp, reason, is_stop):
            en_slip = en_slip0
            ex_slip = ex_stop0 if is_stop else ex_tgt0
            fee = MS.fee_points(prod, ep) + MS.fee_points(prod, xp)
            slip_pts = (en_slip + ex_slip) * tick
            cost = fee + slip_pts
            net = ((xp - ep) if pos > 0 else (ep - xp)) - cost
            mg = MS.margin_yuan(prod, ep)
            # 入场时的初始止损距离（点数）= 每手最大风险；仓位管理据此定手数
            sl0 = s['SLL'][eb] if pos > 0 else s['SLS'][eb]
            risk0 = abs(ep - float(sl0))
            # 持仓期逐K线浮动盈亏（点数，正=浮盈）与最大浮亏（MAE）—— 用于含浮亏的回撤
            # 止损为挂单价，浮亏不会突破初始止损距离，故下界截断在 −risk0
            path = []
            for j in range(eb, i + 1):
                up = (s['C'][j] - ep) if pos > 0 else (ep - s['C'][j])
                path.append((str(s['dt'][j]), float(max(up, -risk0))))
            mae = min(u for _, u in path) if path else 0.0
            out.append(dict(
                prod=prod, name=MS.NAME[prod], code=d['code'], dir=pos,
                et=str(s['dt'][eb]), xt=str(s['dt'][i]), bars=i - eb,
                ep=float(ep), xp=float(xp), wv=float(wv),
                cost=float(cost), fee=float(fee), slip=float(slip_pts),
                net=float(net), net_r=float(net / wv), mult=mult,
                net_yuan=float(net * mult), margin=float(mg),
                risk0=float(risk0), risk_yuan=float(risk0 * mult),
                mae=float(mae), mae_yuan=float(mae * mult), path=path,
                ret=float(net * mult / mg) if mg > 0 else 0.0,
                reason=reason, sl=bool(is_stop)))

        if i == eb:
            sl = s['SLL'][i] if pos > 0 else s['SLS'][i]
            hit = (L[i] <= sl) if pos > 0 else (H[i] >= sl)
            if hit:
                close(sl, '初始止损', True); pos = 0
            continue
        if pos > 0 and s['EXL'][i]:
            sl = s['SLL'][i]; tp = s['TGL'][i]
            hSL = L[i] <= sl; hTP = H[i] >= tp
            if hSL and hTP:
                hSL = (both == 'stop')
            close(sl, ('移动止盈' if sl > ep else '初始止损'), True) if hSL else close(tp, '到达目标', False)
            pos = 0
        elif pos < 0 and s['EXS'][i]:
            sl = s['SLS'][i]; tp = s['TGS'][i]
            hSL = H[i] >= sl; hTP = L[i] <= tp
            if hSL and hTP:
                hSL = (both == 'stop')
            close(sl, ('移动止盈' if sl < ep else '初始止损'), True) if hSL else close(tp, '到达目标', False)
            pos = 0
    return out


def agg(tr):
    if not tr:
        return dict(n=0, exp=0.0, exp_yuan=0.0, win=0.0, tot=0.0, tot_yuan=0.0, t=0.0,
                    pf=0.0, rr=0.0, ret=0.0, mdd_yuan=0.0, mdd_r=0.0, sl=0.0, trl=0.0,
                    tp=0.0, avg_bars=0.0, margin=0.0, cost_yuan=0.0)
    nr = np.array([x['net_r'] for x in tr]); ny = np.array([x['net_yuan'] for x in tr])
    n = len(tr)
    m = float(nr.mean()); sd = float(nr.std(ddof=1)) if n > 1 else 0.0
    w = nr[nr > 0]; lo = nr[nr <= 0]; wy = ny[ny > 0]; loy = ny[ny <= 0]
    eq = np.cumsum(ny); peak = np.maximum.accumulate(eq)
    mult = tr[0]['mult']
    return dict(n=n, exp=m, exp_yuan=float(ny.mean()), win=100.0 * len(w) / n,
                tot=float(nr.sum()), tot_yuan=float(ny.sum()),
                t=(m / (sd / math.sqrt(n))) if sd > 0 else 0.0,
                pf=(float(wy.sum()) / abs(float(loy.sum()))) if len(loy) and loy.sum() != 0 else 0.0,
                rr=(float(w.mean()) / abs(float(lo.mean()))) if len(w) and len(lo) else 0.0,
                ret=100.0 * float(np.mean([x['ret'] for x in tr])),
                mdd_yuan=float((peak - eq).max()), mdd_r=float((peak - eq).max() / mult),
                sl=100.0 * sum(1 for x in tr if x['reason'] == '初始止损') / n,
                trl=100.0 * sum(1 for x in tr if x['reason'] == '移动止盈') / n,
                tp=100.0 * sum(1 for x in tr if x['reason'] == '到达目标') / n,
                avg_bars=float(np.mean([x['bars'] for x in tr])),
                margin=float(np.mean([x['margin'] for x in tr])),
                cost_yuan=float(np.mean([x['cost'] * mult for x in tr])))


def hdr(title, cw=None):
    cw = cw or [6, 9, 7, 25, 6, 7, 9, 10, 8, 9, 11, 11, 10]
    cols = ['品种', '合约', 'K线数', '区间', '笔数', '胜率', '期望R', '期望元', '盈亏比',
            '累计R', '累计元', '最大回撤元', '平均保证金']
    print(''.join(c.rjust(w) for c, w in zip(cols, cw)))


def row(name, code, nb, rng, a, cw=None):
    cw = cw or [6, 9, 7, 25, 6, 7, 9, 10, 8, 9, 11, 11, 10]
    vals = [name, code, str(nb), rng, str(a['n']), f"{a['win']:.1f}%", f"{a['exp']:+.3f}",
            f"{a['exp_yuan']:+.1f}", f"{a['pf']:.2f}", f"{a['tot']:+.2f}",
            f"{a['tot_yuan']:+.1f}", f"{a['mdd_yuan']:.1f}", f"{a['margin']:.0f}"]
    print(''.join(v.rjust(w) for v, w in zip(vals, cw)))


def main():
    print('=' * 150)
    print('四品种【当前主力合约】· GitHub 真实手续费 + 保证金 · v9 价格窗口锁存 + 阶梯锁盈动态止损')
    print('主口径：KB=2.5 SW0=1.25 DYNM=1 LSTP=1.0 TGTW=3.0 GATEW=0.30  滑点=real(开仓限价/止损出场1跳/目标出场限价)')
    print('=' * 150)
    result = {}
    for tf in MS.TF:
        print(f'\n【{tf}】')
        hdr(tf)
        tot = []
        for p in MS.PROD:
            d = load_main(p, tf)
            if d is None:
                continue
            tr = run_one(d, P0)
            a = agg(tr); tot += tr
            rng = f'{str(d["dt"][0])[:10]}~{str(d["dt"][-1])[:10]}'
            row(MS.NAME[p], d['code'], len(d['c']), rng, a)
            result.setdefault(tf, {})[p] = dict(a=a, tr=tr)
        if tot:
            c = agg(tot); row('合计', '', '', '', c)
            result[tf]['ALL'] = dict(a=c, tr=tot)
    with open(r'C:/Users/Administrator/gh-cli/main_result.json', 'w', encoding='utf-8') as f:
        json.dump({tf: {k: dict(a=v['a'], tr=v['tr']) for k, v in r.items()}
                   for tf, r in result.items()}, f, ensure_ascii=False)
    print('\n已落盘 main_result.json')


if __name__ == '__main__':
    main()
