# -*- coding: utf-8 -*-
"""v9np.py —— v9（价格窗口锁存 + 阶梯锁盈动态止损）的 numpy 向量化复刻 + 高速参数扫描

严格对齐 XTRD 落盘代码的语义：
  CEN=MA(C,NMID); WV=MA(TR,NAV)
  UPB/DNB=CEN±KB*WV
  GATE: COSTR/WV<=GATEW
  POSLO: L<=REF(DNB,1);  POSHI: H>=REF(UPB,1)
  WCL: C>DNB+TGTW*WV or C<DNB-SW0*WV
  WL=VALUEWHEN(WCL or POSLO, POSLO)      ← 价格窗口锁存
  RAWL=上升沿(WL) and not POSHI and GATE
  EL=VALUEWHEN(RAWL,REF(DNB,1)); WVL=VALUEWHEN(RAWL,WV)
  R0L=SW0*WVL; S0L=EL-R0L
  A_k = VALUEWHEN(RAWL or (REF(H,1)>=EL+k*LSTP*R0L), 条件) and not RAWL
  NKL=ΣA_k;  SLL=S0L+DYNM*A_1*(R0L+NKL*LSTP*R0L)
  TGL=EL+TGTW*WVL
  EXA=(L<=SLL or H>=TGL) and not RAWL
  HOLD=VALUEWHEN(RAWL or EXA,RAWL); BUY=RAWL and not REF(HOLD,1); EXL=REF(HOLD,1) and not HOLD
"""
import os, glob, math
import numpy as np

BASE = r"D:/360安全浏览器下载/赢益共振/回测4"
COST = {'SA': 1.4, 'CJ': 6.2, 'PK': 3.6, 'SH': 1.1}
NAME = {'SA': '纯碱', 'CJ': '红枣', 'PK': '花生', 'SH': '烧碱'}
PROD = ['SA', 'CJ', 'PK', 'SH']

TFP = {
    '15分钟': dict(pat='_15.csv', NMID=60, NAV=14, NS=30),
    '60分钟': dict(pat='_60.csv', NMID=40, NAV=14, NS=20),
    '日线':   dict(pat='_D.csv',  NMID=20, NAV=14, NS=10),
}


def load_csv(path):
    O = []; H = []; L = []; C = []; D = []
    with open(path, 'r', encoding='utf-8-sig') as f:
        hdr = f.readline()
        for ln in f:
            p = ln.strip().split(',')
            if len(p) < 5:
                continue
            try:
                o, h, l, c = float(p[1]), float(p[2]), float(p[3]), float(p[4])
            except Exception:
                continue
            if h < l:
                h, l = l, h
            o = min(max(o, l), h); c = min(max(c, l), h)
            D.append(p[0]); O.append(o); H.append(h); L.append(l); C.append(c)
    return (np.array(D), np.array(O), np.array(H), np.array(L), np.array(C))


def ma(x, n):
    out = np.full(len(x), np.nan)
    if len(x) < n:
        return out
    c = np.cumsum(np.insert(x, 0, 0.0))
    out[n - 1:] = (c[n:] - c[:-n]) / n
    return out


def ffill(mask, vals):
    """VALUEWHEN：mask 为真时取 vals，否则沿用上一次的值；从未成立则 nan"""
    idx = np.where(mask, np.arange(len(mask)), -1)
    np.maximum.accumulate(idx, out=idx)
    out = np.full(len(mask), np.nan)
    ok = idx >= 0
    out[ok] = vals[idx[ok]]
    return out


_CACHE = {}


def dataset(tf, prods=None):
    key = (tf, tuple(prods or PROD))
    if key in _CACHE:
        return _CACHE[key]
    p = TFP[tf]
    items = []
    for v in (prods or PROD):
        seq = 0
        for f in sorted(glob.glob(os.path.join(BASE, v + '*.csv'))):
            if not os.path.basename(f).endswith(p['pat']):
                continue
            D, O, H, L, C = load_csv(f)
            if len(C) < 120:
                continue
            code = os.path.basename(f).split('_')[0]
            items.append(dict(code=code, prod=code[:2], seq=seq, dt=D, o=O, h=H, l=L, c=C,
                              cost=COST[code[:2]]))
            seq += 1
    _CACHE[key] = dict(items=items, NMID=p['NMID'], NAV=p['NAV'], NS=p['NS'])
    return _CACHE[key]


def signals(d, P):
    O, H, L, C = d['o'], d['h'], d['l'], d['c']
    n = len(C)
    with np.errstate(divide='ignore', invalid='ignore'):
        return _signals(d, P, O, H, L, C, n)


