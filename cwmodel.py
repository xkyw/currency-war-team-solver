# -*- coding: utf-8 -*-
"""
货币战争·入画奇航 —— 共用的数据模型与可配置规则

配置项（JSON，可用 --config 传入，也可用命令行覆盖）
--------------------------------------------------
{
  "required": ["花火", "刻律德菈", "那刻夏"],       # 必须上场的角色
  "emblems":  {"那刻夏": ["梦境交织"]},              # 转职星徽：角色 -> 额外羁绊
  "independent": ["双龙吟", ...],                    # 独立羁绊：不计入“激活羁绊数”
  "trait_rules": {                                   # 特殊激活规则
      "少女乐队": {"exact": [1, 4]},                 # 恰好 1 或 4 人
      "千星商会": {"min": 2}                         # 1 人不生效，至少 2 人
  },
  "cost_caps": {"7": 3, "8": 4, "9": 5, "10": 5, "11": 5}
}
"""
import json

from data_v47 import VERSION, builtin_data

DEFAULT_CONFIG = {
    "required": ["花火", "刻律德菈", "那刻夏"],
    "emblems": {"那刻夏": ["梦境交织"]},
    "independent": ["双龙吟", "盗火行者", "巡海游侠", "黑市主理人", "机心巧匠", "幻乐之主"],
    "trait_rules": {
        "少女乐队": {"exact": [1, 4]},
        "千星商会": {"min": 2},
    },
    "cost_caps": {"7": 3, "8": 4, "9": 5, "10": 5, "11": 5, "12": 5, "13": 5},
}

POS_CN = {'front': '前', 'back': '后', 'flex': '灵活'}


def _clean(s):
    """名字里的 •（U+2022）在 GBK 控制台无法显示，统一成 ·（U+00B7）。

    涉及 6 个角色：丹恒•饮月、丹恒•腾荒、千冶•刃、姬子•启行、砂金•戏浪、知更鸟•晴歌。
    --require / --emblem 里用 • 或 · 都可以，内部会归一化成 ·。
    """
    return s.replace('\u2022', '\u00b7') if isinstance(s, str) else s


def load_data(path=None):
    """给路径就读 JSON（可换赛季数据），不给就用内置的硬编码数据。"""
    if path:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
    else:
        data = builtin_data()
    for t in data['traits']:
        t['name'] = _clean(t['name'])
    for u in data['units']:
        u['name'] = _clean(u['name'])
        u['traits'] = [_clean(x) for x in u['traits']]
    return data


def load_config(path=None):
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if path:
        with open(path, encoding='utf-8') as f:
            user = json.load(f)
        for k, v in user.items():
            if k == 'trait_rules':
                cfg['trait_rules'].update(v)
            elif k == 'cost_caps':
                cfg['cost_caps'].update(v)
            else:
                cfg[k] = v
    return cfg


def apply_overrides(cfg, require=None, emblem=None):
    """命令行覆盖：--require "花火,刻律德菈"；--emblem "那刻夏=梦境交织"。"""
    if require:
        cfg['required'] = [x.strip() for x in require.split(',') if x.strip()]
    if emblem:
        for item in emblem:
            name, traits = item.split('=', 1)
            cfg.setdefault('emblems', {})[name.strip()] = [t.strip() for t in traits.split('+') if t.strip()]
    return cfg


class Model:
    def __init__(self, data=None, cfg=None):
        self.cfg = cfg or load_config()
        if data is None:
            data = builtin_data()
        self.traits = [t['name'] for t in data['traits']]
        self.tidx = {n: i for i, n in enumerate(self.traits)}
        self.th = [t['thresholds'][0] for t in data['traits']]
        self.tiers = {t['name']: t['thresholds'] for t in data['traits']}
        self.double = {t['name']: t['doubleCount'] for t in data['traits']}
        self.units = {u['name']: u for u in data['units']}
        self.nT = len(self.traits)
        self.cfg['required'] = [_clean(n) for n in self.cfg['required']]
        self.required = list(self.cfg['required'])
        for n in self.required:
            if n not in self.units:
                raise KeyError('未知角色: %s' % n)
        self.emblems = {_clean(k): [_clean(t) for t in v]
                        for k, v in self.cfg.get('emblems', {}).items()}
        self.independent = set(self.cfg.get('independent', []))
        self.counted = [t for t in self.traits if t not in self.independent]
        self.cset = set(self.counted)
        self.rules = self.cfg.get('trait_rules', {})
        self.caps = {int(k): v for k, v in self.cfg.get('cost_caps', {}).items()}
        self.cost = {n: u['cost'] for n, u in self.units.items()}

        self.contrib = {}
        for n, u in self.units.items():
            c = {}
            for tr in list(u['traits']) + list(self.emblems.get(n, [])):
                c[tr] = c.get(tr, 0) + (2 if self.double[tr] else 1)
            self.contrib[n] = c

        self.base = [0] * self.nT
        for n in self.required:
            for tr, v in self.contrib[n].items():
                self.base[self.tidx[tr]] += v
        self.base_k = self.k_of(self.base)

    # ---------- 激活判定 ----------
    def is_active(self, trait, count):
        rule = self.rules.get(trait)
        if rule:
            if 'exact' in rule:
                return count in rule['exact']
            if 'min' in rule:
                return count >= rule['min']
        return count >= self.th[self.tidx[trait]]

    def k_of(self, counts):
        return sum(1 for t in self.counted if self.is_active(t, counts[self.tidx[t]]))

    def active_of(self, counts):
        return [t for t in self.counted if self.is_active(t, counts[self.tidx[t]])]

    def counts(self, team):
        c = list(self.base)
        for n in team:
            for tr, v in self.contrib[n].items():
                c[self.tidx[tr]] += v
        return c

    def sub(self, counts, unit):
        c = list(counts)
        for tr, v in self.contrib[unit].items():
            c[self.tidx[tr]] -= v
        return c

    def k(self, team):
        return self.k_of(self.counts(team))

    def cost_profile(self, team, with_required=True):
        cnt = {}
        names = (list(self.required) if with_required else []) + list(team)
        for n in names:
            cnt[self.cost[n]] = cnt.get(self.cost[n], 0) + 1
        return ' '.join('%d费×%d' % (c, cnt[c]) for c in sorted(cnt))

    def pos_ok(self, members):
        front = sum(1 for n in members if self.units[n]['pos'] == 'front')
        back = sum(1 for n in members if self.units[n]['pos'] == 'back')
        fs = self.cfg.get('front_slots', 4)
        bs = self.cfg.get('back_slots', 9)
        return front <= fs and back <= bs


