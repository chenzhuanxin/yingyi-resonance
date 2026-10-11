# -*- coding: utf-8 -*-
"""make_sd_xlsx.py —— 「60D 单品种独立版」Excel（精简：只 D 方案 / 只 60 分钟 / 只 ★优选 / 每品种 30 万）

数据源：single_d_result.json
产出  ：D:/360安全浏览器下载/赢益共振/赢益共振_60D单品种独立版测试_2026-10-11.xlsx
"""
import sys, os, json
sys.path.insert(0, r'C:/Users/Administrator/gh-cli')
import numpy as np
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.chart import LineChart, Reference
import mainspec as MS

CLI = r'C:/Users/Administrator/gh-cli'
OUT = r'D:/360安全浏览器下载/赢益共振/赢益共振_60D单品种独立版测试_2026-10-11.xlsx'
CAP0 = 300000.0
PRODS = [MS.NAME[p] for p in MS.PROD]
F_LAB = {'OLD': '优化前（保证金上限 60% / 单笔 50 手）',
         'NEW': '★推荐（保证金上限 80% / 单笔 100 手）'}

H_FILL = PatternFill('solid', fgColor='1F4E79')
H_FONT = Font(color='FFFFFF', bold=True, size=10.5)
OK_FILL = PatternFill('solid', fgColor='FBE3E3')
BAD_FILL = PatternFill('solid', fgColor='E1F2E5')
STAR_FILL = PatternFill('solid', fgColor='FFF0D0')
KEY_FILL = PatternFill('solid', fgColor='FFF7E0')
THIN = Side(style='thin', color='BFBFBF')
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
C = Alignment(horizontal='center', vertical='center')
L = Alignment(horizontal='left', vertical='center')


def title(ws, r, txt, ncol, size=13):
    ws.cell(r, 1, txt).font = Font(bold=True, size=size, color='1F4E79')
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=ncol)
    return r + 1


def note(ws, r, txt, ncol):
    ws.cell(r, 1, txt).font = Font(italic=True, size=9.5, color='7F7F7F')
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=ncol)
    return r + 1


def para(ws, r, txt, ncol, size=10.5, bold=False):
    ws.cell(r, 1, txt).font = Font(size=size, bold=bold)
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=ncol)
    return r + 1


def head(ws, r, cols, widths=None):
    for j, c in enumerate(cols, 1):
        cell = ws.cell(r, j, c)
        cell.fill = H_FILL; cell.font = H_FONT; cell.alignment = C; cell.border = BOX
    ws.row_dimensions[r].height = 32
    if widths:
        for j, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(j)].width = w
    return r + 1


def prow(ws, r, vals, fmts=None, fill=None, bold=False):
    for j, v in enumerate(vals, 1):
        cell = ws.cell(r, j, v)
        cell.border = BOX
        cell.alignment = C if j > 1 else L
        if fmts and j - 1 < len(fmts) and fmts[j - 1]:
            cell.number_format = fmts[j - 1]
        if fill:
            cell.fill = fill
        if bold:
            cell.font = Font(bold=True)
    return r + 1


def align(curves, cap0):
    ts = sorted(set(t for c in curves for t, _ in c))
    out = []
    for c in curves:
        d = dict(c); last = cap0; vals = []
        for t in ts:
            if t in d:
                last = d[t]
            vals.append(last)
        out.append(vals)
    return ts, out


