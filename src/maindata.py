# -*- coding: utf-8 -*-
"""maindata.py —— 四品种 × 四周期（15分钟 / 30分钟 / 60分钟 / 日线）统一数据加载

· 15/60/日线 ：直接读 回测4/<主力合约>_{15,60,D}.csv
· 30 分钟     ：读 15 分钟再按文华分段规则合成（synth30.py，已用 SA2701 真实 M30 全量校验：
                时间戳 534/534 完全一致、收盘价 534/534 完全一致）
                纯碱另有真实 M30 文件，可用 M30_SRC='real' 切换做交叉验证

参数 NMID（均线周期）/ NAV(波动周期)：
  15分钟 NMID=60 / 30分钟 NMID=40 / 60分钟 NMID=40 / 日线 NMID=20   （30 分钟沿用 60 分钟口径）
"""
import os, sys
import numpy as np
sys.path.insert(0, r'C:/Users/Administrator/gh-cli')
import mainspec as MS
from v9np import load_csv
from synth30 import read_csv as read_raw, synth30

BASE = r'D:/360安全浏览器下载/赢益共振/回测4'
RAW = r'D:/360安全浏览器下载/赢益共振/回测'

TFS = ['15分钟', '30分钟', '60分钟', '日线']
TF4 = {
    '15分钟': dict(pat='_15.csv', NMID=60, NAV=14),
    '30分钟': dict(pat='_15.csv', NMID=40, NAV=14, synth=True),
    '60分钟': dict(pat='_60.csv', NMID=40, NAV=14),
    '日线':   dict(pat='_D.csv',  NMID=20, NAV=14),
}
M30_SRC = 'synth'          # 'synth' = 15分钟合成 | 'real' = 真实M30（仅纯碱有）


def _split(rows):
    D = np.array([r[0] for r in rows])
    O = np.array([r[1] for r in rows], dtype=float)
    H = np.array([r[2] for r in rows], dtype=float)
    L = np.array([r[3] for r in rows], dtype=float)
    C = np.array([r[4] for r in rows], dtype=float)
    return D, O, H, L, C


def load_main(prod, tf):
    """返回 dict(code, prod, dt, o,h,l,c, NMID, NAV) 或 None"""
    q = TF4[tf]
    code = MS.MAIN[prod]
    if tf == '30分钟' and M30_SRC == 'real' and prod == 'SA':
        f = os.path.join(RAW, code + '_M30.csv')
        if os.path.exists(f):
            D, O, H, L, C = _split(read_raw(f))
            return dict(code=code, prod=prod, dt=D, o=O, h=H, l=L, c=C,
                        NMID=q['NMID'], NAV=q['NAV'])
    f = os.path.join(BASE, code + q['pat'])
    if not os.path.exists(f):
        return None
    if q.get('synth'):
        rows = read_raw(f)
        rows = synth30(rows)
        if len(rows) < 60:
            return None
        D, O, H, L, C = _split(rows)
    else:
        D, O, H, L, C = load_csv(f)
    return dict(code=code, prod=prod, dt=D, o=O, h=H, l=L, c=C,
                NMID=q['NMID'], NAV=q['NAV'])


def audit():
    """数据体检：合成 30 分钟是否出现异常交易日"""
    import collections
    print('=== 四品种 × 四周期 数据体检 ===')
    print(f'{"品种":6s}{"合约":9s}' + ''.join(f'{t:>22s}' for t in TFS))
    for p in MS.PROD:
        cells = []
        for tf in TFS:
            d = load_main(p, tf)
            if d is None:
                cells.append('缺失'); continue
            cells.append(f'{len(d["c"]):>4d}根 {str(d["dt"][0])[:10]}~{str(d["dt"][-1])[:10]}')
        print(f'{MS.NAME[p]:6s}{MS.MAIN[p]:9s}' + ''.join(f'{c:>22s}' for c in cells))
    print()
    print('=== 15 分钟数据每日根数分布（用于判断合成质量）===')
    for p in MS.PROD:
        f = os.path.join(BASE, MS.MAIN[p] + '_15.csv')
        rows = read_raw(f)
        c = collections.Counter(r[0][:10] for r in rows)
        cnt = collections.Counter(c.values())
        full = 23 if p in ('SA', 'SH') else 15
        print(f'  {MS.NAME[p]}: 交易日 {len(c)} 天 | 每日根数分布 {dict(sorted(cnt.items()))} '
              f'| 完整日应为 {full} 根')


if __name__ == '__main__':
    audit()
