# -*- coding: utf-8 -*-
"""
货币战争·入画奇航 —— 人口过渡链（同核心、零换人）

思路
----
队伍随人口逐级扩编，每一级完整包含上一级（7→8 重合 7 人、8→9 重合 8 人……），
角色重合数达到理论上限，中途不用卖人。费用按常规节奏卡上限（7 人口 ≤3 费、
8 人口 ≤4 费、9 人口及以上 ≤5 费）。在满足条件的链里按「各级羁绊数之和」排序，
同样总分再比较高层羁绊数。

可配置
------
* `--require "角色A,角色B"`：必须上场的角色（默认 花火,刻律德菈,那刻夏）
* `--emblem "角色=羁绊"`：给某角色加转职羁绊（默认 那刻夏=梦境交织），可重复
* `--config cfg.json`：整体覆盖规则，例如
    {"required": ["花火"], "trait_rules": {"千星商会": {"min": 2}}}
* 默认已内置两条特殊规则：少女乐队仅恰好 1/4 人激活；千星商会 1 人不生效（≥2 才算）。

用法
----
    python transition_teams.py 其他数据.json
    python transition_teams.py 数据.json --to 10 --top 5
    python transition_teams.py 数据.json --require "花火,翡翠" --emblem "翡翠=梦境交织"
"""
import json
import sys
import time

import cwmodel


def best_chain(m, top_team, lo):
    """从 top_team 逐级减人，返回 (k 序列, [(人口, k, 队伍), ...]) 最优的一条。"""
    n = len(top_team) + len(m.required)
    counts = m.counts(top_team)
    best = {'profile': None, 'path': None}

    def rec(team, c, level, path):
        if level == lo:
            prof = tuple(x[1] for x in path)
            if best['profile'] is None or (sum(prof), prof) > (sum(best['profile']), best['profile']):
                best['profile'] = prof
                best['path'] = list(path)
            return
        for u in [x for x in team if x not in m.required]:
            nt = tuple(x for x in team if x != u)
            if any(m.cost[x] > m.caps.get(level - 1, 5) for x in list(m.required) + list(nt)):
                continue
            nc = m.sub(c, u)
            rec(nt, nc, level - 1, path + [(level - 1, m.k_of(nc), nt)])

    rec(top_team, counts, n, [(n, m.k_of(counts), top_team)])
    return best['profile'], best['path']


def fmt(m, team):
    return '、'.join('%s(%d费)' % (n, m.cost[n]) for n in list(m.required) + list(team))


