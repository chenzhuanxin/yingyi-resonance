# -*- coding: utf-8 -*-
"""make_sd_report.py —— 「60D 单品种独立版」HTML 报告（只 D 方案 / 只 60 分钟 / 只 ★优选 / 每品种 30 万）"""
import sys, os, json, math, datetime as dt
sys.path.insert(0, r'C:/Users/Administrator/gh-cli')
import numpy as np
import mainspec as MS

CLI = r'C:/Users/Administrator/gh-cli'
OUT = r'D:/360安全浏览器下载/赢益共振/赢益共振_60D单品种独立版报告.html'
CAP0 = 300000.0
R = json.load(open(os.path.join(CLI, 'single_d_result.json'), encoding='utf-8'))
RS = R['res']; DG = R['diag']; M = R['meta']
PRODS = [MS.NAME[p] for p in MS.PROD]
RED, GRN, BLU, GLD, GRY = '#C0392B', '#1E8449', '#2E86C1', '#BF9000', '#A6A6A6'
PLT = {'纯碱': RED, '花生': BLU, '烧碱': GLD, '红枣': GRN}


def esc(s):
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def t2d(t, t0):
    try:
        return (dt.datetime.fromisoformat(str(t)[:19]) -
                dt.datetime.fromisoformat(str(t0)[:19])).total_seconds() / 86400.0
    except Exception:
        return 0.0


def svg_line(series, W=650, H=280, title='', base=None, ylab='', xlab='', xfmt='{:,.0f}',
             yfmt='{:,.0f}', pctmode=False):
    PL, PR, PT, PB = 74, 18, 32, 46
    iw, ih = W - PL - PR, H - PT - PB
    xs = [p[0] for _, _, pts in series for p in pts]
    ys = [p[1] for _, _, pts in series for p in pts]
    if base is not None:
        ys.append(base)
    if not xs:
        return f'<svg viewBox="0 0 {W} {H}"></svg>'
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    if y1 - y0 < 1e-9:
        y0, y1 = y0 - 1, y1 + 1
    pd = (y1 - y0) * 0.10
    y0 -= pd; y1 += pd
    X = lambda v: PL + (v - x0) / (x1 - x0) * iw if x1 > x0 else PL + iw / 2
    Y = lambda v: PT + ih - (v - y0) / (y1 - y0) * ih
    P = [f'<svg viewBox="0 0 {W} {H}" style="width:100%;height:auto;font-family:inherit">']
    P.append(f'<rect x="{PL}" y="{PT}" width="{iw}" height="{ih}" fill="#FCFDFE" stroke="#E3E8EF"/>')
    for k in range(5):
        v = y0 + (y1 - y0) * k / 4
        y = Y(v)
        P.append(f'<line x1="{PL}" y1="{y:.1f}" x2="{PL+iw}" y2="{y:.1f}" stroke="#EEF1F5"/>')
        P.append(f'<text x="{PL-7}" y="{y+4:.1f}" font-size="10.5" fill="#7A8794" '
                 f'text-anchor="end">{yfmt.format(v)}</text>')
    if base is not None:
        y = Y(base)
        P.append(f'<line x1="{PL}" y1="{y:.1f}" x2="{PL+iw}" y2="{y:.1f}" '
                 f'stroke="#B9C3CE" stroke-dasharray="5 4"/>')
    for k in range(6):
        v = x0 + (x1 - x0) * k / 5
        x = X(v)
        P.append(f'<line x1="{x:.1f}" y1="{PT+ih}" x2="{x:.1f}" y2="{PT+ih+4}" stroke="#C6CDD6"/>')
        P.append(f'<text x="{x:.1f}" y="{PT+ih+17}" font-size="10.5" fill="#7A8794" '
                 f'text-anchor="middle">{xfmt.format(v)}</text>')
    for label, color, pts in series:
        if not pts:
            continue
        if len(pts) == 1:
            P.append(f'<circle cx="{X(pts[0][0]):.1f}" cy="{Y(pts[0][1]):.1f}" r="3.5" fill="{color}"/>')
            continue
        dd = ' '.join(f'{X(a):.1f},{Y(b):.1f}' for a, b in pts)
        P.append(f'<polyline points="{dd}" fill="none" stroke="{color}" stroke-width="2.2" '
                 f'stroke-linejoin="round"/>')
    P.append(f'<text x="{PL}" y="17" font-size="12.5" font-weight="600" fill="#1F4E79">{esc(title)}</text>')
    if xlab:
        P.append(f'<text x="{W-PR}" y="{H-4}" font-size="10.5" fill="#7A8794" text-anchor="end">{esc(xlab)}</text>')
    lx = PL + 8; ly = H - 20
    for label, color, _ in series:
        P.append(f'<rect x="{lx}" y="{ly-8}" width="11" height="3" fill="{color}" rx="1.5"/>')
        P.append(f'<text x="{lx+15}" y="{ly-2}" font-size="11" fill="#39465A">{esc(label)}</text>')
        lx += 26 + len(str(label)) * 8.0
    P.append('</svg>')
    return ''.join(P)


