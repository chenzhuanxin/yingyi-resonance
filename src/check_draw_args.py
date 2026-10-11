# -*- coding: utf-8 -*-
"""绘图函数参数个数体检：对照文华 WH6 官方签名，逐行核对。"""
import re

P = r'D:/360安全浏览器下载/赢益共振/赢益共振_v9.XTRD'

# 文华 WH6 官方签名（必需参数个数）；颜色/线型等修饰在函数后置时为可选
SIG = {
    'DRAWTEXT': (3, 3),
    'DRAWNUMBER': (4, 5),
    'DRAWLINE': (5, 5),
    'DRAWICON': (3, 3),
    'DRAWKLINE': (4, 4),
    'STICKLINE': (5, 6),
    'DRAWGBK': (2, 4),
    'DRAWBAND': (3, 4),
    'POLYLINE': (1, 1),
}
DRAWERS = sorted(SIG, key=len, reverse=True)


def split_args(s):
    """按顶层逗号切分（忽略括号内逗号）"""
    out, depth, cur = [], 0, ''
    for ch in s:
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        if ch == ',' and depth == 0:
            out.append(cur); cur = ''
        else:
            cur += ch
    out.append(cur)
    return [x.strip() for x in out]


def main():
    txt = open(P, 'rb').read().decode('gbk')
    lines = txt.split('\r\n')
    bad, cnt = [], {}
    for i, ln in enumerate(lines, 1):
        code = ln.split('//')[0] if not ln.strip().startswith('//') else ''
        for f in DRAWERS:
            for m in re.finditer(r'(?<![A-Z_])' + f + r'\s*\(', code):
                # 找到与之配对的右括号
                start = m.end() - 1
                depth = 0
                for j in range(start, len(code)):
                    if code[j] == '(':
                        depth += 1
                    elif code[j] == ')':
                        depth -= 1
                        if depth == 0:
                            inner = code[start + 1:j]
                            break
                else:
                    continue
                args = split_args(inner)
                n = len(args)
                cnt[f] = cnt.get(f, 0) + 1
                lo, hi = SIG[f]
                mark = 'OK ' if lo <= n <= hi else 'BAD'
                if mark == 'BAD':
                    bad.append((i, f, n, lo, hi, ln))
    print('== 各绘图函数调用次数 ==')
    for f in DRAWERS:
        if cnt.get(f):
            lo, hi = SIG[f]
            print(f'  {f:12s} {cnt[f]:>3d} 次   合法参数个数 {lo}~{hi}')
    print('\n== 逐行核对（仅列出非 DRAWNUMBER 的行，避免刷屏）==')
    for i, ln in enumerate(lines, 1):
        if 'DRAWNUMBER' in ln or 'DRAWLINE' in ln or ('DRAWTEXT' in ln and '面板' in ln):
            if ln.strip().startswith('//') or ln.strip() == '':
                continue
            for f in DRAWERS:
                if f + '(' in ln:
                    s = ln[ln.find(f + '(') + len(f) + 1:ln.rfind(')')]
                    print(f'  {i:>3d}  {f:12s} {len(split_args(s))} 参  | {ln[:96]}')
                    break
    print('\n== 结论 ==')
    if bad:
        print('发现参数个数越界的调用：')
        for i, f, n, lo, hi, ln in bad:
            print(f'  行{i}  {f} 给了 {n} 个参数，期望 {lo}~{hi}  -> {ln}')
    else:
        print('所有绘图函数参数个数均在合法区间内 ✔')


if __name__ == '__main__':
    main()