def main():
    argv = sys.argv[1:]
    path, top, out, to, lo, cfg_path = None, 3, 'transition', 11, 7, None
    require, emblems, five = None, [], False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == '--top':
            top = int(argv[i + 1]); i += 2
        elif a == '--out':
            out = argv[i + 1]; i += 2
        elif a == '--to':
            to = int(argv[i + 1]); i += 2
        elif a == '--from':
            lo = int(argv[i + 1]); i += 2
        elif a == '--config':
            cfg_path = argv[i + 1]; i += 2
        elif a == '--require':
            require = argv[i + 1]; i += 2
        elif a == '--emblem':
            emblems.append(argv[i + 1]); i += 2
        elif a == '--five':
            five = True; i += 1
        else:
            path = a; i += 1
    cfg = cwmodel.load_config(cfg_path)
    cwmodel.apply_overrides(cfg, require, emblems)
    data = cwmodel.load_data(path)          # 没给数据文件 → 用内置数据
    m = cwmodel.Model(data, cfg)

    print('数据: %s' % (path or '内置（data_v47.py，v4.7）'))
    print('必带角色: %s；转职: %s' % ('、'.join(m.required),
                                ', '.join('%s→%s' % (k, '+'.join(v)) for k, v in m.emblems.items()) or '无'))
    print('计入羁绊 %d 个；特殊规则: %s' % (len(m.counted),
                                      ', '.join('%s=%s' % (k, v) for k, v in m.rules.items()) or '无'))
    print('费用上限: %s；每级只加人不换人' % ', '.join('%s人口≤%d费' % (k, v) for k, v in sorted(m.caps.items())))
    print('基础羁绊 %d 个: %s' % (m.base_k, '、'.join(m.active_of(m.base))))
    print()

    md = ['# 人口过渡链（同核心、零换人）', '',
          '- 必带角色：%s' % '、'.join(m.required),
          '- 转职：%s' % (', '.join('%s→%s' % (k, '+'.join(v)) for k, v in m.emblems.items()) or '无'),
          '- 费用上限：%s' % ', '.join('%s 人口 ≤%d 费' % (k, v) for k, v in sorted(m.caps.items())),
          '']

    for end in range(max(9, lo + 1), to + 1):
        t0 = time.time()
        # 先从“不设 k 下限”地找该人口的最高羁绊数：用 min-k 枚举逐步试探
        teams = []
        for kmin in range(18, 5, -1):
            teams = cwmodel.MinKEnumerator(m, end, kmin, m.caps.get(end, 5)).run()
            if teams:
                break
        if not teams:
            print('人口 %d：无可行队伍' % end)
            continue
        kmax = max(m.k(t) for t in teams)
        tops = [t for t in teams if m.k(t) == kmax
                and all(m.cost[n] <= m.caps.get(end, 5) for n in list(m.required) + list(t))]
        if five:
            tops = [t for t in tops if any(m.cost[n] == 5 for n in t)]
        print('人口 %d：≤%d 费候选 %d 队，最高 %d 羁绊（%d 队）  %.1fs'
              % (end, m.caps.get(end, 5), len(teams), kmax, len(tops), time.time() - t0))
        sys.stdout.flush()

        chains = []
        for t in tops:
            prof, p = best_chain(m, t, lo)
            if prof:
                chains.append((sum(prof), prof, p))
        chains.sort(key=lambda x: (x[0], x[1]), reverse=True)

        title = '最强 %d → %d 人口过渡链' % (lo, end)
        if five:
            title += '（终端含 5 费）'
        print('\n' + '=' * 64)
        print(title)
        print('=' * 64)
        md += ['## ' + title, '']
        seen, shown = set(), 0
        for total, prof, p in chains:
            key = p[0][2]
            if key in seen:
                continue
            seen.add(key)
            shown += 1
            asc = list(reversed(p))
            kk = [x[1] for x in asc]
            print('\n路线 %d ｜ 羁绊数 %s（合计 %d）' % (shown, ' → '.join(map(str, kk)), sum(kk)))
            md.append('### 路线 %d ｜ 羁绊数 %s' % (shown, ' → '.join(map(str, kk))))
            for idx, (pop, k, team) in enumerate(asc):
                if idx == 0:
                    print(' %2d 人口（%d 羁绊）：%s' % (pop, k, fmt(m, team)))
                    md.append('- %d 人口（%d 羁绊）：%s' % (pop, k, fmt(m, team)))
                else:
                    prev = asc[idx - 1][2]
                    added = [x for x in team if x not in prev]
                    print(' %2d 人口（%d 羁绊）：+%s ｜ %s'
                          % (pop, k, '、'.join(added), m.cost_profile(team)))
                    md.append('- %d 人口（%d 羁绊）：+%s ｜ %s'
                              % (pop, k, '、'.join(added), m.cost_profile(team)))
            final = p[0][2]
            print('   最终羁绊：%s' % '、'.join(m.active_of(m.counts(final))))
            md.append('- 最终羁绊：%s' % '、'.join(m.active_of(m.counts(final))))
            md.append('')
            if shown >= top:
                break
        print()

    with open(out + '.md', 'w', encoding='utf-8') as f:
        f.write('\n'.join(md))
    print('已写出 %s.md' % out)


if __name__ == '__main__':
    main()
