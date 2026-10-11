# -*- coding: utf-8 -*-
"""mainspec.py —— 主力合约测试专用：合约规格 / 手续费 / 保证金

★ 数据源已更新（2026-10-11）★

主源 = 用户 GitHub 仓库 chenzhuanxin/eastmoney-futures-margin
       文件：index.html 内嵌 DATA（fetch @2026-10-11 20:46，官网更新 @10-11 19:54）
       表：①「期货手续费」②「保证金比例」③「品种及交易规则」④「单手保证金」
       —— 本文件 ref/efm/DATA.json 即该内嵌 DATA 的解析结果
交叉校验源 = chenzhuanxin/futures-sim-trading-terminal / 品种参数.json（@2026-10-05）

口径说明（来自仓库原文）：
  · 保证金 = 东方财富期货「公司保证金比例」（高于交易所最低标准）
  · 手续费 = 东方财富期货「公司手续费标准」，模式「按手收取」(元/手) 或「按成交额」(比例)
  · 手续费折算：官网标准 ≈ 交易所标准的 3 倍（郑商所官网：红枣3元/手、花生2元/手、
    纯碱成交额万分之一、烧碱成交额万分之一；东方财富：9元/手、6元/手、万分之3、万分之3）
  · 申报费（梯度申报费）：郑商所对本四品种均实施，但仅在"单日信息量 > 4000 笔"时触发，
    本策略日均报单 ≤ 2 笔 → 申报费 = 0，可忽略（见 REPORT 说明）
  · 平今加收：本四品种「平今/日内加收」列为空 → 无加收

成本换算为「价格点数」(便于引擎统一处理)：
    按成交额：手续费(元) = 价格 × 合约乘数 × 费率  →  点数 = 价格 × 费率
    按手数  ：手续费(元) = 固定元/手             →  点数 = 元/手 ÷ 合约乘数

手续费折扣 FEE_DISCOUNT（1.0 = 官网「公司标准」）：
    0.333 ≈ 交易所标准（可谈）；1.0 = 东方财富官网公示标准；>1 = 更保守的压力测试
"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
REF_EFM = os.path.join(HERE, 'ref', 'efm', 'DATA.json')       # 主源
REF_SIM = os.path.join(HERE, 'ref', '品种参数_新.json')        # 交叉校验源

PROD = ['SA', 'CJ', 'PK', 'SH']
MAIN = {'SA': 'SA2701', 'CJ': 'CJ2701', 'PK': 'PK2611', 'SH': 'SH2611'}
TF = {'15分钟': ('_15.csv', 60, 14), '60分钟': ('_60.csv', 40, 14), '日线': ('_D.csv', 20, 14)}

# 手续费折扣（全局可调）：1.0 = 官网公司标准
FEE_DISCOUNT = 1.0


# ------------------------------------------------------------------ 文本解析
def _parse_fee(text):
    """'万分之3（按成交额）' / '9元/手' / '万分之1.5，平今仓万分之3（按成交额）'
    → (mode, value, extra_flag)   mode ∈ {'rate','lot'}；value: rate=万分比小数, lot=元/手
    extra_flag: '平今加收' / '日内加收' / ''"""
    t = str(text).strip()
    extra = ''
    if '平今' in t and ('加收' in t or '平今仓' in t or '平今' in t.split('，')[0] is False):
        pass
    # 平今/日内加收标记
    if re.search(r'平今(仓)?(交易)?(手续费)?(成交金额|万分|元)', t):
        extra = '平今加收'
    if '日内' in t:
        extra = (extra + '、日内加收').strip('、') if extra else '日内加收'

    head = re.split(r'[，,]', t)[0]        # 只取第一条（开仓/平昨标准）
    m = re.search(r'万分之([0-9.]+)', head)
    if m:
        return 'rate', float(m.group(1)) / 10000.0, extra
    m = re.search(r'([0-9.]+)\s*元\s*/\s*手', head)
    if m:
        return 'lot', float(m.group(1)), extra
    raise ValueError(f'无法解析手续费文本: {text!r}')


def _parse_pct(text):
    m = re.search(r'([0-9.]+)\s*%', str(text))
    return float(m.group(1)) / 100.0 if m else None


def _parse_unit(text):
    """'20吨/手' → 20"""
    m = re.search(r'([0-9.]+)\s*\S*?/\s*手', str(text))
    return float(m.group(1)) if m else None


def _parse_tick(text):
    """'1元/吨' → 1.0"""
    m = re.search(r'([0-9.]+)\s*元', str(text))
    return float(m.group(1)) if m else None


# ------------------------------------------------------------------ 从主源构造 SPEC
def _build():
    d = json.load(open(REF_EFM, encoding='utf-8'))
    fee = {}
    for r in d['feeFutures']['rows']:
        code = str(r[2]).strip().upper()
        if code:
            fee[code] = dict(text=r[3], mode_col=r[4], extra=r[5])
    margin, mainc = {}, {}
    for r in d['ratio']['rows']:
        code = str(r[2]).strip().upper()
        margin[code] = dict(margin=_parse_pct(r[5]), main=str(r[3]).strip(),
                            limit=_parse_pct(r[4]), adj=r[6])
    rules = {}
    for r in d['rules']['rows']:
        m = re.search(r'([A-Za-z_]+)\s*$', str(r[1]).strip())
        if m:
            rules[m.group(1).upper()] = dict(tick=_parse_tick(r[2]), unit=_parse_unit(r[6]))
    lot = {}
    for r in d['margin']['rows']:
        m = re.match(r'^([A-Za-z]+)', str(r[1]).strip())
        if m:
            lot[m.group(1).upper()] = dict(yuan=float(r[2]), rate=float(r[3]))

    spec = {}
    for p in PROD:
        mode, val, extra = _parse_fee(fee[p]['text'])
        u = rules.get(p, {})
        spec[p] = dict(
            name={'SA': '纯碱', 'CJ': '红枣', 'PK': '花生', 'SH': '烧碱'}[p],
            exch='郑商所',
            mult=int(u.get('unit') or {'SA': 20, 'CJ': 5, 'PK': 5, 'SH': 30}[p]),
            tick=float(u.get('tick') or {'SA': 1, 'CJ': 5, 'PK': 2, 'SH': 1}[p]),
            margin=margin[p]['margin'],
            limit=margin[p]['limit'],
            main_contract=margin[p]['main'],
            margin_adj=margin[p]['adj'],
            fee_mode=mode, fee_open=val, fee_close=val, fee_today=val,
            fee_text=fee[p]['text'], fee_extra=extra,
            margin_yuan_repo=lot.get(p, {}).get('yuan'),
            margin_rate_repo=lot.get(p, {}).get('rate'),
        )
    return spec, d


SPEC, DATA = _build()
NAME = {k: v['name'] for k, v in SPEC.items()}

META = dict(
    src='chenzhuanxin/eastmoney-futures-margin · index.html 内嵌 DATA',
    fetch=DATA.get('fetchTime'), update=DATA.get('updateTime'),
)


# ------------------------------------------------------------------ 成本
def fee_points(prod, price, discount=None):
    """单边手续费（价格点数）。discount 默认用全局 FEE_DISCOUNT"""
    s = SPEC[prod]
    k = FEE_DISCOUNT if discount is None else discount
    if s['fee_mode'] == 'rate':
        return price * s['fee_open'] * k
    return s['fee_open'] * k / s['mult']


def roundtrip_cost(prod, ep, xp, slip_ticks=1.0, discount=None):
    """一次往返总成本（价格点数）= 开仓费 + 平仓费 + 双边滑点"""
    s = SPEC[prod]
    fee = fee_points(prod, ep, discount) + fee_points(prod, xp, discount)
    slip = 2.0 * slip_ticks * s['tick']
    return fee + slip, fee, slip


def margin_yuan(prod, price, discount=None):
    """一手保证金（元）"""
    return price * SPEC[prod]['mult'] * SPEC[prod]['margin']


def set_discount(x):
    global FEE_DISCOUNT
    FEE_DISCOUNT = float(x)
    return FEE_DISCOUNT


# ------------------------------------------------------------------ 交叉校验
def verify_against_repo():
    """SPEC 与新快照主源、旧 sim-terminal 源逐字段比对，返回差异列表"""
    diff = []
    # ① 与主源派生字段自检
    for p in PROD:
        s = SPEC[p]
        r = s['margin_yuan_repo']
        if r:
            # 用仓库「单手保证金」表的价格反推校验保证金率
            implied = None
        if s['margin_rate_repo'] is not None and abs(s['margin_rate_repo'] - s['margin']) > 1e-9:
            diff.append(f'{p} 保证金率 两表不一致: 比例表{s["margin"]} vs 单手表{s["margin_rate_repo"]}')
        if str(s['main_contract']).lstrip('0') and MAIN[p][2:]:
            if not MAIN[p].endswith(str(s['main_contract'])):
                diff.append(f'{p} 主力合约不一致: 代码={MAIN[p]} vs 快照={s["main_contract"]}')
    # ② 与 sim-terminal 交叉校验
    if os.path.exists(REF_SIM):
        o = json.load(open(REF_SIM, encoding='utf-8'))['品种']
        for p in PROD:
            s = SPEC[p]; a = o[p]
            if abs(a['合约乘数'] - s['mult']):
                diff.append(f'{p} 乘数 两源不一致: {a["合约乘数"]} vs {s["mult"]}')
            if abs(a['最小变动价位'] - s['tick']):
                diff.append(f'{p} 最小变动 两源不一致: {a["最小变动价位"]} vs {s["tick"]}')
            m2 = a['手续费']
            md = 'rate' if m2['模式'] == '按成交额' else 'lot'
            if md != s['fee_mode'] or abs(m2['开仓'] - s['fee_open']) > 1e-12:
                diff.append(f'{p} 手续费 两源不一致: {m2} vs {s["fee_mode"]}/{s["fee_open"]}')
            if abs(a['保证金率'] - s['margin']) > 1e-9:
                diff.append(f'{p} 保证金率 两源不一致(已知): sim-terminal {a["保证金率"]} '
                            f'vs 新快照 {s["margin"]}')
    return diff


if __name__ == '__main__':
    print('=' * 120)
    print('数据源：', META['src'])
    print('抓取时间：', META['fetch'], ' 官网更新：', META['update'])
    print('=' * 120)
    print('=== 交叉校验（两源差异）===')
    df = verify_against_repo()
    print('无差异' if not df else '\n'.join('  ! ' + x for x in df))
    print()
    print(f'{"品种":5s}{"主力":9s}{"乘数":>5s}{"最小变动":>9s}{"保证金率":>9s}{"手续费原文":>22s}'
          f'{"模式":>9s}{"开仓费":>12s}{"单手保证金(仓库)":>16s}')
    for p in PROD:
        s = SPEC[p]
        mode = '按成交额' if s['fee_mode'] == 'rate' else '按手数'
        of = f"{s['fee_open']*10000:.2f}‱" if s['fee_mode'] == 'rate' else f"{s['fee_open']:.1f}元/手"
        print(f'{NAME[p]:5s}{MAIN[p]:9s}{s["mult"]:>5d}{s["tick"]:>9.1f}{s["margin"]*100:>8.0f}%'
              f'{s["fee_text"]:>22s}{mode:>9s}{of:>12s}{(s["margin_yuan_repo"] or 0):>16.1f}')
    print()
    print('=== 一次往返成本（价格点数 / 元）@ 2026-10-11 主力收盘价 ===')
    px = {'SA': 1001.0, 'CJ': 6855.0, 'PK': 7830.0, 'SH': 1810.0}
    for p in PROD:
        for dk in (1/3, 1.0):
            c, f, sl = roundtrip_cost(p, px[p], px[p], 1.0, discount=dk)
            tag = '交易所标准(×1/3)' if dk < 1 else '公司标准(官网)'
            print(f'  {NAME[p]} [{tag:14s}] 滑点1跳: 合计 {c:7.3f} 点 = {c*SPEC[p]["mult"]:7.2f} 元 '
                  f'(手续费 {f:.3f} 点 / 滑点 {sl:.3f} 点)')
