# -*- coding: utf-8 -*-
"""validate_v9b.py —— 对生成的 v9 XTRD 做落盘校验

校验：① GBK 可编码 ② 变量不重复定义 ③ 函数白名单 ④ 括号配平
      ⑤ 无禁用函数/跨周期 ⑥ 关键参数与校准结果一致 ⑦ 逐行语义抽查
"""
import re, os, sys, json

PATH = r"D:\360安全浏览器下载\赢益共振\赢益共振_v9.XTRD"
ALLOWED = set("""MA SMA EMA DMA REF REFX HHV LLV SUM COUNT STD VAR AVEDEV SLOPE FORCAST
ABS MAX MIN MOD POW SQRT LOG LN EXP INT INTPART ROUND CEILING FLOOR SIGN
CROSS LONGCROSS UPNDAY DOWNNDAY BARSCOUNT BARSSINCE
IF IFF IFELSE VALUEWHEN BARSLAST BARSSINCE FILTER
DRAWGBK DRAWTEXT DRAWNUMBER DRAWICON DRAWLINE DRAWKLINE STICKLINE
PARTLINE POLYLINE VERTLINE HORLINE PLOYLINE
RGB COLORRED COLORGREEN COLORBLUE COLORYELLOW COLORWHITE COLORBLACK COLORMAGENTA
BACKSET SPR SETCOLOR SETSTYLE
ISLASTBAR ISCONTR ISMONTHEND ISWEEKEND DAY MONTH YEAR HOUR MINUTE WEEKDAY
STDDEV BIAS VOLATILITY ADAPTIVE TR BARSLAST
""".split())
FORBID_SELFREF = ['LOOP2', 'LOOP', 'BARSLAST', 'IFELSE', 'DATEREF', 'DATE', 'DATE1']
FUNCS = ['VALUEWHEN', 'DRAWGBK', 'DRAWTEXT', 'DRAWNUMBER', 'DRAWLINE', 'STICKLINE',
         'PARTLINE', 'REF', 'MA', 'MAX', 'MIN', 'ABS', 'HHV', 'LLV', 'SLOPE',
         'RGB', 'COLORRED', 'COLORGREEN', 'COLORYELLOW', 'ISLASTBAR', 'NOT']

txt = open(PATH, 'rb').read().decode('gbk')
code = txt.split('<CODE>')[1].split('</CODE>')[0]
lines = [x.strip() for x in code.split('\r\n')]
lines = [x for x in lines if x and not x.startswith('//')]

errs = []
# ① 变量重复定义
seen = {}
for i, ln in enumerate(lines):
    m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*:=', ln)
    if m:
        v = m.group(1)
        if v in seen:
            errs.append(f'变量重复定义: {v} (行{seen[v]+1} 与 行{i+1})')
        seen[v] = i
print(f'变量定义 {len(seen)} 个，重复 {len([e for e in errs if "重复" in e])} 处')

# ② 禁用函数（在剥离注释后的净代码上判）
CODE_CLEAN = "\n".join(lines)
for f in ('LOOP2', 'DATEREF', 'BARSLAST', 'IFELSE'):
    if re.search(r'\b' + f + r'\s*\(', CODE_CLEAN):
        errs.append(f'使用了禁用函数 {f}')
if '$' in CODE_CLEAN:
    errs.append('存在跨周期引用 $')

# ③ 括号配平 + 行长
for i, ln in enumerate(lines):
    if ln.count('(') != ln.count(')'):
        errs.append(f'括号不配平 行{i+1}: {ln}')
    if len(ln) > 120:
        errs.append(f'行长超限({len(ln)}) 行{i+1}')

# ④ 未知函数（简单启发式：大写字母+左括号）
known = ALLOWED | set(FUNCS) | {'C'}
calls = set(re.findall(r"\b([A-Z][A-Z0-9_]{1,15})\s*\(", CODE_CLEAN))
unk = sorted(c for c in calls if c not in known)
print('调用到的函数:', sorted(calls))
if unk:
    print('白名单外待确认:', unk)

# ⑤ ISBN 关键参数一致性
P = {}
for ln in lines:
    m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*:=\s*([-0-9.]+)\s*;', ln)
    if m:
        P[m.group(1)] = float(m.group(2))
EXP = dict(NMID=60, NAV=14, KB=2.0, SW0=1.25, DYNM=1, LSTP=1.0, TGTW=3.0, GATEW=0.00)
print('\n参数核对:')
for k, v in EXP.items():
    got = P.get(k)
    flag = 'OK' if got == v else '不符!'
    print(f'  {k:8s} 期望={v:<8g} 实际={got}  {flag}')
    if got != v:
        errs.append(f'参数 {k} 不符（期望{v}, 实际{got}）')

# ⑥ 逻辑抽查
need = ['WCL:=', 'WL:=VALUEWHEN(WCL OR POSLO,POSLO)', 'NEWL:=', 'RAWL:=NEWL',
        'SLL:=S0L+DYNM*A1L*(R0L+LKL)', 'SLS:=S0S-DYNM*A1S*(R0S+LKS)',
        'HOLD_L:=VALUEWHEN(RAWL OR EXA,RAWL)']
for nd in need:
    if not any(nd in ln for ln in lines):
        errs.append(f'缺少关键行: {nd}')

print('\n' + ('【全部通过】' if not errs else '【发现问题】'))
for e in errs:
    print('  -', e)
print(f'\n文件: {PATH}  {os.path.getsize(PATH)} 字节  GBK 解码正常')
print(f'总行数 {len(code.split(chr(13)+chr(10)))}  代码行 {len(lines)}')