def main():
    R = json.load(open(os.path.join(CLI, 'single_d_result.json'), encoding='utf-8'))
    RS = R['res']; DG = R['diag']; M = R['meta']
    wb = Workbook(); wb.remove(wb.active)

    # ==================== 说明
    ws = wb.create_sheet('说明'); r = 1
    r = title(ws, r, '赢益共振 v9 · 60D 单品种独立版 —— 测试报告', 10, size=15)
    r = note(ws, r, '生成 2026-10-11 · 只 D 方案（风险 3%）· 只 60 分钟 · 只 ★优选配置（零闸门 + 0.5 跳）· 每品种独立 30 万', 10)
    r += 1
    r = title(ws, r, '一、本版范围（严格按指定口径，无其他方案/周期/配置）', 10, size=12)
    for s in [
        '· 仓位方案：D 固定比例风险 3%（单笔最大亏损 = 当时权益 × 3%）',
        '· 周期：60 分钟（不再提供 15 / 30 / 日线）',
        '· 信号配置：★优选 = 成本闸门 GATEW=0（关闭）+ 出场滑点 0.5 跳',
        '   （不再提供旧默认 GATEW=0.30 / 保守 CON 两档）',
        '· 资金：纯碱 30 万 / 红枣 30 万 / 花生 30 万 / 烧碱 30 万，四个独立账户，互不影响',
        '· 均线参数 NMID=40 / 波动参数 NAV=14；手续费与保证金取自 GitHub 仓库快照',
    ]:
        r = para(ws, r, s, 10)
    r += 1
    r = title(ws, r, '二、本次新增：让资金用得更合理', 10, size=12)
    r = para(ws, r, '诊断发现问题：默认「单笔保证金占用上限 60%」把本该开出的仓位砍掉了 ——', 10)
    r = para(ws, r, '   花生想按 3% 风险开 69 手，却因保证金上限只能开 42 手，实际风险只用到 2.00%（应为 3%）；', 10)
    r = para(ws, r, '   纯碱/红枣/花生还多次撞上「单笔最大 50 手」的天花板。资金被闲置，风险预算没用足。', 10)
    r += 1
    r = para(ws, r, '修正：在 D 方案框架内把资金参数改为', 10, bold=True)
    r = para(ws, r, '   保证金占用上限 MGTOT：60% → 80%（单笔最多占权益 80%，仍留 20% 缓冲）', 10)
    r = para(ws, r, '   单笔最大手数 MAXLOT：50 → 100（仅解除不必要的天花板）', 10)
    r += 1
    r = head(ws, r, ['品种', '风险预算利用率 优化前 → 优化后', '被保证金压制的笔数',
                     '收益率 优化前 → 优化后'], [9, 34, 20, 26])
    for nm in PRODS:
        d0 = DG.get(f'{nm}|OLD'); d1 = DG.get(f'{nm}|NEW')
        s0 = RS[nm]['OLD']['stat']; s1 = RS[nm]['NEW']['stat']
        r = prow(ws, r, [nm,
                         f"{100*d0['risk_use_pct']/3:.1f}% → {100*d1['risk_use_pct']/3:.1f}%",
                         f"{d0['bind']}/{d0['n']} → {d1['bind']}/{d1['n']}",
                         f"{s0['ret_pct']:+.1f}% → {s1['ret_pct']:+.1f}%"],
                 None, fill=KEY_FILL)
    r += 1
    r = para(ws, r, '注意：优化提高的是「资金使用效率」，不是「更激进的赌注」——'
                    '单笔风险预算始终是权益的 3%，只是让每笔真正按 3% 开足手数。', 10)
    r = para(ws, r, '副作用：保证金占用峰值从约 60% 升到约 78%，回撤略增（见 01_核心指标）。', 10)

    # ==================== 核心指标
    ws = wb.create_sheet('01_核心指标'); r = 1
    r = title(ws, r, '四品种各自独立 30 万 · D 方案 3% · 60 分钟 ★优选', 16, size=14)
    r = note(ws, r, '每行 = 一个品种的一个独立 30 万账户；优化前/后仅资金参数不同，信号完全相同', 16)
    r = head(ws, r, ['品种', '合约', '资金参数', '成交', '胜率', 'PF', '期望R', '均手', '最大手',
                     '实际风险%', '峰值保证金%', '终值(元)', '收益率', '年化',
                     '含浮亏回撤%', 'Calmar', 'Sharpe'],
             [8, 10, 30, 7, 8, 7, 8, 7, 7, 10, 12, 13, 10, 9, 12, 8, 8])
    for nm in PRODS:
        for ck in ('OLD', 'NEW'):
            d = RS[nm][ck]; s = d['stat']; ex = d['extra']; dg = d['diag']
            fill = STAR_FILL if ck == 'NEW' else None
            r = prow(ws, r, [nm, R['data'][nm]['code'], F_LAB[ck], s['n'], s['win'] / 100.0,
                             s['pf'], ex['exp_r'], s['avg_lots'], dg['max_lots'],
                             dg['risk_use_pct'] / 100.0, dg['mg_peak_pct'] / 100.0,
                             s['eq_end'], s['ret_pct'] / 100.0, s['ann_pct'] / 100.0,
                             s['mdd_mtm_pct'] / 100.0, s['calmar'], s['sharpe']],
                     [None, None, None, '0', '0.0%', '0.00', '+0.000', '0.00', '0',
                      '0.00%', '0.0%', '#,##0', '+0.0%', '+0.0%', '0.00%', '0.00', '0.00'],
                     fill=fill)
        r += 1
    a0 = R['alloc_OLD']; a1 = R['alloc_NEW']
    r = prow(ws, r, ['四账户合计', '—', '优化前（60%/50手）', a0['n'], a0['win'] / 100.0, '', '',
                     '', '', '', '', a0['eq_end'], a0['ret_pct'] / 100.0, '', '', '', ''],
             [None, None, None, '0', '0.0%', None, None, None, None, None, None,
              '#,##0', '+0.0%'], fill=KEY_FILL, bold=True)
    r = prow(ws, r, ['四账户合计', '—', '★推荐（80%/100手）', a1['n'], a1['win'] / 100.0, '', '',
                     '', '', '', '', a1['eq_end'], a1['ret_pct'] / 100.0, '', '', '', ''],
             [None, None, None, '0', '0.0%', None, None, None, None, None, None,
              '#,##0', '+0.0%'], fill=STAR_FILL, bold=True)
    r = note(ws, r, f'合计投入 120 万（四账户各 30 万）。优化后合计盈亏 {a1["pnl"]:+,.0f} 元，'
                    f'较优化前多 {a1["pnl"]-a0["pnl"]:+,.0f} 元。', 17)

    # ==================== 资金使用诊断
    ws = wb.create_sheet('02_资金使用诊断'); r = 1
    r = title(ws, r, '资金使用诊断：手数被谁约束、风险预算用了几成', 10, size=14)
    r = note(ws, r, '「风险允许手数」= 权益×3% ÷ 每手风险；「保证金允许手数」= 权益×上限 ÷ 单手保证金', 10)
    r = head(ws, r, ['品种', '资金参数', '风险允许手数', '保证金允许手数', '实际开仓手数',
                     '被压制的笔数', '风险预算利用率', '平均保证金占用', '峰值保证金占用'],
             [8, 30, 14, 15, 14, 13, 14, 14, 15])
    for nm in PRODS:
        for ck in ('OLD', 'NEW'):
            dg = DG[f'{nm}|{ck}']
            fill = STAR_FILL if ck == 'NEW' else None
            r = prow(ws, r, [nm, F_LAB[ck], dg['lots_risk_avg'], dg['lots_mgtot_avg'],
                             dg['lots_act_avg'], f"{dg['bind']}/{dg['n']}",
                             100 * dg['risk_use_pct'] / 3.0 / 100.0,
                             dg['mg_use_pct'] / 100.0, dg['mg_peak_pct'] / 100.0],
                     [None, None, '0.0', '0.0', '0.0', None, '0.0%', '0.0%', '0.0%'], fill=fill)
        r += 1
    r = note(ws, r, '被压制的笔数 = 实际手数 < 风险允许手数 的笔数（说明该笔没能按 3% 风险开足）。', 10)
    r = note(ws, r, '风险预算利用率 = 实际单笔风险 ÷ 3%；越接近 100% 说明资金用得越充分。', 10)

    # ==================== 每品种权益曲线
    idx = 3
    for nm in PRODS:
        ws = wb.create_sheet(f'{idx:02d}_权益_{nm}'); idx += 1
        r = 1
        r = title(ws, r, f'{nm}（{R["data"][nm]["code"]}）· 独立账户 30 万 · D 方案 3% · 60 分钟 ★优选', 6, size=14)
        r = note(ws, r, '「含浮亏」= 已实现权益 + 在持仓浮亏（浮亏按初始止损价截断）', 6)
        cs = [RS[nm]['OLD'], RS[nm]['NEW']]
        t0 = min(c['curve'][0][0] for c in cs if c['curve'])
        ts, cols = align([cs[0]['curve'], cs[0]['mtm'], cs[1]['curve'], cs[1]['mtm']], CAP0)
        r = head(ws, r, ['时间', '优化前·已实现权益', '优化前·含浮亏', '★推荐·已实现权益',
                         '★推荐·含浮亏'], [21, 18, 16, 18, 16])
        hdr = r - 1
        for i, t in enumerate(ts):
            r = prow(ws, r, [str(t)[:19]] + [cols[k][i] for k in range(4)],
                     [None, '#,##0', '#,##0', '#,##0', '#,##0'])
        last = r - 1
        ch = LineChart(); ch.title = f'{nm} 权益曲线（本金 30 万 · D 方案 3%）'
        ch.height = 11; ch.width = 25
        ch.y_axis.title = '权益（元）'; ch.x_axis.title = '时间'
        ch.add_data(Reference(ws, min_col=2, max_col=5, min_row=hdr, max_row=last),
                    titles_from_data=True)
        ch.set_categories(Reference(ws, min_col=1, min_row=hdr + 1, max_row=last))
        for sr in ch.series:
            sr.graphicalProperties.line.width = 20000
        ws.add_chart(ch, f'G{hdr}')
        r += 1
        r = title(ws, r, '关键指标', 6, size=12)
        r = head(ws, r, ['指标', '优化前', '★推荐'], [22, 18, 18])
        s0 = cs[0]['stat']; s1 = cs[1]['stat']; e1 = cs[1]['extra']
        for lab, k, f in [('成交笔数', 'n', '0'), ('胜率', 'win', '0.0%'),
                          ('盈亏比 PF', 'pf', '0.00'), ('终值(元)', 'eq_end', '#,##0'),
                          ('收益率', 'ret_pct', '+0.0%'), ('年化', 'ann_pct', '+0.0%'),
                          ('最大回撤%', 'mdd_pct', '0.00%'),
                          ('含浮亏回撤%', 'mdd_mtm_pct', '0.00%'),
                          ('Calmar', 'calmar', '0.00'), ('Sharpe', 'sharpe', '0.00'),
                          ('均手', 'avg_lots', '0.00'), ('保证金峰值%', 'mg_peak_pct', '0.0%'),
                          ('最长连亏笔数', 'max_loss_streak', '0')]:
            v0 = s0[k] / 100.0 if k in ('win', 'ret_pct', 'ann_pct', 'mdd_pct',
                                        'mdd_mtm_pct', 'mg_peak_pct') else s0[k]
            v1 = s1[k] / 100.0 if k in ('win', 'ret_pct', 'ann_pct', 'mdd_pct',
                                        'mdd_mtm_pct', 'mg_peak_pct') else s1[k]
            r = prow(ws, r, [lab, v0, v1], [None, f, f])
        r = prow(ws, r, ['出场：移动止盈%', e1['trl'] / 100.0, ''], [None, '0.0%', None])
        r = prow(ws, r, ['出场：初始止损%', e1['sl'] / 100.0, ''], [None, '0.0%', None])
        r = prow(ws, r, ['出场：到达目标%', e1['tp'] / 100.0, ''], [None, '0.0%', None])

    # ==================== 逐笔明细
    for nm in PRODS:
        ws = wb.create_sheet(f'{idx:02d}_逐笔_{nm}'); idx += 1
        r = 1
        r = title(ws, r, f'{nm} 逐笔明细（★推荐资金参数）· D 方案 3% · 60 分钟 ★优选', 20, size=14)
        r = note(ws, r, '手数 = 按当时权益的 3% 风险预算 ÷ 每手风险，并受保证金上限 80% 约束', 20)
        r = head(ws, r, ['#', '方向(开→平)', '开仓时间', '平仓时间', '持仓K线', '开仓价', '平仓价',
                         'WV(点)', '成本(点)', '净盈亏(点)', '净盈亏(R)', '手数',
                         '实际盈亏(元)', '保证金占用(元)', '单笔风险(元)', '风险%',
                         '平仓后权益', '出场原因', '最大浮亏(元)', '风险预算利用率'],
                 [5, 12, 18, 18, 8, 9, 9, 8, 9, 10, 10, 6, 12, 13, 12, 8, 13, 12, 13, 13])
        dstart = r
        for t in RS[nm]['NEW']['taken']:
            fill = OK_FILL if t['pnl'] > 0 else BAD_FILL
            r = prow(ws, r, [None, '开多→平多' if t['dir'] > 0 else '开空→平空',
                             str(t['et'])[:19], str(t['xt'])[:19], t['bars'], t['ep'], t['xp'],
                             t['wv'], t['cost'], t['net'], t['net_r'], t['lots'], t['pnl'],
                             t['mg_used'], t['risk_used'], t['risk_pct'] / 100.0,
                             t['eq_after'], t['reason'], t['mae_yuan'] * t['lots'],
                             min(t['risk_pct'] / 3.0, 1.0)],
                     [None, None, None, None, '0', None, None, '0.0', '0.00', '0.00',
                      '+0.000', '0', '#,##0', '#,##0', '#,##0', '0.00%', '#,##0', None,
                      '#,##0', '0.0%'], fill=fill)
        for i, row in enumerate(range(dstart, r), 1):
            ws.cell(row, 1, i).alignment = C

    # ==================== 月度收益
    ws = wb.create_sheet(f'{idx:02d}_月度收益'); idx += 1
    r = 1
    r = title(ws, r, '月度收益（★推荐资金参数）· 各自独立 30 万', 10, size=14)
    months = sorted(set(mm['month'] for nm in PRODS
                        for mm in RS[nm]['NEW']['monthly']))
    r = head(ws, r, ['月份'] + PRODS, [11] + [12] * 4)
    tab = {nm: {mm['month']: mm['ret_pct'] / 100.0 for mm in RS[nm]['NEW']['monthly']}
           for nm in PRODS}
    for mo in months:
        r = prow(ws, r, [mo] + [tab[nm].get(mo) for nm in PRODS],
                 [None] + ['+0.0%;-0.0%'] * 4)

    # ==================== 参数速查
    ws = wb.create_sheet(f'{idx:02d}_参数速查'); idx += 1
    r = 1
    r = title(ws, r, '参数速查（与指标文件赢益共振_v9.XTRD 一致）', 6, size=14)
    r = head(ws, r, ['参数', '值', '含义'], [16, 18, 62])
    for k, v, d in [
        ('KB', M['P0']['KB'], '低阈博反弹的阈值系数'),
        ('SW0', M['P0']['SW0'], '初始止损 = SW0 × ATR'),
        ('TGTW', M['P0']['TGTW'], '目标位 = TGTW × 初始风险'),
        ('DYNM', M['P0']['DYNM'], '动态止损开关（1=开）'),
        ('LSTP', M['P0']['LSTP'], '移动止盈的锁定系数'),
        ('GATEW', M['gatew'], '成本闸门（0 = 关闭，恒开闸）'),
        ('滑点', M['slip'], '出场滑点（跳）：开仓 0 / 止损与移动止盈 0.5 / 到达目标 0'),
        ('NMID', M['nmid'], '均线参照周期（60 分钟）'),
        ('NAV', M['nav'], '波动参照周期'),
        ('RISK', M['risk'], '单笔风险预算 = 当时权益 × 3%（D 方案）'),
        ('MGTOT', 0.80, '单笔保证金占用上限 = 权益 × 80%'),
        ('MAXLOT', 100, '单笔最大手数'),
        ('COMPOUND', 'True', '复利：风险预算按当时权益计算'),
    ]:
        r = prow(ws, r, [k, v, d], [None, None, None])

    # ==================== 数据区间
    ws = wb.create_sheet(f'{idx:02d}_数据区间'); idx += 1
    r = 1
    r = title(ws, r, '数据区间', 6, size=14)
    r = head(ws, r, ['品种', '主力合约', 'K线根数', '区间'], [9, 12, 12, 34])
    for nm in PRODS:
        d = R['data'][nm]
        r = prow(ws, r, [nm, d['code'], d['n'], d['rng']], [None, None, '#,##0', None])

    wb.save(OUT)
    print(f'已生成 {OUT}')
    print(f'工作表 {len(wb.sheetnames)} 张：', ', '.join(wb.sheetnames))


if __name__ == '__main__':
    main()
