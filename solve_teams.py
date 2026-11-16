# -*- coding: utf-8 -*-
"""
货币战争·入画奇航 —— 指定角色 × 恰好 k 个羁绊的最少上场人数配队

可配置
------
* `--require "角色A,角色B"`：必须上场的角色（默认 花火,刻律德菈,那刻夏）
* `--emblem "角色=羁绊"`：给某角色加转职羁绊（默认 那刻夏=梦境交织），可重复
* `--config cfg.json`：整体覆盖规则
* 默认内置：少女乐队仅恰好 1/4 人激活；千星商会 1 人不生效（≥2 人）；
  独立羁绊（双龙吟等）不计入激活数

用法
----
    python solve_teams.py 其他数据.json
    python solve_teams.py 数据.json --max-k 14 --no-next
    python solve_teams.py 数据.json --require "花火,翡翠" --emblem "翡翠=梦境交织"
"""
import json
import sys
import time
import csv

import cwmodel


def arrange(m, team):
    """队伍内：必带角色置顶，其余按费用升序（同费按名字）。"""
    rest = sorted(team, key=lambda n: (m.cost[n], n))
    return list(m.required) + rest


def team_key(m, team):
    costs = sorted((m.cost[n] for n in list(m.required) + list(team)), reverse=True)
    return (costs, sorted(list(m.required) + list(team)))