def _signals(d, P, O, H, L, C, n):
    CEN = ma(C, P['NMID'])
    pc = np.concatenate(([C[0]], C[:-1]))
    trw = np.maximum.reduce([H, L, pc]) - np.minimum.reduce([H, L, pc])
    WV = ma(trw, P['NAV'])
    ok = np.isfinite(CEN) & (WV > 0)
    UPB = np.where(ok, CEN + P['KB'] * WV, 0.0)
    DNB = np.where(ok, CEN - P['KB'] * WV, 0.0)
    GATE = ok & ((P['GATEW'] <= 0) | (d['cost'] / WV <= P['GATEW']))
    UP1 = np.concatenate(([0.0], UPB[:-1]))
    DN1 = np.concatenate(([0.0], DNB[:-1]))
    POSLO = ok.copy(); POSLO[0] = False
    POSLO[1:] &= (L[1:] <= DN1[1:])
    POSHI = ok.copy(); POSHI[0] = False
    POSHI[1:] &= (H[1:] >= UP1[1:])
    WCL = ok & ((C > DNB + P['TGTW'] * WV) | (C < DNB - P['SW0'] * WV))
    WCS = ok & ((C < UPB - P['TGTW'] * WV) | (C > UPB + P['SW0'] * WV))
    MODE = P.get('MODE', 'win')
    if MODE == 'ma':
        # ★无高低阈版（放开阈值）：阈宽归零（KB=0 时 DNB=UPB=CEN），
        #   并去掉「打到高阈就不做多」的互相否决 → 收盘价下穿/上穿均线即出信号
        LZ = ok & np.isfinite(CEN) & (C <= CEN)
        HZ = ok & np.isfinite(CEN) & (C > CEN)
        RAWL = LZ & ~np.concatenate(([False], LZ[:-1])) & GATE
        RAWS = HZ & ~np.concatenate(([False], HZ[:-1])) & GATE
    elif MODE == 'win':
        # 价格窗口锁存：一轮下跌只开一次仓，锚点在整段持仓期不变
        WL = np.nan_to_num(ffill(WCL | POSLO, POSLO.astype(float))) > 0.5
        WS = np.nan_to_num(ffill(WCS | POSHI, POSHI.astype(float))) > 0.5
        NEWL = WL & ~np.concatenate(([False], WL[:-1]))
        NEWS = WS & ~np.concatenate(([False], WS[:-1]))
        RAWL = NEWL & ~POSHI & GATE
        RAWS = NEWS & ~POSLO & GATE
    else:
        # 简化触及版（落盘 XTRD 当前形态）：每根触及低/高阈的K都可能触发
        RAWL = POSLO & ~POSHI & GATE
        RAWS = POSHI & ~POSLO & GATE
    wvz = np.where(ok, WV, 0.0)
    EL = np.nan_to_num(ffill(RAWL, DN1)); ES = np.nan_to_num(ffill(RAWS, UP1))
    WVL = np.nan_to_num(ffill(RAWL, wvz)); WVS = np.nan_to_num(ffill(RAWS, wvz))
    R0L = P['SW0'] * WVL; R0S = P['SW0'] * WVS
    S0L = EL - R0L; S0S = ES + R0S
    TGL = EL + P['TGTW'] * WVL; TGS = ES - P['TGTW'] * WVS
    prevH = np.concatenate(([H[0]], H[:-1]))
    prevL = np.concatenate(([L[0]], L[:-1]))
    NKL = np.zeros(n); NKS = np.zeros(n); arm1L = np.zeros(n); arm1S = np.zeros(n)
    for k in (1, 2, 3, 4, 5):
        HL = prevH >= EL + k * P['LSTP'] * R0L
        LL = prevL <= ES - k * P['LSTP'] * R0S
        v1 = np.nan_to_num(ffill(RAWL | HL, HL.astype(float))) > 0.5
        v2 = np.nan_to_num(ffill(RAWS | LL, LL.astype(float))) > 0.5
        a1 = v1 & ~RAWL; a2 = v2 & ~RAWS
        if k == 1:
            arm1L = a1.astype(float); arm1S = a2.astype(float)
        NKL += a1; NKS += a2
    SLL = S0L + P['DYNM'] * arm1L * (R0L + NKL * P['LSTP'] * R0L)
    SLS = S0S - P['DYNM'] * arm1S * (R0S + NKS * P['LSTP'] * R0S)
    EXA = ((L <= SLL) | (P['TGTW'] > 0) & (H >= TGL)) & ~RAWL
    EXB = ((H >= SLS) | (P['TGTW'] > 0) & (L <= TGS)) & ~RAWS
    HOLDL = np.nan_to_num(ffill(RAWL | EXA, RAWL.astype(float))) > 0.5
    HOLDS = np.nan_to_num(ffill(RAWS | EXB, RAWS.astype(float))) > 0.5
    BUY = RAWL & ~np.concatenate(([False], HOLDL[:-1]))
    SELL = RAWS & ~np.concatenate(([False], HOLDS[:-1]))
    EXL = np.concatenate(([False], HOLDL[:-1])) & ~HOLDL
    EXS = np.concatenate(([False], HOLDS[:-1])) & ~HOLDS
    return dict(n=n, O=O, H=H, L=L, C=C, UPB=UPB, DNB=DNB, EL=EL, ES=ES, WVL=WVL, WVS=WVS,
                SLL=SLL, SLS=SLS, TGL=TGL, TGS=TGS, BUY=BUY, SELL=SELL, EXL=EXL, EXS=EXS,
                RAWL=RAWL, RAWS=RAWS, POSLO=POSLO, POSHI=POSHI, GATE=GATE, WV=WV, CEN=CEN,
                cost=d['cost'], dt=d['dt'])


