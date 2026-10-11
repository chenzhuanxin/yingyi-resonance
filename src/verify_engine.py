# -*- coding: utf-8 -*-
"""verify_np2.py —— 用最终参数核对：向量化引擎 v9np 与逐行复刻器 rep_v9 的
所有中间量（EL/ES/WVL/WVS/SLL/SLS/TGL/TGS/BUY/SELL/EXL/EXS）是否逐点一致

rep_v9 是按 XTRD 源码语义逐行手写的纯 Python 复刻（VALUEWHEN = 前值锁存），
因此本校验等价于「向量化引擎 == 落盘 XTRD 的语义」。
"""
import sys, os, glob
sys.path.insert(0, r'C:/Users/Administrator/gh-cli')
import v9np, rep_v9
from bt10 import load

P = dict(KB=2.0, SW0=1.25, DYNM=1, LSTP=1.0, TGTW=3.0, GATEW=0.00)
TFS = {'15分钟': ('_15.csv', 60), '60分钟': ('_60.csv', 40), '日线': ('_D.csv', 20)}
KEYS = ['EL', 'ES', 'WVL', 'WVS', 'SLL', 'SLS', 'TGL', 'TGS']
BKEYS = ['BUY', 'SELL', 'EXL', 'EXS', 'RAWL', 'RAWS']

bad = 0; tested = 0
for tf, (pat, nmid) in TFS.items():
    ds = v9np.dataset(tf)
    for d in ds['items'][:6]:
        f = os.path.join(v9np.BASE, d['code'] + pat)
        if not os.path.exists(f):
            continue
        rows = load(f)
        PP = dict(P, NMID=nmid, NAV=14)
        r = v9np.signals(d, PP)
        q = rep_v9.xtrd(rows, d['code'], dict(P, NMID=nmid, NAV=14, COSTR=d['cost']))
        tested += 1
        diff = []
        for k in KEYS:
            a = r[k] if not hasattr(r[k], 'tolist') else r[k].tolist()
            b = q[k]
            for i in range(min(len(a), len(b))):
                if abs(float(a[i]) - float(b[i])) > 1e-6:
                    diff.append(f'{k}@{i}: {a[i]} vs {b[i]}'); break
        for k in BKEYS:
            a = [bool(x) for x in (r[k] if not hasattr(r[k], 'tolist') else r[k].tolist())]
            b = [bool(x) for x in q[k]]
            if a != b:
                for i in range(min(len(a), len(b))):
                    if a[i] != b[i]:
                        diff.append(f'{k}@{i}: {a[i]} vs {b[i]}'); break
        status = 'OK' if not diff else 'DIFF'
        if diff:
            bad += 1
            print(f'{tf:6s} {d["code"]:10s} {status}  {diff[:3]}')
        else:
            print(f'{tf:6s} {d["code"]:10s} {status}')
print(f'\n核对 {tested} 个合约，不一致 {bad} 个 → ' +
      ('向量化引擎与逐行复刻语义完全一致' if bad == 0 else '存在不一致，需排查'))
