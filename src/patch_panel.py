# -*- coding: utf-8 -*-
"""
patch_panel_v9.py —— 一次性完成两件事（幂等 · 单遍 · 纯 CRLF · 自动备份）

① DRAWNUMBER 颜色移入括号内
   DRAWNUMBER(COND,DATA,NUMBER,PRECISION),COLOR;  ->  DRAWNUMBER(COND,DATA,NUMBER,PRECISION,COLOR);
   共 4 处（挂多手数 / 挂空手数 / 面板手数），面板内那处随后被新面板覆盖。

② 状态面板瘦身（解决「文字把 K 线撑得展不开」）
   原来 10 行、最顶那行在 HIGH+0.95*SRNG（SRNG = 120 周期振幅），
   相当于把最后一根 K 线上方撑出近一整个波段的高度 -> K 线被压扁。
   现改为 7 行、行距 0.035*SRNG，总高 0.245*SRNG（压缩 74%），
   并新增总开关 SHOWPNL（1=显示 / 0=整段隐藏，K 线可完全展开）。
   同时去掉「成本/波动比例」那行（GATEW=0 后恒开闸，该数字已不参与决策，
   且小数常显示为 0.xx 看着像 0）。
"""
import os
import re
import shutil
import sys

P = r'D:/360安全浏览器下载/赢益共振/赢益共振_v9.XTRD'
BAK = r'D:/360安全浏览器下载/赢益共振/赢益共振_v9_面板瘦身前备份.XTRD'

# ---------------------------------------------------------------- ① 颜色移入括号
NUM_PATCHES = [
    ("DRAWNUMBER(SHOWP=1 AND BUY_S,DN1*0.991,LSL_L,0),COLORRED;",
     "DRAWNUMBER(SHOWP=1 AND BUY_S,DN1*0.991,LSL_L,0,COLORRED);"),
    ("DRAWNUMBER(SHOWP=1 AND SELL_S,UP1*1.009,LSL_S,0),COLORGREEN;",
     "DRAWNUMBER(SHOWP=1 AND SELL_S,UP1*1.009,LSL_S,0,COLORGREEN);"),
]

# ---------------------------------------------------------------- ② 新面板（7 行）
NEW_PANEL = [
    '//——— 十五、状态面板（只在最后一根K线显示；把下面 SHOWPNL 改成 0 可整段关闭）———',
    'SHOWPNL:=1;                                         //1=显示面板  0=隐藏（面板是唯一占用K线上方空间的东西）',
    'SRNG:=MAX(HHV(HIGH,120)-LLV(LOW,120),CLOSE*0.01);',
    'SPAD:=SRNG*0.035;                                   //行距：原 0.10*SRNG → 0.035*SRNG，7 行总高仅 0.245*SRNG',
    'SY1:=HIGH+SPAD*1;',
    'SY2:=HIGH+SPAD*2;',
    'SY3:=HIGH+SPAD*3;',
    'SY4:=HIGH+SPAD*4;',
    'SY5:=HIGH+SPAD*5;',
    'SY6:=HIGH+SPAD*6;',
    'SY7:=HIGH+SPAD*7;',
    "DRAWTEXT(ISLASTBAR=1 AND SHOWPNL=1,SY7,'【赢益共振 v9】均线中枢+波动轨+限价挂单+动态止损'),COLORYELLOW;",
    "DRAWTEXT(ISLASTBAR=1 AND SHOWPNL=1 AND SHOWP=1,SY6,'建议手数（资金×单笔风险÷每手止损额）：'),COLORYELLOW;",
    "DRAWNUMBER(ISLASTBAR=1 AND SHOWPNL=1 AND SHOWP=1,SY5,LSNC,0,COLORYELLOW);",
    "DRAWTEXT(ISLASTBAR=1 AND SHOWPNL=1 AND GATE,SY4,'成本闸门：开·可交易'),COLORGREEN;",
    "DRAWTEXT(ISLASTBAR=1 AND SHOWPNL=1 AND NOT(GATE),SY4,'成本闸门：关·本档不做'),COLORRED;",
    "DRAWTEXT(ISLASTBAR=1 AND SHOWPNL=1 AND POSLO,SY3,'位置：低阈附近·伺机博反弹（挂多）'),COLORRED;",
    "DRAWTEXT(ISLASTBAR=1 AND SHOWPNL=1 AND POSHI,SY3,'位置：高阈附近·伺机博回调（挂空）'),COLORGREEN;",
    "DRAWTEXT(ISLASTBAR=1 AND SHOWPNL=1 AND NOT(POSLO) AND NOT(POSHI),SY3,'位置：中枢中部·此处不挂单'),COLORYELLOW;",
    "DRAWTEXT(ISLASTBAR=1 AND SHOWPNL=1 AND HOLD_L=1,SY2,'持仓：已挂多·动态止损跟随（图上红粗线）'),COLORRED;",
    "DRAWTEXT(ISLASTBAR=1 AND SHOWPNL=1 AND HOLD_S=1,SY2,'持仓：已挂空·动态止损跟随（图上绿粗线）'),COLORGREEN;",
    "DRAWTEXT(ISLASTBAR=1 AND SHOWPNL=1 AND NOT(HOLD_L) AND NOT(HOLD_S),SY2,'持仓：空仓·等触及'),COLORYELLOW;",
    "DRAWTEXT(ISLASTBAR=1 AND SHOWPNL=1 AND SLPV>0.5,SY1,'均线状态：向上'),COLORRED;",
    "DRAWTEXT(ISLASTBAR=1 AND SHOWPNL=1 AND SLPV<-0.5,SY1,'均线状态：向下'),COLORGREEN;",
    "DRAWTEXT(ISLASTBAR=1 AND SHOWPNL=1 AND ABS(SLPV)<=0.5,SY1,'均线状态：走平'),COLORYELLOW;",
]


