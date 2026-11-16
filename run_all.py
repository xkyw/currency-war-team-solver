# -*- coding: utf-8 -*-
"""
一键运行脚本 —— 配置都写在下面的 CONFIG 里，改完直接双击 / 运行即可。

    python run_all.py            # 按 CONFIG 跑（或双击 run.bat）
    python run_all.py --quick    # 快速试跑（k 只到 8、不算次优、过渡链到 9 人口）

会依次调用同目录下的：
    solve_teams.py       配队求解（k=3..max_k，最优 [+ 次优]）
    transition_teams.py  人口过渡链
输出写到 CONFIG['out_dir'] 目录。
"""

import json
import os
import subprocess
import sys
import time

# 沿用终端自身编码（VSCode/cmd 可能是 GBK），只把个别无法编码的字符替换掉，避免报错
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace", line_buffering=True)
    except Exception:
        pass

# ============================================================================
# 配置区：按需修改
# ============================================================================
CONFIG = {
    # ---------- 数据 ----------
    "data": "",                      # 留空 = 用内置数据；填路径 = 读外部赛季 JSON

    # ---------- 必带角色 / 转职星徽 ----------
    "required": ["花火", "刻律德菈", "那刻夏"],
    "emblems": {"那刻夏": ["梦境交织"]},          # 角色 -> 额外羁绊

    # ---------- 激活规则 ----------
    "independent": ["双龙吟", "盗火行者", "巡海游侠", "黑市主理人",
                    "机心巧匠", "幻乐之主"],       # 独立羁绊，不计入激活数
    "trait_rules": {
        "少女乐队": {"exact": [1, 4]},             # 仅恰好 1/4 人激活
        "千星商会": {"min": 2},                    # 1 人不生效，≥2 人才算
    },
    "cost_caps": {"7": 3, "8": 4, "9": 5, "10": 5, "11": 5},  # 人口 -> 费用上限

    # ---------- 跑什么 ----------
    "run_teams": True,               # 配队求解
    "max_k": 14,                     # 羁绊数上限
    "include_next": False,            # 是否连“次优（+1 人）”一起算：很慢、文件很大

    "run_transition": True,          # 人口过渡链
    "trans_from": 7,
    "trans_to": 11,
    "trans_top": 3,                  # 每个终点人口输出几条路线

    # ---------- 输出 ----------
    "out_dir": "输出",
}
# ============================================================================


def _should_pause():
    """双击运行（控制台里只有本进程）时，结束后停住，方便看输出。"""
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        arr = (ctypes.c_uint * 8)()
        n = k32.GetConsoleProcessList(arr, 8)
        if n > 1:
            return False
    except Exception:
        return False
    try:
        return bool(sys.stdin) and sys.stdin.isatty()
    except Exception:
        return False


HERE = os.path.dirname(os.path.abspath(__file__))


def find_data(cfg):
    """返回外部数据文件路径；没配置就返回 None（程序用内置数据）。"""
    if cfg.get("data"):
        p = os.path.abspath(cfg["data"])
        if not os.path.exists(p):
            sys.exit("CONFIG['data'] 指定的文件不存在：%s" % p)
        return p
    return None


def run_step(title, args):
    print("\n" + "=" * 70)
    print(">> " + title)
    print("=" * 70)
    t0 = time.time()
    p = subprocess.run([sys.executable] + args, cwd=HERE)
    print("<< %s 完成，用时 %.1f 秒（返回码 %d）" % (title, time.time() - t0, p.returncode))
    return p.returncode == 0


def run(cfg):
    data = find_data(cfg)
    out_dir = os.path.join(HERE, cfg.get("out_dir") or "输出")
    os.makedirs(out_dir, exist_ok=True)

    # 把 CONFIG 里与模型有关的项写成临时配置文件，供两个程序读取
    model_cfg = {k: cfg[k] for k in
                 ("required", "emblems", "independent", "trait_rules", "cost_caps")
                 if k in cfg}
    tmp_cfg = os.path.join(HERE, "_run_cfg.json")
    with open(tmp_cfg, "w", encoding="utf-8") as f:
        json.dump(model_cfg, f, ensure_ascii=False, indent=1)

    print("数据     : %s" % (data or "内置（data_v47.py，v4.7）"))
    print("输出目录 : %s" % out_dir)
    print("必带角色 : %s" % "、".join(cfg["required"]))
    print("转职     : %s" % (", ".join("%s→%s" % (k, "+".join(v))
                                   for k, v in cfg.get("emblems", {}).items()) or "无"))
    print("规则     : %s" % ", ".join("%s=%s" % (k, v)
                                   for k, v in cfg.get("trait_rules", {}).items()))

    ok = True
    t_all = time.time()
    try:
        if cfg.get("run_teams", True):
            args = ["solve_teams.py"] + ([data] if data else []) + [
                "--config", tmp_cfg,
                "--max-k", str(cfg.get("max_k", 14)),
                "--out", os.path.join(out_dir, "answer")]
            if not cfg.get("include_next", True):
                args.append("--no-next")
            ok = run_step("配队求解（k=3..%d）" % cfg.get("max_k", 14), args) and ok

        if cfg.get("run_transition", True):
            args = ["transition_teams.py"] + ([data] if data else []) + [
                "--config", tmp_cfg,
                    "--from", str(cfg.get("trans_from", 7)),
                    "--to", str(cfg.get("trans_to", 11)),
                    "--top", str(cfg.get("trans_top", 3)),
                    "--out", os.path.join(out_dir, "transition")]
            ok = run_step("人口过渡链（%d→%d 人口）" % (cfg.get("trans_from", 7), cfg.get("trans_to", 11)), args) and ok
    finally:
        if os.path.exists(tmp_cfg):
            os.remove(tmp_cfg)

    print("\n" + "=" * 70)
    print("全部完成，总用时 %.1f 秒" % (time.time() - t_all))
    print("=" * 70)
    for root, _, files in os.walk(out_dir):
        for fn in sorted(files):
            p = os.path.join(root, fn)
            print("  %-14s %8.1f KB  %s" % (fn, os.path.getsize(p) / 1024,
                                            os.path.relpath(p, HERE)))
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    if "--quick" in sys.argv:
        CONFIG.update({"max_k": 8, "include_next": False,
                       "trans_to": 9, "trans_top": 1, "out_dir": "输出_试跑"})
        print("（快速试跑模式）")
    try:
        run(CONFIG)
    finally:
        if "--no-pause" not in sys.argv and _should_pause():
            try:
                input("\n按回车键关闭窗口...")
            except Exception:
                pass