def svg_bar(groups, series, W=650, H=300, title='', vfmt='{:+.1f}%', zero=True, yfmt='{:.0f}'):
    PL, PR, PT, PB = 66, 18, 32, 58
    iw, ih = W - PL - PR, H - PT - PB
    vals = [v for _, _, vs in series for v in vs if v is not None]
    vmin, vmax = min(vals + ([0] if zero else [])), max(vals + ([0] if zero else []))
    if vmax - vmin < 1e-9:
        vmax = vmin + 1
    pad = (vmax - vmin) * 0.18
    vmin -= pad; vmax += pad
    Y = lambda v: PT + ih - (v - vmin) / (vmax - vmin) * ih
    ng, ns = len(groups), len(series)
    gw = iw / ng
    bw = min(38, gw * 0.72 / ns)
    P = [f'<svg viewBox="0 0 {W} {H}" style="width:100%;height:auto;font-family:inherit">']
    P.append(f'<rect x="{PL}" y="{PT}" width="{iw}" height="{ih}" fill="#FCFDFE" stroke="#E3E8EF"/>')
    for k in range(5):
        v = vmin + (vmax - vmin) * k / 4
        y = Y(v)
        P.append(f'<line x1="{PL}" y1="{y:.1f}" x2="{PL+iw}" y2="{y:.1f}" stroke="#EEF1F5"/>')
        P.append(f'<text x="{PL-7}" y="{y+4:.1f}" font-size="10.5" fill="#7A8794" '
                 f'text-anchor="end">{yfmt.format(v)}</text>')
    yz = Y(0)
    P.append(f'<line x1="{PL}" y1="{yz:.1f}" x2="{PL+iw}" y2="{yz:.1f}" stroke="#9AA5B1" stroke-width="1.2"/>')
    for gi, g in enumerate(groups):
        cx = PL + gw * (gi + 0.5)
        tot = bw * ns
        for si, (label, color, vs) in enumerate(series):
            v = vs[gi]
            if v is None:
                continue
            x = cx - tot / 2 + bw * si + bw * 0.10
            y = Y(v); h = abs(Y(0) - y)
            yy = min(y, Y(0))
            P.append(f'<rect x="{x:.1f}" y="{yy:.1f}" width="{bw*0.8:.1f}" height="{max(h,1):.1f}" '
                     f'fill="{color}" rx="2"/>')
            ty = yy - 4 if v >= 0 else yy + h + 12
            P.append(f'<text x="{x+bw*0.4:.1f}" y="{ty:.1f}" font-size="10" fill="#39465A" '
                     f'text-anchor="middle">{vfmt.format(v)}</text>')
        P.append(f'<text x="{cx:.1f}" y="{PT+ih+18}" font-size="11.5" fill="#39465A" '
                 f'text-anchor="middle">{esc(g)}</text>')
    P.append(f'<text x="{PL}" y="17" font-size="12.5" font-weight="600" fill="#1F4E79">{esc(title)}</text>')
    lx = PL + 8; ly = H - 8
    for label, color, _ in series:
        P.append(f'<rect x="{lx}" y="{ly-10}" width="11" height="11" fill="{color}" rx="2"/>')
        P.append(f'<text x="{lx+15}" y="{ly-1}" font-size="11" fill="#39465A">{esc(label)}</text>')
        lx += 30 + len(str(label)) * 8.4
    P.append('</svg>')
    return ''.join(P)


def tbl(headers, rows, widths=None):
    a = ['<table>']
    if widths:
        a.append('<colgroup>' + ''.join(f'<col style="width:{w}">' for w in widths) + '</colgroup>')
    a.append('<thead><tr>' + ''.join(f'<th>{esc(h)}</th>' for h in headers) + '</tr></thead><tbody>')
    for row in rows:
        rcls = ''
        if isinstance(row, tuple):
            row, rcls = row
        tds = []
        for v in row:
            s = str(v); ks = []
            while True:
                if s.startswith('@@+'):
                    ks.append('up'); s = s[3:]
                elif s.startswith('@@-'):
                    ks.append('dn'); s = s[3:]
                elif s.startswith('@@h'):
                    ks.append('hl'); s = s[3:]
                else:
                    break
            k = f' class="{" ".join(ks)}"' if ks else ''
            tds.append(f'<td{k}>{s}</td>')
        rc = f' class="{rcls}"' if rcls else ''
        a.append(f'<tr{rc}>' + ''.join(tds) + '</tr>')
    a.append('</tbody></table>')
    return ''.join(a)


def ynat(v):
    return ('@@+' if v > 0 else ('@@-' if v < 0 else '')) + f'{v:+,.0f}'


def pct(x, d=1):
    return ('@@+' if x > 0 else ('@@-' if x < 0 else '')) + f'{x:+.{d}f}%'