class ExactEnumerator:
    """枚举上场人数 size、恰好 target 个计入羁绊的全部队伍（不含固定成员）。"""

    def __init__(self, model, target, size):
        self.m = model
        self.target = target
        self.r = size - len(model.required)
        names = [n for n in model.units if n not in model.required]
        names.sort(key=lambda n: (-sum(1 for t in model.contrib[n] if t in model.cset),
                                  model.cost[n], n))
        self.names = names
        self.c = [[(model.tidx[t], v) for t, v in model.contrib[n].items() if t in model.cset]
                  for n in names]
        self.suffix = [0] * (len(names) + 1)
        for i in range(len(names) - 1, -1, -1):
            mask = self.suffix[i + 1]
            for j, _ in self.c[i]:
                mask |= 1 << j
            self.suffix[i] = mask
        self.prefix = [0] * (len(names) + 1)
        for i in range(len(names) - 1, -1, -1):
            self.prefix[i] = self.prefix[i + 1] + len(self.c[i])
        self.counts = list(model.base)
        self.act = 0
        for i in range(model.nT):
            if model.traits[i] in model.cset and model.is_active(model.traits[i], self.counts[i]):
                self.act |= 1 << i
        self.k = self.act.bit_count()
        # 只有“恰好”类规则可能因为再加人而失效，最多回退 1
        self.slack = 1 if any('exact' in r for r in model.rules.values()) else 0
        self.found = []
        self.sel = [None] * self.r

    def _upd(self, i, sign):
        m = self.m
        for j, v in self.c[i]:
            old = self.counts[j]
            new = old + sign * v
            self.counts[j] = new
            t = m.traits[j]
            b, a = m.is_active(t, old), m.is_active(t, new)
            if b != a:
                if a:
                    self.act |= 1 << j
                    self.k += 1
                else:
                    self.act &= ~(1 << j)
                    self.k -= 1

    def _dfs(self, start, depth):
        rem = self.r - depth
        if rem == 0:
            if self.k == self.target:
                self.found.append(tuple(self.sel))
            return
        if self.k > self.target + self.slack:
            return
        reachable = (self.suffix[start] & ~self.act).bit_count()
        gain = self.prefix[start] - self.prefix[min(start + rem, len(self.names))]
        if self.k + min(gain, reachable) + self.slack < self.target:
            return
        last = len(self.names) - rem
        for i in range(start, last + 1):
            self.sel[depth] = self.names[i]
            self._upd(i, +1)
            if self.k <= self.target + self.slack:
                self._dfs(i + 1, depth + 1)
            self._upd(i, -1)

    def run(self):
        self._dfs(0, 0)
        return self.found


class MinKEnumerator:
    """枚举 size 人队（含固定成员），全员费用 <= cap，k >= kmin。"""

    def __init__(self, model, size, kmin, cap):
        self.m = model
        self.r = size - len(model.required)
        self.kmin = kmin
        pool = [n for n in model.units
                if n not in model.required and model.cost[n] <= cap]
        pool.sort(key=lambda n: (-sum(1 for t in model.contrib[n] if t in model.cset),
                                 model.cost[n], n))
        self.pool = pool
        self.c = [[(model.tidx[t], v) for t, v in model.contrib[n].items() if t in model.cset]
                  for n in pool]
        self.prefix = [0] * (len(pool) + 1)
        for i in range(len(pool) - 1, -1, -1):
            self.prefix[i] = self.prefix[i + 1] + len(self.c[i])
        self.counts = list(model.base)
        self.k = model.k_of(self.counts)
        self.out = []
        self.sel = [None] * self.r

    def _upd(self, i, sign):
        m = self.m
        for j, v in self.c[i]:
            old = self.counts[j]
            new = old + sign * v
            self.counts[j] = new
            t = m.traits[j]
            b, a = m.is_active(t, old), m.is_active(t, new)
            if b != a:
                self.k += 1 if a else -1

    def _dfs(self, start, depth):
        rem = self.r - depth
        if rem == 0:
            if self.k >= self.kmin:
                self.out.append(tuple(self.sel))
            return
        if self.k + self.prefix[start] - self.prefix[min(start + rem, len(self.pool))] + 1 < self.kmin:
            return
        last = len(self.pool) - rem
        for i in range(start, last + 1):
            self.sel[depth] = self.pool[i]
            self._upd(i, +1)
            self._dfs(i + 1, depth + 1)
            self._upd(i, -1)

    def run(self):
        self._dfs(0, 0)
        return self.out