def trades(d, P, both='stop'):
    """both: 'stop'=同K线内止损与目标同时命中时按止损计（悲观）；'tgt'=按目标计（乐观）"""
    sig = signals(d, P)
    out = []
    pos = 0; ep = 0.0; wv = 0.0
    for i in range(sig['n']):
        if pos == 0:
            if sig['BUY'][i]:
                pos, ep, wv = 1, sig['EL'][i], (sig['WVL'][i] or 1e-9)
            elif sig['SELL'][i]:
                pos, ep, wv = -1, sig['ES'][i], (sig['WVS'][i] or 1e-9)
        if pos > 0 and sig['EXL'][i]:
            sl = sig['SLL'][i]; tp = sig['TGL'][i]
            hitSL = sig['L'][i] <= sl; hitTP = sig['H'][i] >= tp
            if hitSL and hitTP:
                hitSL = (both == 'stop')
            xp = sl if hitSL else tp
            out.append(dict(dir=1, ep=ep, xp=xp, wv=wv, net=(xp - ep) - sig['cost'],
                            sl=bool(hitSL), dt=sig['dt'][i], prod=d['prod'], code=d['code']))
            pos = 0
        elif pos < 0 and sig['EXS'][i]:
            sl = sig['SLS'][i]; tp = sig['TGS'][i]
            hitSL = sig['H'][i] >= sl; hitTP = sig['L'][i] <= tp
            if hitSL and hitTP:
                hitSL = (both == 'stop')
            xp = sl if hitSL else tp
            out.append(dict(dir=-1, ep=ep, xp=xp, wv=wv, net=(ep - xp) - sig['cost'],
                            sl=bool(hitSL), dt=sig['dt'][i], prod=d['prod'], code=d['code']))
            pos = 0
    return out


def run(tf, P, both='stop', prods=None, split=None):
    ds = dataset(tf, prods)
    P = dict(P)
    P.setdefault('KB', 2.0); P.setdefault('SW0', 3.0); P.setdefault('DYNM', 1)
    P.setdefault('LSTP', 1.0); P.setdefault('TGTW', 0.5); P.setdefault('GATEW', 0.10)
    P['NMID'] = ds['NMID']; P['NAV'] = ds['NAV']
    alltr = []
    for d in ds['items']:
        alltr += trades(d, P, both)
    if split is None:
        return alltr
    a, b = [], []
    for d in ds['items']:
        (a if split(d) else b).extend(trades(d, P, both))
    return a, b


def agg(tr):
    if not tr:
        return dict(n=0, exp=0.0, win=0.0, tot=0.0, t=0.0, slrate=0.0, rr=0.0, mae=0.0)
    na = np.array([x['net'] / x['wv'] for x in tr])
    n = len(tr)
    m = float(na.mean()); sd = float(na.std(ddof=1)) if n > 1 else 0.0
    wins = na[na > 0]; loss = na[na <= 0]
    return dict(n=n, exp=m, win=100.0 * len(wins) / n,
                tot=float(na.sum()),
                t=(m / (sd / math.sqrt(n))) if sd > 0 else 0.0,
                slrate=100.0 * sum(1 for x in tr if x['sl']) / n,
                rr=(float(wins.mean()) / abs(float(loss.mean()))) if len(wins) and len(loss) else 0.0,
                mae=0.0)


def fwd(tf, ds, tr, NF=24):
    """噪音出局率：被止损的笔中，止损后 NF 根内价格回到原目标线的比例"""
    ratio = {}
    for d in ds['items']:
        pass
    return ratio


def split_odd(d):
    """按合约序号奇偶交错（避免区间偏误）：偶数→训练，奇数→测试"""
    try:
        num = int(''.join(ch for ch in d['code'][2:] if ch.isdigit()))
    except Exception:
        num = 0
    return (num // 1) % 2 == 0
