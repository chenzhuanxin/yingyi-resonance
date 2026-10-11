# -*- coding: utf-8 -*-
"""patch_kb_restore.py —— 恢复高低阈：轨道宽度 KB 由 2.0 改回 2.5

用户决定「还是用原来的」，即回退到 KB=2.5（原始最优配置）：
    高阈 UPB = CEN + 2.5*WV   （触及挂空，博回调）
    低阈 DNB = CEN - 2.5*WV   （触及挂多，博反弹）

幂等 · 单遍 · 纯 CRLF · 自动备份。只改参数数值与一处注释，信号逻辑一字未动。
"""
import os, shutil

P = r'D:/360安全浏览器下载/赢益共振/赢益共振_v9.XTRD'
BAK = r'D:/360安全浏览器下载/赢益共振/赢益共振_v9_恢复KB2.5前备份.XTRD'

OLD = 'KB:=2.0;          //★★轨道宽度（倍波动）：低阈=CEN-KB*WV，高阈=CEN+KB*WV（已放开：2.5→2.0）'
NEW = 'KB:=2.5;          //★★轨道宽度（倍波动）：低阈=CEN-KB*WV，高阈=CEN+KB*WV'


def main():
    raw = open(P, 'rb').read()
    s = raw.decode('gbk')
    if 'KB:=2.5;' in s:
        print('已经是 KB=2.5，跳过'); return
    if 'KB:=2.0;' not in s:
        print('!! 未找到 KB:=2.0，请人工检查'); return
    if not os.path.exists(BAK):
        shutil.copy2(P, BAK); print('已备份 →', BAK)

    s2 = s.replace('\r\n', '\n')
    assert s2.count(OLD) == 1, f'匹配数异常：{s2.count(OLD)}'
    s2 = s2.replace(OLD, NEW, 1)
    out = s2.replace('\n', '\r\n')

    assert out.count('\n') == out.count('\r\n'), 'CRLF 校验失败'
    assert 'KB:=2.5;' in out and 'KB:=2.0;' not in out, '替换校验失败'
    assert out.count('//★★轨道宽度') == 1, '注释校验失败'

    open(P, 'wb').write(out.encode('gbk'))
    print('已修改 KB: 2.0 → 2.5（恢复原配置）')
    print('  行数', out.count('\r\n'), ' CRLF 正常', out.count('\n') == out.count('\r\n'))


if __name__ == '__main__':
    main()
