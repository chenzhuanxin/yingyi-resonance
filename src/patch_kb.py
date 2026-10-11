# -*- coding: utf-8 -*-
"""patch_kb_v9.py —— 放开高低阈：轨道宽度 KB 由 2.5 改为 2.0

高低阈定义（不变）：
    高阈 UPB = CEN + KB*WV   （触及挂空，博回调）
    低阈 DNB = CEN - KB*WV   （触及挂多，博反弹）
本次只把 KB 由 2.5 收窄到 2.0 —— 阈值更贴近均线中枢，触及更容易、入场机会更多。

幂等 · 单遍 · 纯 CRLF · 自动备份。只改参数数值与一处注释，信号逻辑一字未动。
"""
import os, shutil

P = r'D:/360安全浏览器下载/赢益共振/赢益共振_v9.XTRD'
BAK = r'D:/360安全浏览器下载/赢益共振/赢益共振_v9_放开高低阈前备份.XTRD'

OLD = 'KB:=2.5;          //★★轨道宽度（倍波动）：低阈=CEN-KB*WV，高阈=CEN+KB*WV'
NEW = 'KB:=2.0;          //★★轨道宽度（倍波动）：低阈=CEN-KB*WV，高阈=CEN+KB*WV（已放开：2.5→2.0）'


def main():
    raw = open(P, 'rb').read()
    s = raw.decode('gbk')
    if 'KB:=2.0;' in s:
        print('已打过补丁（KB=2.0），跳过'); return
    if 'KB:=2.5;' not in s:
        print('!! 未找到 KB:=2.5，请人工检查'); return
    if not os.path.exists(BAK):
        shutil.copy2(P, BAK); print('已备份 →', BAK)

    # CRLF 归一化后再替换，最后还原
    s2 = s.replace('\r\n', '\n')
    assert s2.count(OLD) == 1, f'匹配数异常：{s2.count(OLD)}'
    s2 = s2.replace(OLD, NEW, 1)
    out = s2.replace('\n', '\r\n')

    # 校验
    assert out.count('\n') == out.count('\r\n'), 'CRLF 校验失败'
    assert 'KB:=2.0;' in out and 'KB:=2.5;' not in out, '替换校验失败'
    assert out.count('//★★轨道宽度') == 1, '注释校验失败'

    open(P, 'wb').write(out.encode('gbk'))
    print('已修改 KB: 2.5 → 2.0')
    print('  行数', out.count('\r\n'), ' CRLF 正常', out.count('\n') == out.count('\r\n'))


if __name__ == '__main__':
    main()