def main():
    raw = open(P, 'rb').read()
    s = raw.decode('gbk')
    s = s.replace('\r\n', '\n')          # 归一化，便于块处理
    lines = s.split('\n')

    # 定位原面板段
    i0 = next((i for i, l in enumerate(lines) if '十五、状态面板' in l), None)
    i1 = next((i for i, l in enumerate(lines)
               if '上一行 = 成本/波动比例' in l), None)
    if i0 is None or i1 is None or i1 < i0:
        print('!! 未能定位原面板段，请检查文件。'); return 1

    # 幂等：若已是新面板（有 SHOWPNL 且无旧 SY10）
    already = any('SHOWPNL:=' in l for l in lines)
    if already:
        print('面板已是新版，跳过面板替换。')
    else:
        print(f'原面板段：第 {i0+1} ~ {i1+1} 行，共 {i1-i0+1} 行 → 压缩为 {len(NEW_PANEL)} 行')
        lines[i0:i1 + 1] = NEW_PANEL

    s = '\n'.join(lines)

    # ① 颜色移入括号
    n1 = 0
    for old, new in NUM_PATCHES:
        if new in s:
            print('  已是目标形态，跳过:', new[:50]); continue
        if old in s:
            s = s.replace(old, new, 1); n1 += 1
            print('  ✔ 颜色移入括号:', new)
        else:
            print('  ✘ 未找到:', old)

    if not os.path.exists(BAK):
        shutil.copy2(P, BAK); print('已备份 →', BAK)

    s = s.replace('\n', '\r\n')
    assert s.count('\n') == s.count('\r\n'), 'CRLF 归一化异常'
    open(P, 'wb').write(s.encode('gbk'))
    print(f'\n已写入 {P}（颜色改动 {n1} 处）')

    # ---------------- 复核
    chk = open(P, 'rb').read().decode('gbk')
    print('\n== 复核 DRAWNUMBER ==')
    ok = True
    for l in chk.split('\r\n'):
        if 'DRAWNUMBER' in l:
            inner = l[l.find('(') + 1:l.rfind(')')]
            narg = inner.count(',') + 1
            # 颜色是否在括号内
            incol = any(c in inner for c in
                        ('COLORRED', 'COLORGREEN', 'COLORYELLOW', 'COLORWHITE',
                         'COLORBLUE', 'COLORMAGENTA', 'COLORCYAN'))
            print(f'  {narg} 参  颜色在括号内={incol} | {l}')
            if narg != 5 or not incol:
                ok = False
    print('\n== 面板高度 ==')
    m = re.search(r'SPAD:=SRNG\*([\d.]+)', chk)
    k = float(m.group(1)) if m else 0
    top = max([float(x) for x in re.findall(r'SY(\d+):=', chk)] or [0])
    print(f'  行距系数 {k} × 最高行号 {int(top)} → 面板总高 {k*top:.3f}×SRNG（原 0.95×SRNG，'
          f'压缩 {100*(1-k*top/0.95):.0f}%）')
    print(f'  SHOWPNL 开关: {"有" if "SHOWPNL:=" in chk else "无"}')
    print('\n结果:', '✔ 通过' if ok else '✘ 有问题')
    return 0 if ok else 2


if __name__ == '__main__':
    sys.exit(main())