def card(label, value, sub='', color='#1F4E79'):
    return (f'<div class="card"><div class="cl">{label}</div>'
            f'<div class="cv" style="color:{color}">{value}</div>'
            f'<div class="cs">{sub}</div></div>')


def rc(v):
    return RED if v > 0 else (GRN if v < 0 else '#20303F')


def main():
    H = []; A = H.append
    a0 = R['alloc_OLD']; a1 = R['alloc_NEW']
    S1 = {nm: RS[nm]['NEW']['stat'] for nm in PRODS}
    best = max(PRODS, key=lambda n: S1[n]['ret_pct'])
    worst = min(PRODS, key=lambda n: S1[n]['ret_pct'])

    A('''<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>赢益共振 v9 · 60D 单品种独立版 测试报告</title>
<style>
*{box-sizing:border-box}
body{margin:0;background:#F4F6F9;color:#20303F;
 font-family:-apple-system,"Segoe UI","Microsoft YaHei",sans-serif;line-height:1.7}
.wrap{max-width:1080px;margin:0 auto;padding:0 22px 70px}
header{background:linear-gradient(135deg,#123A5E,#1F6FA8);color:#fff;padding:38px 22px 30px;margin-bottom:26px}
header .in{max-width:1080px;margin:0 auto}
header h1{margin:0 0 8px;font-size:25px;letter-spacing:.5px}
header .sub{opacity:.9;font-size:13.5px}
h2{font-size:18.5px;margin:38px 0 14px;padding-left:12px;border-left:5px solid #1F6FA8;color:#123A5E}
h3{font-size:15.5px;margin:22px 0 10px;color:#1F4E79}
p{margin:9px 0;font-size:14px}
.note{background:#FFFDF3;border:1px solid #F0E3B8;border-radius:8px;padding:12px 15px;
 font-size:13.3px;color:#6B5A21;margin:12px 0}
.warn{background:#FEF3F2;border:1px solid #F5C6C0;border-radius:8px;padding:13px 16px;
 font-size:13.5px;color:#8C2F22;margin:14px 0}
.ok{background:#F1F8F3;border:1px solid #C4E3CE;border-radius:8px;padding:13px 16px;
 font-size:13.5px;color:#1E5C36;margin:14px 0}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(172px,1fr));gap:12px;margin:16px 0}
.card{background:#fff;border:1px solid #E3E8EF;border-radius:10px;padding:14px 15px;
 box-shadow:0 1px 3px rgba(20,50,80,.05)}
.cl{font-size:12px;color:#7A8794;margin-bottom:5px}
.cv{font-size:22px;font-weight:700;letter-spacing:.3px}
.cs{font-size:11.5px;color:#96A0AC;margin-top:4px}
table{width:100%;border-collapse:collapse;background:#fff;margin:12px 0;font-size:12.7px;
 border:1px solid #E3E8EF;border-radius:8px;overflow:hidden}
th{background:#1F4E79;color:#fff;padding:9px 7px;font-weight:600;font-size:12.2px;text-align:center;
 border-right:1px solid rgba(255,255,255,.16)}
td{padding:7px 8px;border-top:1px solid #EDF1F5;text-align:center;white-space:nowrap}
tbody tr:hover{background:#F7FAFD}
tr.op td{border-top:1.6px solid #CFD9E4}
tr.mk td:first-child{color:#B7C0CB;font-weight:400}
tr.mk{background:#FBFCFE}
td:first-child{text-align:left;font-weight:600;color:#2C3E50}
.up{color:#C0392B;font-weight:600}
.dn{color:#1E8449;font-weight:600}
.hl{background:#FFF7E0;font-weight:700}
.chart{background:#fff;border:1px solid #E3E8EF;border-radius:10px;padding:14px 12px 6px;margin:16px 0}
ul{font-size:14px;padding-left:22px} li{margin:5px 0}
code{background:#EEF2F7;padding:1.5px 6px;border-radius:4px;font-size:12.5px;
 font-family:ui-monospace,Consolas,monospace;color:#1F4E79}
.prod{background:#fff;border:1px solid #E3E8EF;border-radius:10px;padding:16px 18px 8px;margin:18px 0}
.prod h3{margin-top:0}
.scope{background:#E8F1F8;border:1px solid #BFD9EC;border-radius:8px;padding:14px 18px;margin:16px 0;
 font-size:14px;color:#154360}
.scope b{color:#123A5E}
</style></head><body>''')

    A(f'''<header><div class="in">
<h1>赢益共振 v9 · 60D 单品种独立版</h1>
<div class="sub">方案 D 固定比例风险 3% · 周期 60 分钟 · ★优选配置（零闸门 + 0.5 跳滑点）·
高低阈已放开（KB 2.5 → 2.0）· 纯碱 / 红枣 / 花生 / 烧碱 各一个独立 30 万账户 · 生成于 2026-10-11</div>
</div></header><div class="wrap">''')

    # ============ 结论
    A(f'''<div class="ok"><b>一句话：</b>四个品种各用 30 万独立跑，全部为正收益；
合计盈亏 <b>+{a1['pnl']:,.0f} 元</b>（收益率 <b>+{a1['ret_pct']:.1f}%</b>，投入 120 万）。
其中 <b>{best}</b> 最强（{S1[best]['ret_pct']:+.1f}%），<b>{worst}</b> 最弱（{S1[worst]['ret_pct']:+.1f}%）。</div>''')
    A('<div class="cards">')
    for nm in PRODS:
        s = S1[nm]
        A(card(f'{nm} · {R["data"][nm]["code"]}', f'{s["ret_pct"]:+.1f}%',
               f'{s["n"]} 笔 · 胜率 {s["win"]:.0f}% · 回撤 {s["mdd_mtm_pct"]:.2f}%',
               rc(s['ret_pct'])))
    A('</div>')

    # ============ 一、范围
    A('<h2>一、本版只做这一件事</h2>')
    A('''<div class="scope">
按指定口径，本报告<b>只包含一种组合</b>，不再提供任何其他选项：<br><br>
<b>方案</b>：D 固定比例风险 <b>3%</b>（不再给 C 方案）<br>
<b>周期</b>：<b>60 分钟</b>（不再给 15 / 30 / 日线）<br>
<b>信号配置</b>：★优选 = 闸门 <code>GATEW=0</code>（关闭）+ 出场滑点 <b>0.5 跳</b>（不再给旧默认 0.30 / 保守 CON）<br>
<b>高低阈</b>：<code>KB = 2.0</code>（<b>已按要求放开</b>，原值 2.5）→ 低阈 = <code>CEN − 2.0×WV</code>，高阈 = <code>CEN + 2.0×WV</code><br>
<b>资金</b>：纯碱 30 万 / 红枣 30 万 / 花生 30 万 / 烧碱 30 万，<b>四个独立账户</b>
</div>''')
    A('''<p>报告中出现的两组对照，都是本次按您要求所做的改动，不是方案对照：
<b>①放开高低阈</b>（<code>KB</code> 2.5→2.0，见第二节）与
<b>②资金使用参数</b>（保证金上限 60%→80%，见第三节）。</p>''')

    # ============ 二、放开高低阈
    A('<h2>二、放开高低阈（本轮核心）</h2>')
    A('''<p>v9 的入场位置由两条轨道定义：<b>高阈</b> <code>UPB = CEN + KB×WV</code>
（价格涨到此处挂空、博回调）、<b>低阈</b> <code>DNB = CEN − KB×WV</code>
（价格跌到此处挂多、博反弹）。<code>KB</code> 是轨道宽度系数，原值 <b>2.5</b>。</p>
<p>本轮按您的要求「放开高低阈」，把 <code>KB</code> 收窄 —— 阈值离均线中枢更近、更容易被触及，
入场机会随之增多。<b>先看放开到什么程度最合适。</b></p>''')
    A('<h3>放开程度扫描（60 分钟 · 四品种 · 各 30 万 · D 方案 3% · ★优选）</h3>')
    KS = json.load(open(os.path.join(CLI, 'kb_scan.json'), encoding='utf-8'))
    rows = []
    for r in KS:
        ma = r.get('mode') == 'ma'
        if ma:
            pos = '阈宽=0 + 取消上下互斥'
        elif r['kb'] == 0:
            pos = '阈宽=0（仅退化为均线）'
        else:
            pos = f'均线 ± {r["kb"]:.2f} × WV'
        if not ma and abs(r['kb'] - 2.5) < 1e-9:
            pos = '<b>' + pos + '（原值）</b>'
        if not ma and abs(r['kb'] - 2.0) < 1e-9:
            pos = '@@h' + pos + '（★本次采用）'
        rows.append([pos, f"{r['sig']}", f"{r['n']}", f"{r['win']:.1f}%", f"{r['pf']:.2f}",
                     f"{r['exp_r']:+.3f}", pct(r['ret']), f"{r['mdd']:.2f}%", f"{r['calmar']:.2f}"])
    A(tbl(['高低阈位置', '信号数', '成交', '胜率', 'PF', '期望R', '四账户收益率', '回撤', 'Calmar'],
          rows, ['25%', '8%', '7%', '9%', '7%', '9%', '13%', '9%', '8%']))
    A(f'''<div class="warn"><b>放开越彻底，效果越差——这一点必须说清楚。</b><br>
高低阈不是"限制"，它是<b>入场优势区的定义</b>：只有跌到低阈才值得博反弹、涨到高阈才值得博回调。
阈值收窄＝在越来越没有价格优势的位置也进场，于是胜率与赔率同步下滑：<br><br>
· <b>2.5 → 2.0</b>（本次采用）：胜率 74.0% → 72.4%，期望 R +0.795 → +0.641，
收益 <b>+37.3% → +28.1%</b>；<br>
· <b>2.0 → 1.0</b>（再放一半）：收益掉到 +14.3%；<br>
· <b>彻底放开</b>（阈宽归零 + 取消上下互斥）：信号从 73 笔翻倍到 <b>145 笔</b>，
但胜率崩到 <b>52.4%</b>、PF <b>0.96</b>、收益 <b>−2.3%</b>、回撤放大到 <b>11.48%</b>
—— 手续费与滑点把利润全部吃光。<br><br>
另有一处<b>结构性耦合</b>要提醒：窗口关窗条件 <code>C &gt; DNB + TGTW×WV</code> 里含
<code>DNB（= CEN − KB×WV）</code>，KB 缩到 0 时关窗门槛升到 <code>CEN + 3×WV</code>，
窗口几乎再也关不上，信号数反而从 73 笔<b>塌到 2 笔</b>。所以"放开"并不单调地等于"信号变多"。
</div>''')

    # ============ 三、资金优化
    A('<h2>三、如何最合理地使用资金</h2>')
    A('''<h3>问题：钱被"保证金上限"卡住了</h3>
<p>D 方案的定义是「单笔最大亏损 = 当时权益的 3%」。理论上每笔都该按 3% 开足手数，
但实际会发现：<b>该开的手数开不出来</b>。原因有两个默认限制：</p>
<ul>
<li><code>MGTOT=0.60</code>：单笔保证金占用不得超过权益的 60%。</li>
<li><code>MAXLOT=50</code>：单笔最多 50 手。</li>
</ul>''')
    rows = []
    for nm in PRODS:
        d = DG[f'{nm}|OLD']
        rows.append([nm, f"{d['lots_risk_avg']:.1f} 手", f"{d['lots_mgtot_avg']:.1f} 手",
                     f"{d['lots_act_avg']:.1f} 手", f"{d['bind']}/{d['n']}",
                     f"{100*d['risk_use_pct']/3:.1f}%"])
    A(tbl(['品种', '按 3% 风险应开', '保证金上限允许开', '实际开出', '被压制的笔数',
           '风险预算利用率'], rows, ['12%', '18%', '20%', '16%', '17%', '17%']))
    A(f'''<div class="warn">最突出的是<b>花生</b>：按 3% 风险该开 <b>69.4 手</b>，
保证金上限只允许 <b>42.8 手</b> → 实际只开 42.3 手，
<b>风险预算只用了 66.5%</b>（实际单笔风险 2.00% 而不是 3.00%），
23 笔里有 <b>22 笔</b>都被砍过手数。资金明显没用足。</div>''')

    A('<h3>修正：在 D 方案框架内放宽资金上限</h3>')
    A('''<p>关键认识：<b>这里放宽的不是"风险"，而是"资金占用上限"。</b>
单笔风险预算始终是权益的 3% —— 提高保证金上限，只是让原本就该开的仓位能真正开出来。</p>''')
    A(tbl(['参数', '原值', '★推荐值', '为什么这么改'], [
        ['保证金占用上限 MGTOT', '60%', '@@h80%',
         '单品种同时只持 1 仓，不存在四品种叠加占用；留 20% 缓冲应对盘中浮亏与追加保证金'],
        ['单笔最大手数 MAXLOT', '50 手', '@@h100 手',
         '纯碱 / 花生多次撞到 50 手天花板；提高到 100 手只是解除这个不必要的限制'],
    ], ['26%', '12%', '14%', '48%']))

    A('<h3>效果：风险预算用足了，收益也上来了</h3>')
    v0 = [RS[nm]['OLD']['stat']['ret_pct'] for nm in PRODS]
    v1 = [RS[nm]['NEW']['stat']['ret_pct'] for nm in PRODS]
    A('<div class="chart">' + svg_bar(
        PRODS, [('优化前（保证金上限 60%）', GRY, v0), ('★推荐（保证金上限 80%）', RED, v1)],
        W=680, H=310, title='四品种收益率：资金参数优化前 vs 优化后（每品种独立 30 万）') + '</div>')

    u0 = [100 * DG[f'{nm}|OLD']['risk_use_pct'] / 3 for nm in PRODS]
    u1 = [100 * DG[f'{nm}|NEW']['risk_use_pct'] / 3 for nm in PRODS]
    A('<div class="chart">' + svg_bar(
        PRODS, [('优化前', GRY, u0), ('★推荐', BLU, u1)],
        W=680, H=300, title='风险预算利用率（实际单笔风险 ÷ 3%）：越接近 100% 说明资金用得越充分',
        vfmt='{:.1f}%', zero=False, yfmt='{:.0f}%') + '</div>')

    rows = []
    for nm in PRODS:
        d0 = DG[f'{nm}|OLD']; d1 = DG[f'{nm}|NEW']
        s0 = RS[nm]['OLD']['stat']; s1 = RS[nm]['NEW']['stat']
        rows.append([nm, f"{d0['bind']}/{d0['n']} → {d1['bind']}/{d1['n']}",
                     f"{100*d0['risk_use_pct']/3:.1f}% → {100*d1['risk_use_pct']/3:.1f}%",
                     f"{d0['mg_peak_pct']:.1f}% → {d1['mg_peak_pct']:.1f}%",
                     pct(s0['ret_pct']) + ' → ' + f"{s1['ret_pct']:+.1f}%",
                     f"{s0['calmar']:.2f} → {s1['calmar']:.2f}"])
    A(tbl(['品种', '被压制笔数', '风险利用率', '保证金峰值', '收益率', 'Calmar'],
          rows, ['10%', '18%', '21%', '19%', '20%', '16%']))
    A(f'''<div class="note">四账户合计盈亏从 <b>+{a0['pnl']:,.0f} 元</b> 提升到
<b>+{a1['pnl']:,.0f} 元</b>（多赚 <b>{a1['pnl']-a0['pnl']:+,.0f} 元</b>），
收益率 <b>+{a0['ret_pct']:.1f}% → +{a1['ret_pct']:.1f}%</b>。<br>
代价是保证金占用峰值从约 60% 升到约 78%，回撤小幅上升
（纯碱 {RS['纯碱']['OLD']['stat']['mdd_mtm_pct']:.2f}%→{RS['纯碱']['NEW']['stat']['mdd_mtm_pct']:.2f}%、
花生 {RS['花生']['OLD']['stat']['mdd_mtm_pct']:.2f}%→{RS['花生']['NEW']['stat']['mdd_mtm_pct']:.2f}%）。<br>
<b>烧碱是唯一"性价比下降"的品种</b>：它的瓶颈本来在风险预算而非保证金，提高上限只让它多开
{RS['烧碱']['NEW']['stat']['avg_lots']-RS['烧碱']['OLD']['stat']['avg_lots']:.2f} 手，
收益略升（+{RS['烧碱']['OLD']['stat']['ret_pct']:.1f}%→+{RS['烧碱']['NEW']['stat']['ret_pct']:.1f}%）
但 Calmar 从 {RS['烧碱']['OLD']['stat']['calmar']:.2f} 降到 {RS['烧碱']['NEW']['stat']['calmar']:.2f}。
若想更保守，烧碱可单独保持 60% 上限。</div>''')

    # ============ 四、四品种结果
    A('<h2>四、四品种结果（各 30 万独立账户）</h2>')
    rows = []
    for nm in PRODS:
        s = S1[nm]; ex = RS[nm]['NEW']['extra']; dg = DG[f'{nm}|NEW']
        rows.append([nm, R['data'][nm]['code'], f"{s['n']}", f"{s['win']:.1f}%", f"{s['pf']:.2f}",
                     f"{ex['exp_r']:+.3f}", f"{s['avg_lots']:.1f}", f"{dg['max_lots']}",
                     f"{s['eq_end']:,.0f}", pct(s['ret_pct']), pct(s['ann_pct']),
                     f"{s['mdd_mtm_pct']:.2f}%", f"{s['calmar']:.2f}", f"{s['sharpe']:.2f}"])
    rows.append(['@@h四账户合计', '—', f"{a1['n']}", f"{a1['win']:.1f}%", '—', '—', '—', '—',
                 f"{a1['eq_end']:,.0f}", '@@h' + pct(a1['ret_pct']), '—', '—', '—', '—'])
    A(tbl(['品种', '合约', '成交', '胜率', 'PF', '期望R', '均手', '最大手', '终值(元)',
           '收益率', '年化', '含浮亏回撤', 'Calmar', 'Sharpe'], rows,
          ['10%', '10%', '6%', '7%', '6%', '7%', '6%', '7%', '11%', '9%', '9%', '10%', '8%', '8%']))
    A('''<p class="note">「含浮亏回撤」= 已实现权益 + 在持仓浮亏的口径下测得的回撤（浮亏按初始止损价截断），
比只看已实现回撤更接近真实账户体验。</p>''')

    cmt = {
        '纯碱': '<b>本轮放开高低阈受损最明显的品种</b>：胜率 77.3%→68.2%、PF 3.95→1.80、'
                '收益 +47.5%→+22.2%，含浮亏回撤 8.16% 也是四品种最高。信号仍最密（22 笔）。',
        '红枣': '胜率 87.5%、PF 6.40 均为四品种最高，且是<b>唯一因放开阈值而受益</b>的品种'
                '（+16.2%→+19.7%）；但只有 <b>8 笔</b>，样本最薄，指标说服力有限。',
        '花生': '笔数最多（25 笔）、收益最高 <b>+42.1%</b>、PF 2.77、回撤 6.43%，'
                '四品种里最均衡；受放开影响相对小（+56.6%→+42.1%）。',
        '烧碱': '胜率 66.7% 为四品种最低，但 PF 2.13、收益 +28.3% 尚可，'
                '基本不受放开影响（+28.9%→+28.3%）。',
    }
    for nm in PRODS:
        d = RS[nm]['NEW']; s = d['stat']; ex = d['extra']; d0 = RS[nm]['OLD']
        A(f'<div class="prod"><h3>{nm}（{R["data"][nm]["code"]}）</h3>')
        A('<div class="cards">')
        A(card('收益率', f'{s["ret_pct"]:+.1f}%', f'终值 {s["eq_end"]:,.0f} 元', rc(s['ret_pct'])))
        A(card('成交 / 胜率', f'{s["n"]} 笔 · {s["win"]:.0f}%', f'PF {s["pf"]:.2f}'))
        A(card('含浮亏回撤', f'{s["mdd_mtm_pct"]:.2f}%', f'Calmar {s["calmar"]:.2f}'))
        A(card('出场结构', f'{ex["trl"]:.0f}% 移动止盈',
               f'止损 {ex["sl"]:.0f}% / 目标 {ex["tp"]:.0f}%'))
        A('</div>')
        t0 = min(c['curve'][0][0] for c in (d0, d) if c['curve'])
        curves = [
            ('★推荐·已实现权益', RED, [(t2d(t, t0), v) for t, v in d['curve']]),
            ('★推荐·含浮亏权益', GRY, [(t2d(t, t0), v) for t, v in d['mtm']]),
            ('优化前·已实现权益', BLU, [(t2d(t, t0), v) for t, v in d0['curve']]),
        ]
        A('<div class="chart">' + svg_line(
            curves, title=f'{nm} 独立账户权益曲线（本金 30 万 · D 方案 3% · 60 分钟 ★优选）',
            base=CAP0, xlab='距首笔交易的天数') + '</div>')
        A(f'<p>{cmt[nm]}</p></div>')

    # ============ 五、逐笔交易记录
    A('<h2>五、各品种逐笔交易记录</h2>')
    A('''<p>下面按品种给出<b>每一笔交易的完整记录</b>。一笔完整交易拆为两行：
<b>开仓行</b>（方向 <span class="up">开多</span> 或 <span class="dn">开空</span>）与
<b>平仓行</b>（方向 <span class="up">平多</span> 或 <span class="dn">平空</span>）。</p>
<ul>
<li><b>开多</b> ＝ 买入开仓，建立多头持仓；<b>平多</b> ＝ 卖出平仓，了结多头持仓。</li>
<li><b>开空</b> ＝ 卖出开仓，建立空头持仓；<b>平空</b> ＝ 买入平仓，了结空头持仓。</li>
<li>方向列：多系（开多 / 平多）标<span class="up">红色</span>，空系（开空 / 平空）标<span class="dn">绿色</span>。</li>
<li>盈亏列：<span class="up">红色为盈利</span>、<span class="dn">绿色为亏损</span>（国内期货惯例）。</li>
<li><b>保证金</b>＝开仓时实际占用的保证金；<b>本笔风险</b>＝按当时权益 3% 计算的最大可亏额度
（＝入场价与初始止损价之差 × 手数 × 合约乘数）。</li>
<li>开仓行与平仓行成对出现，平仓行的「平仓后权益」为该笔了结后的账户权益（复利基数）。</li>
</ul>''')
    FLOW_W = ['4.5%', '14.5%', '7%', '8%', '5%', '10.5%', '9.5%', '10.5%', '7%', '9%', '10%']
    for nm in PRODS:
        d = RS[nm]['NEW']; tr = d['taken']; s = d['stat']; ex = d['extra']
        A(f'<h3>{nm}（{R["data"][nm]["code"]}）· 共 {len(tr)} 笔 · 独立账户本金 30 万</h3>')
        rows = []
        for i, t in enumerate(tr, 1):
            lg = t['dir'] > 0
            op_d = '@@+开多' if lg else '@@-开空'
            cl_d = '@@+平多' if lg else '@@-平空'
            rows.append(([f'<b>{i}</b>', str(t['et'])[:16], op_d, f"{t['ep']:.0f}", f"{t['lots']}",
                          f"{t['mg_used']:,.0f}", f"{t['risk_used']:,.0f}", '—', '—', '—', '—'], 'op'))
            rows.append((['↳', str(t['xt'])[:16], cl_d, f"{t['xp']:.0f}", f"{t['lots']}", '—', '—',
                          ynat(t['pnl']), f"{t['net_r']:+.3f}", t['reason'],
                          f"{t['eq_after']:,.0f}"], 'mk'))
        A(tbl(['#', '时间', '方向', '成交价', '手数', '保证金(元)', '本笔风险(元)',
               '本笔盈亏(元)', '盈亏(R)', '出场原因', '平仓后权益(元)'], rows, FLOW_W))
        A(f'''<p class="note">{nm} 小结：{len(tr)} 笔（胜率 {s['win']:.1f}%），
累计净盈亏 <b>{s['eq_end']-CAP0:+,.0f} 元</b>，期末权益 <b>{s['eq_end']:,.0f} 元</b>；
出场结构：移动止盈 {ex['trl']:.0f}% / 初始止损 {ex['sl']:.0f}% / 到达目标 {ex['tp']:.0f}%。</p>''')

    # ============ 六、出场结构与成本
    A('<h2>六、出场结构与成本</h2>')
    rows = []
    for nm in PRODS:
        ex = RS[nm]['NEW']['extra']
        tot = ex['fee_yuan'] + ex['slip_yuan']
        rows.append([nm, f"{ex['sl']:.1f}%", f"{ex['trl']:.1f}%", f"{ex['tp']:.1f}%",
                     f"{ex['long']:.1f}%", f"{ex['cost_yuan']:,.1f}", f"{ex['fee_yuan']:,.1f}",
                     f"{ex['slip_yuan']:,.1f}", f"{ex['cost_pct_of_wv']:.2f}%"])
    A(tbl(['品种', '初始止损%', '移动止盈%', '到达目标%', '做多占比%', '成本合计(元/手)',
           '手续费(元/手)', '滑点(元/手)', '成本占WV'], rows,
          ['10%', '12%', '12%', '12%', '12%', '15%', '14%', '13%', '12%']))
    _tr = [RS[nm]['NEW']['extra']['trl'] for nm in PRODS]
    _sl = [RS[nm]['NEW']['extra']['sl'] for nm in PRODS]
    A(f'''<p class="note">四个品种都是「移动止盈」占主导（{min(_tr):.0f}%~{max(_tr):.0f}%），
初始止损 {min(_sl):.0f}%~{max(_sl):.0f}%，说明阶梯锁盈在起作用；
「到达目标」出场占比为 0%（本配置下没有一笔直达目标位）。
出场滑点已降到 0.5 跳，滑点只占成本 28%~41%。<code>WV</code> = 单笔初始风险（点）。</p>''')

    # ============ 七、局限
    A('<h2>七、必须知道的局限</h2>')
    A(f'''<div class="warn"><ul>
<li><b>放开高低阈是"用收益换机会"</b>：<code>KB</code> 由 2.5 收窄到 2.0 后，成交从 73 笔增到 76 笔，
但胜率 74.0%→72.4%、期望 R +0.795→+0.641、收益 +37.3%→+28.1%。若想要更高收益，
把 <code>KB</code> 调回 2.5 即可（详见第二节扫描表）。</li>
<li><b>样本期 8~9 个月</b>（{R['data']['纯碱']['rng']}），年化收益率是短样本外推，不能当可持续预期。</li>
<li><b>红枣只有 8 笔</b>交易，胜率 87.5% / PF 6.40 这类指标统计意义弱。</li>
<li><b>保证金占用峰值已到约 78%</b>：一旦行情剧烈不利、浮亏扩大，可能触及追加保证金通知。若不能接受，把 <code>MGTOT</code> 调回 0.6~0.7。</li>
<li><b>提高资金上限会同步放大回撤</b>：优化后纯碱回撤
{RS['纯碱']['OLD']['stat']['mdd_mtm_pct']:.2f}%→{RS['纯碱']['NEW']['stat']['mdd_mtm_pct']:.2f}%、
烧碱 {RS['烧碱']['OLD']['stat']['mdd_mtm_pct']:.2f}%→{RS['烧碱']['NEW']['stat']['mdd_mtm_pct']:.2f}%。</li>
<li><b>滑点是最难估算的一项</b>：本配置假设止损/移动止盈出场只滑 0.5 跳，若实际每次跨 1 跳，收益会明显下降。</li>
<li><b>D 方案（3% 风险）本身是激进档</b>：单笔最大亏损可达权益 3%，连续 10 笔亏损即回撤约 26%。</li>
</ul></div>''')

    # ============ 八、交付物
    A('<h2>八、交付物</h2>')
    A(f'''<ul>
<li><code>赢益共振_60D单品种独立版测试_2026-10-11.xlsx</code> —— 14 张表，含 4 张原生权益曲线折线图：
说明、核心指标、资金使用诊断、权益曲线×4、逐笔明细×4、月度收益、参数速查、数据区间。</li>
<li><code>赢益共振_60D单品种独立版报告.html</code> —— 本报告，含<b>第五节各品种逐笔交易记录</b>
（每笔拆为「开仓行 + 平仓行」，方向以开多 / 开空 / 平多 / 平空标注）。</li>
<li><code>赢益共振_v9.XTRD</code> —— 指标文件（信号部分与本次测试完全一致；<code>MGTOT</code>/<code>MAXLOT</code> 属仓位参数，需在你的下单环节按 80% / 100 手执行）。</li>
<li>脚本：<code>bt_single_d.py</code>（回测）、<code>diag_fund.py</code>（资金诊断）、
<code>make_sd_xlsx.py</code>（Excel）、<code>make_sd_report.py</code>（本报告）、
原始数据 <code>single_d_result.json</code>。</li>
</ul>''')

    A('</div></body></html>')

    html = ''.join(H)
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'已生成 {OUT}  大小 {len(html)/1024:.0f} KB  @@残留 {html.count("@@")}')


if __name__ == '__main__':
    main()