def main():
    argv = sys.argv[1:]
    path, max_k, out = None, 14, 'answer'
    strict_pos, with_next = False, True
    cfg_path, require, emblems = None, None, []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == '--max-k':
            max_k = int(argv[i + 1]); i += 2
        elif a == '--out':
            out = argv[i + 1]; i += 2
        elif a == '--strict-pos':
            strict_pos = True; i += 1
        elif a == '--no-next':
            with_next = False; i += 1
        elif a == '--config':
            cfg_path = argv[i + 1]; i += 2
        elif a == '--require':
            require = argv[i + 1]; i += 2
        elif a == '--emblem':
            emblems.append(argv[i + 1]); i += 2
        else:
            path = a; i += 1
    cfg = cwmodel.load_config(cfg_path)
    cwmodel.apply_overrides(cfg, require, emblems)
    data = cwmodel.load_data(path)          # 没给数据文件 → 用内置数据
    m = cwmodel.Model(data, cfg)
    t0 = time.time()

    print('数据: %s' % (path or '内置（data_v47.py，v4.7）'))
    print('必带角色: %s；转职: %s' % ('、'.join(m.required),
                                ', '.join('%s→%s' % (k, '+'.join(v)) for k, v in m.emblems.items()) or '无'))
    print('计入羁绊 %d 个；特殊规则: %s' % (len(m.counted),
                                      ', '.join('%s=%s' % (k, v) for k, v in m.rules.items()) or '无'))
    print('基础羁绊 %d 个: %s' % (m.base_k, '、'.join(m.active_of(m.base))))
    print()

    fcsv = open(out + '.csv', 'w', encoding='utf-8-sig', newline='')
    writer = csv.writer(fcsv)
    writer.writerow(['激活羁绊数', '类别', '上场人数',
                     '队伍成员（必带角色置顶，其余按费用升序）', '已激活羁绊（计入的）', '站位'])

    def pos_ok(team):
        return (not strict_pos) or m.pos_ok(list(m.required) + list(team))

    def emit(k, tag, size, teams):
        teams.sort(key=lambda t: team_key(m, t))
        for team in teams:
            full = arrange(m, team)
            writer.writerow([k, tag, size, '、'.join(full),
                             '、'.join(m.active_of(m.counts(team))),
                             '、'.join(cwmodel.POS_CN.get(m.units[n]['pos'], m.units[n]['pos'])
                                       for n in full)])

    result = {}
    for k in range(m.base_k, max_k + 1):
        size = len(m.required)
        teams, cnt = [], 0
        while size <= len(m.units):
            en = cwmodel.ExactEnumerator(m, k, size)
            teams = [t for t in en.run() if pos_ok(t)]
            cnt = len(teams)
            if cnt:
                break
            size += 1
        if not cnt:
            print('k=%2d  无解' % k)
            continue
        emit(k, '最优', size, teams)
        print('k=%2d  最优 %2d 人 %6d 队   (%.1fs)' % (k, size, cnt, time.time() - t0))
        sys.stdout.flush()
        entry = {'size': size, 'count': cnt, 'teams': teams[:] if cnt <= 3000 else teams[:300]}
        if with_next:
            en = cwmodel.ExactEnumerator(m, k, size + 1)
            teams2 = [t for t in en.run() if pos_ok(t)]
            emit(k, '次优', size + 1, teams2)
            entry['next_size'] = size + 1
            entry['next_count'] = len(teams2)
            entry['next_teams'] = teams2[:] if len(teams2) <= 3000 else teams2[:300]
            print('     次优 %2d 人 %6d 队   (%.1fs)' % (size + 1, len(teams2), time.time() - t0))
            sys.stdout.flush()
        result[k] = entry
    fcsv.close()

    # ---------- Markdown ----------
    md = ['# 货币战争·入画奇航 —— 指定角色 × 羁绊数 的配队', '',
          '- 必带角色：%s' % '、'.join(m.required),
          '- 转职：%s' % (', '.join('%s→%s' % (k, '+'.join(v)) for k, v in m.emblems.items()) or '无'),
          '- 特殊规则：%s' % (', '.join('%s=%s' % (k, v) for k, v in m.rules.items()) or '无'),
          '- 基础羁绊：%s（k = %d）' % ('、'.join(m.active_of(m.base)), m.base_k),
          '- 排序：必带角色置顶，其余按费用升序；队伍之间按最高费用升序（同高再比次高）', '',
          '## 总览', '', '| k | 最优人数 | 最优队数 | 次优人数 | 次优队数 |', '|---|---|---|---|---|']
    for k in range(3, max_k + 1):
        if k in result:
            r = result[k]
            md.append('| %d | %d | %d | %s | %s |' % (k, r['size'], r['count'],
                                                      r.get('next_size', '-'), r.get('next_count', '-')))
    md.append('')
    for k in sorted(result):
        r = result[k]
        md.append('## k = %d：最优 %d 人（%d 队）' % (k, r['size'], r['count']))
        md.append('')
        if r['count'] <= 3000:
            for t in r['teams']:
                md.append('- ' + '、'.join(arrange(m, t)))
        else:
            md.append('共 %d 队，完整列表见 `%s.csv`；以下为前 %d 队示例：' % (r['count'], out, len(r['teams'])))
            md.append('')
            for t in r['teams']:
                md.append('- ' + '、'.join(arrange(m, t)))
        md.append('')
        if r.get('next_count'):
            md.append('### k = %d：次优 %d 人（%d 队）' % (k, r['next_size'], r['next_count']))
            md.append('')
            if r['next_count'] <= 3000:
                for t in r['next_teams']:
                    md.append('- ' + '、'.join(arrange(m, t)))
            else:
                md.append('共 %d 队，完整列表见 `%s.csv`；以下为前 %d 队示例：'
                          % (r['next_count'], out, len(r['next_teams'])))
                md.append('')
                for t in r['next_teams']:
                    md.append('- ' + '、'.join(arrange(m, t)))
            md.append('')
    with open(out + '.md', 'w', encoding='utf-8') as f:
        f.write('\n'.join(md))

    with open(out + '_summary.json', 'w', encoding='utf-8') as f:
        json.dump({str(k): {'size': v['size'], 'count': v['count'],
                            'next_size': v.get('next_size'), 'next_count': v.get('next_count')}
                   for k, v in result.items()}, f, ensure_ascii=False, indent=1)
    print('\n总耗时 %.1fs，已写出 %s.csv / %s.md / %s_summary.json' % (time.time() - t0, out, out, out))


if __name__ == '__main__':
    main()
