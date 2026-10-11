# -*- coding: utf-8 -*-
"""
修复 DRAWNUMBER「参数个数非法」：
文华 WH6 的 DRAWNUMBER 签名 = DRAWNUMBER(COND, DATA, NUMBER, PRECISION);
比 DRAWTEXT(COND, PRICE, TEXT) 多一个必需的 PRECISION（小数点后位数）。
原文件只写了 3 个参数 -> 编译报「参数个数非法」。

本补丁给 4 处 DRAWNUMBER 各补一个精度参数（手数=0，成本比例=2），
保持与文件中 DRAWTEXT 一致的「函数后置颜色」风格。
幂等 · 单遍 · 纯 CRLF · 自动备份。
"""
import os
import shutil
import sys

P = r'D:/360安全浏览器下载/赢益共振/赢益共振_v9.XTRD'
BAK = r'D:/360安全浏览器下载/赢益共振/赢益共振_v9_DRAWNUMBER修复前备份.XTRD'

# (旧, 新)  —— 逐条精确匹配，幂等
PATCHES = [
    # 1) 挂多时的建议手数
    ("DRAWNUMBER(SHOWP=1 AND BUY_S,DN1*0.991,LSL_L),COLORRED;",
     "DRAWNUMBER(SHOWP=1 AND BUY_S,DN1*0.991,LSL_L,0),COLORRED;"),
    # 2) 挂空时的建议手数
    ("DRAWNUMBER(SHOWP=1 AND SELL_S,UP1*1.009,LSL_S),COLORGREEN;",
     "DRAWNUMBER(SHOWP=1 AND SELL_S,UP1*1.009,LSL_S,0),COLORGREEN;"),
    # 3) 面板上的建议手数
    ("DRAWNUMBER(ISLASTBAR=1 AND SHOWP=1,SY8,LSNC),COLORYELLOW;",
     "DRAWNUMBER(ISLASTBAR=1 AND SHOWP=1,SY8,LSNC,0),COLORYELLOW;"),
    # 4) 面板上的成本/波动比例（小数，2 位）
    ("DRAWNUMBER(ISLASTBAR=1,SY2,COSTW),COLORYELLOW;",
     "DRAWNUMBER(ISLASTBAR=1,SY2,COSTW,2),COLORYELLOW;"),
]


def main():
    raw = open(P, 'rb').read()
    s = raw.decode('gbk')
    # 归一化行尾，便于块匹配
    s = s.replace('\r\n', '\n')

    # 幂等判据：4 处都已带精度参数
    if all(new in s for _, new in PATCHES):
        print('已打过补丁，跳过。')
        return 0

    if not os.path.exists(BAK):
        shutil.copy2(P, BAK)
        print('已备份 →', BAK)

    n = 0
    for old, new in PATCHES:
        if new in s:                      # 该条已修
            print('  已是目标形态，跳过:', old[:44], '...')
            continue
        elif old in s:
            s = s.replace(old, new, 1)
            n += 1
            print('  ✔ 已补精度:', new)
        else:
            print('  ✘ 未找到原句:', old)

    if n == 0:
        print('无可改内容。')
        return 1

    # 还原 CRLF
    s = s.replace('\n', '\r\n')
    assert s.count('\n') == s.count('\r\n'), 'CRLF 归一化异常'
    open(P, 'wb').write(s.encode('gbk'))
    print(f'\n已写入 {P}（共修改 {n} 处）')

    # 复核
    chk = open(P, 'rb').read().decode('gbk')
    bad = []
    for line in chk.split('\r\n'):
        if 'DRAWNUMBER' in line:
            inner = line[line.find('(') + 1:line.rfind(')')]
            # 顶层逗号计数（本文件 DRAWNUMBER 参数里无嵌套括号，可直接数）
            nargs = inner.count(',') + 1
            print('  复核:', f'{nargs} 参数', '|', line)
            if nargs != 4:
                bad.append(line)
    if bad:
        print('\n!! 仍有参数个数不为 4 的 DRAWNUMBER：')
        for b in bad:
            print('   ', b)
        return 2
    print('\n全部 DRAWNUMBER 均为 4 参数 ✔')
    return 0


if __name__ == '__main__':
    sys.exit(main())
