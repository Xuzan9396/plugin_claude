#!/usr/bin/env python3
"""XZ Planning - 辅助脚本，处理文件操作、状态解析、交互式菜单。"""

import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path

# 项目根目录：始终使用当前工作目录，不依赖脚本位置
PROJECT_ROOT = Path.cwd()
PLANNING_DIR = PROJECT_ROOT / ".xz_planning"
PHASES_DIR = PLANNING_DIR / "phases"
ARCHIVE_DIR = PLANNING_DIR / "archive"
STATE_FILE = PLANNING_DIR / "STATE.md"


# 版本号格式：整数或小数，如 1 / 1.5 / 2.5 / 1.5.2
_VERSION_RE = r"\d+(?:\.\d+)*"


def _version_tuple(v: str):
    """版本号字符串转可比较的数值元组：'1.5' -> (1, 5)，'2' -> (2,)。"""
    return tuple(int(p) for p in v.split("."))


def _split_dir(name: str):
    """拆分目录名 'N.名称' -> (版本号, 名称)，版本号支持小数。
    '1.5.订单优化' -> ('1.5', '订单优化')；'1.订单优化' -> ('1', '订单优化')。
    版本号后必须紧跟 '.' 再接名称；不匹配返回 (None, None)。"""
    m = re.match(rf"^({_VERSION_RE})\.(.+)$", name)
    if m:
        return m.group(1), m.group(2)
    return None, None


def _parse_n(n: str):
    """用户输入的版本号 -> 数值元组，非法返回 None。"""
    if n and re.fullmatch(_VERSION_RE, n):
        return _version_tuple(n)
    return None


def _sort_by_version(path: Path):
    """按版本号数值排序：'1.xxx' < '1.5.xxx' < '2.xxx' < '10.xxx'。非版本目录退化到末尾。"""
    ver, _ = _split_dir(path.name)
    if ver:
        return (0, _version_tuple(ver), "")
    return (1, (), path.name)


def _sorted_phases(base: Path):
    return sorted(base.iterdir(), key=_sort_by_version)


def init():
    """初始化 .xz_planning 目录结构。"""
    PHASES_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    if not STATE_FILE.exists():
        STATE_FILE.write_text(
            "# XZ Planning State\n\n"
            "## 当前进度\n\n"
            "| 版本 | 需求 | 讨论 | 状态 | 进度 | 创建时间 |\n"
            "|------|------|------|------|------|----------|\n\n"
            "## 已归档\n\n"
            "| 版本 | 需求 | 完成时间 |\n"
            "|------|------|----------|\n"
        )
    print(json.dumps({"ok": True, "planning_dir": str(PLANNING_DIR)}))


def _build_phase(d: Path, ver: str, archived: bool) -> dict:
    """用目录真实版本号构造 phase 信息（文件名以目录解析出的版本号为准）。"""
    plan_file = d / f"{ver}-PLAN.md"
    discuss_file = d / f"{ver}-DISCUSS.md"
    return {
        "dir": str(d),
        "dir_name": d.name,
        "version": ver,
        "plan_file": str(plan_file),
        "plan_exists": plan_file.exists(),
        "discuss_file": str(discuss_file),
        "discuss_exists": discuss_file.exists(),
        "archived": archived,
    }


def find_phase(n: str, include_archive: bool = False) -> dict | None:
    """查找版本 N 对应的 phases 目录。版本号按数值精确匹配（查 '1' 不会误中 '1.5'）。
    include_archive=True 时也查 archive。"""
    target = _parse_n(n)
    if target is None or not PHASES_DIR.exists():
        return None
    # 先找活跃版本
    for d in PHASES_DIR.iterdir():
        if not d.is_dir() or d.name == "archive":
            continue
        ver, _ = _split_dir(d.name)
        if ver and _version_tuple(ver) == target:
            return _build_phase(d, ver, archived=False)
    # 再找归档版本
    if include_archive and ARCHIVE_DIR.exists():
        for d in ARCHIVE_DIR.iterdir():
            if not d.is_dir():
                continue
            ver, _ = _split_dir(d.name)
            if ver and _version_tuple(ver) == target:
                return _build_phase(d, ver, archived=True)
    return None


def parse_plan(n: str, include_archive: bool = False):
    """解析 N-PLAN.md，返回结构化 JSON。"""
    phase = find_phase(n, include_archive=include_archive)
    if not phase:
        print(json.dumps({"ok": False, "error": f"版本 {n} 不存在"}))
        return
    if not phase["plan_exists"]:
        # 目录存在但无 PLAN（可能只有 DISCUSS）
        print(json.dumps({"ok": False, "error": f"版本 {n} 的计划不存在", "phase": phase}, ensure_ascii=False))
        return

    content = Path(phase["plan_file"]).read_text(encoding="utf-8")

    # 解析 todolist 条目
    todos = []
    pattern = re.compile(r"^- \[([ x])\] (\d+)\. (.+)$", re.MULTILINE)
    for m in pattern.finditer(content):
        done = m.group(1) == "x"
        num = int(m.group(2))
        title = m.group(3).strip()
        todos.append({"num": num, "title": title, "done": done})

    total = len(todos)
    completed = sum(1 for t in todos if t["done"])

    print(
        json.dumps(
            {
                "ok": True,
                "phase": phase,
                "todos": todos,
                "total": total,
                "completed": completed,
                "progress": f"{completed}/{total}",
            },
            ensure_ascii=False,
        )
    )


def status():
    """扫描所有 PLAN.md，输出 JSON 状态。"""
    if not PLANNING_DIR.exists():
        print(json.dumps({"ok": True, "active": [], "archived": [], "initialized": False}))
        return

    active = []
    archived = []

    # 扫描活跃版本
    if PHASES_DIR.exists():
        for d in _sorted_phases(PHASES_DIR):
            if not d.is_dir() or d.name == "archive":
                continue
            n, name = _split_dir(d.name)
            if n is None:
                continue
            plan_file = d / f"{n}-PLAN.md"
            discuss_file = d / f"{n}-DISCUSS.md"
            total = 0
            completed = 0
            if plan_file.exists():
                content = plan_file.read_text(encoding="utf-8")
                for m in re.finditer(r"^- \[([ x])\] \d+\.", content, re.MULTILINE):
                    total += 1
                    if m.group(1) == "x":
                        completed += 1
            active.append(
                {
                    "version": n,
                    "name": name,
                    "total": total,
                    "completed": completed,
                    "has_discuss": discuss_file.exists(),
                }
            )

    # 扫描归档
    if ARCHIVE_DIR.exists():
        for d in _sorted_phases(ARCHIVE_DIR):
            if not d.is_dir():
                continue
            n, name = _split_dir(d.name)
            if n is not None:
                archived.append({"version": n, "name": name})

    print(
        json.dumps(
            {"ok": True, "active": active, "archived": archived, "initialized": True},
            ensure_ascii=False,
        )
    )


def _archive_one(src: Path) -> str:
    """把单个 phase 目录移入 archive，返回移动描述。同名目标先删再移。"""
    dst = ARCHIVE_DIR / src.name
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        shutil.rmtree(dst)
    shutil.move(str(src), str(dst))
    return f"{src.name} -> archive/{src.name}"


def _list_phases():
    """列出 phases 下的目录，返回 (合法版本目录列表, 被跳过的名字列表)。"""
    targets, skipped = [], []
    if not PHASES_DIR.exists():
        return targets, skipped
    for d in _sorted_phases(PHASES_DIR):
        if not d.is_dir() or d.name == "archive":
            continue
        ver, _ = _split_dir(d.name)
        if ver:
            targets.append(d)
        else:
            skipped.append(d.name)
    return targets, skipped


def list_phases():
    """输出 phases 下全部版本的清单（供 xz-done all 归档前预览）。"""
    targets, skipped = _list_phases()
    items = []
    for d in targets:
        ver, name = _split_dir(d.name)
        plan_file = d / f"{ver}-PLAN.md"
        total = completed = 0
        status_text = ""
        if plan_file.exists():
            content = plan_file.read_text(encoding="utf-8")
            for m in re.finditer(r"^- \[([ x])\] \d+\.", content, re.MULTILINE):
                total += 1
                if m.group(1) == "x":
                    completed += 1
            sm = re.search(r"^>\s*状态:\s*(.+)$", content, re.MULTILINE)
            if sm:
                status_text = sm.group(1).strip()
        items.append(
            {
                "version": ver,
                "name": name,
                "dir_name": d.name,
                "plan_exists": plan_file.exists(),
                "total": total,
                "completed": completed,
                "progress": f"{completed}/{total}",
                "status": status_text,
            }
        )
    print(
        json.dumps(
            {"ok": True, "count": len(items), "phases": items, "skipped": skipped},
            ensure_ascii=False,
        )
    )


def complete(n: str):
    """将版本 N 移入 archive，更新 STATE.md。N 为 'all' 时归档 phases 下全部版本。"""
    if n.strip().lower() == "all":
        complete_all()
        return

    phase = find_phase(n)
    if not phase:
        print(json.dumps({"ok": False, "error": f"版本 {n} 不存在"}))
        return

    moved = _archive_one(Path(phase["dir"]))
    _update_state()
    print(json.dumps({"ok": True, "moved": moved}, ensure_ascii=False))


def complete_all():
    """强制归档 phases 下全部版本，不看完成度。"""
    if not PHASES_DIR.exists():
        print(
            json.dumps(
                {"ok": False, "error": ".xz_planning/phases 目录不存在"},
                ensure_ascii=False,
            )
        )
        return

    targets, skipped = _list_phases()
    if not targets:
        print(
            json.dumps(
                {
                    "ok": True,
                    "mode": "all",
                    "count": 0,
                    "archived": [],
                    "skipped": skipped,
                    "note": "phases 下没有可归档的版本目录",
                },
                ensure_ascii=False,
            )
        )
        return

    archived = [_archive_one(d) for d in targets]
    _update_state()
    print(
        json.dumps(
            {
                "ok": True,
                "mode": "all",
                "count": len(archived),
                "archived": archived,
                "skipped": skipped,
            },
            ensure_ascii=False,
        )
    )


def delete(n: str):
    """删除版本 N 的目录，更新 STATE.md。"""
    phase = find_phase(n)
    if not phase:
        print(json.dumps({"ok": False, "error": f"版本 {n} 不存在"}))
        return

    dir_path = Path(phase["dir"])
    dir_name = dir_path.name
    shutil.rmtree(dir_path)

    _update_state()
    print(json.dumps({"ok": True, "deleted": dir_name}, ensure_ascii=False))


def remove_all():
    """交互式菜单删除 .xz_planning。"""
    if not PLANNING_DIR.exists():
        print(json.dumps({"ok": False, "error": ".xz_planning 目录不存在"}))
        return

    # 收集当前内容摘要
    summary = []
    if PHASES_DIR.exists():
        for d in _sorted_phases(PHASES_DIR):
            if not d.is_dir() or d.name == "archive":
                continue
            summary.append(f"  phases/{d.name}")
        if ARCHIVE_DIR.exists():
            for d in _sorted_phases(ARCHIVE_DIR):
                if d.is_dir():
                    summary.append(f"  archive/{d.name}")

    try:
        import select as _sel

        has_tty = sys.stdin.isatty()
    except Exception:
        has_tty = False

    if not has_tty:
        # 非交互模式，输出内容让 AI 处理
        print(
            json.dumps(
                {"ok": True, "mode": "non-interactive", "contents": summary},
                ensure_ascii=False,
            )
        )
        return

    # 交互式菜单
    options = ["全部删除（删除整个 .xz_planning）", "否（取消）"]
    selected = 0
    custom_mode = False
    custom_input = ""

    def render():
        # 清屏并重绘
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.write("⚠️  清理 .xz_planning\n\n")
        sys.stdout.write("当前内容:\n")
        for line in summary:
            sys.stdout.write(f"  {line}\n")
        sys.stdout.write("\n")

        if not custom_mode:
            sys.stdout.write("↑↓ 选择操作:\n")
            for i, opt in enumerate(options):
                prefix = " › ●" if i == selected else "   ○"
                sys.stdout.write(f"{prefix} {opt}\n")
            sys.stdout.write("\n[Tab] 切换到自定义输入\n")
        else:
            sys.stdout.write("自定义输入（输入删除要求，回车确认，Tab 返回）:\n")
            sys.stdout.write(f"> {custom_input}\n")
        sys.stdout.flush()

    import tty
    import termios

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        render()
        while True:
            ch = sys.stdin.read(1)
            if ch == "\t":
                custom_mode = not custom_mode
                render()
                continue
            if custom_mode:
                if ch in ("\r", "\n"):
                    break
                elif ch == "\x7f":  # backspace
                    custom_input = custom_input[:-1]
                    render()
                elif ch == "\x03":  # Ctrl+C
                    selected = 1
                    custom_mode = False
                    break
                elif ch >= " ":
                    custom_input += ch
                    render()
            else:
                if ch == "\x1b":
                    seq = sys.stdin.read(2)
                    if seq == "[A":  # up
                        selected = (selected - 1) % len(options)
                    elif seq == "[B":  # down
                        selected = (selected + 1) % len(options)
                    render()
                elif ch in ("\r", "\n"):
                    break
                elif ch == "\x03":  # Ctrl+C
                    selected = 1
                    break
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()

    if custom_mode and custom_input.strip():
        print(
            json.dumps(
                {"ok": True, "action": "custom", "input": custom_input.strip()},
                ensure_ascii=False,
            )
        )
    elif selected == 0:
        shutil.rmtree(PLANNING_DIR)
        print(json.dumps({"ok": True, "action": "remove_all", "removed": str(PLANNING_DIR)}))
    else:
        print(json.dumps({"ok": True, "action": "cancel"}))


def _update_state():
    """重新扫描 phases 并重建 STATE.md。"""
    active_rows = []
    archived_rows = []

    if PHASES_DIR.exists():
        for d in _sorted_phases(PHASES_DIR):
            if not d.is_dir() or d.name == "archive":
                continue
            n, name = _split_dir(d.name)
            if n is None:
                continue
            plan_file = d / f"{n}-PLAN.md"
            discuss_file = d / f"{n}-DISCUSS.md"
            total = completed = 0
            created = ""
            discuss_flag = "💬" if discuss_file.exists() else ""
            status_text = "📋 已计划"
            if plan_file.exists():
                content = plan_file.read_text(encoding="utf-8")
                for m in re.finditer(r"^- \[([ x])\] \d+\.", content, re.MULTILINE):
                    total += 1
                    if m.group(1) == "x":
                        completed += 1
                cm = re.search(r"创建时间:\s*(.+)", content)
                if cm:
                    created = cm.group(1).strip()
                if completed > 0 and completed < total:
                    status_text = "🚧 进行中"
                elif completed == total and total > 0:
                    status_text = "✅ 已完成"
            elif discuss_file.exists():
                status_text = "💬 讨论中"
            active_rows.append(
                f"| {n} | {name} | {discuss_flag} | {status_text} | {completed}/{total} | {created} |"
            )

    if ARCHIVE_DIR.exists():
        for d in _sorted_phases(ARCHIVE_DIR):
            if not d.is_dir():
                continue
            n, name = _split_dir(d.name)
            if n is not None:
                # 尝试从 PLAN 文件提取完成时间
                plan_file = d / f"{n}-PLAN.md"
                archived_time = ""
                if plan_file.exists():
                    content = plan_file.read_text(encoding="utf-8")
                    # 取变更记录最后一条时间
                    times = re.findall(r"^- (\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})", content, re.MULTILINE)
                    if times:
                        archived_time = times[-1]
                if not archived_time:
                    archived_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                archived_rows.append(f"| {n} | {name} | {archived_time} |")

    state_content = (
        "# XZ Planning State\n\n"
        "## 当前进度\n\n"
        "| 版本 | 需求 | 讨论 | 状态 | 进度 | 创建时间 |\n"
        "|------|------|------|------|------|----------|\n"
    )
    for row in active_rows:
        state_content += row + "\n"
    state_content += (
        "\n## 已归档\n\n"
        "| 版本 | 需求 | 完成时间 |\n"
        "|------|------|----------|\n"
    )
    for row in archived_rows:
        state_content += row + "\n"

    STATE_FILE.write_text(state_content, encoding="utf-8")


def update_state():
    """公开的 update-state 命令：重新扫描 phases 并重建 STATE.md。"""
    if not PLANNING_DIR.exists():
        print(json.dumps({"ok": False, "error": ".xz_planning 目录不存在"}))
        return
    _update_state()
    print(json.dumps({"ok": True, "message": "STATE.md 已更新"}, ensure_ascii=False))


# ---------------- worktree 并行开发（供 /xz-worktree 使用） ----------------
#
# 机制：子 agent 只在自己的 worktree 里改文件、不碰 git 历史；主会话抓
# `git diff --binary` 成 patch，再按组序串行 `git apply` 到主工作区，**不 commit**。
# 成功即删 worktree，冲突/失败保留现场。

_GROUP_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
_WT_BRANCH_PREFIX = "xz-worktree"
_WT_MAX_GROUPS = 4


def _git(args, cwd=None, binary=False):
    """跑 git，返回 (rc, stdout, stderr)。cwd 默认项目根。

    binary=True 时 stdout 是**原始字节、不做任何解码** —— 抓 patch 必须用它：
    git 只把含 NUL 的文件当二进制（走 base85，字节安全），GBK/Big5/Latin-1 这类
    非 UTF-8 纯文本是原样字节进 diff 的，一旦经过 errors="replace" 就会被换成
    U+FFFD，patch 应用后文件内容静默变乱码（新建文件没有 context，git 不会拦）。
    """
    p = subprocess.run(
        ["git", "-C", str(cwd or PROJECT_ROOT), *args],
        capture_output=True,
        **({} if binary else {"text": True, "encoding": "utf-8", "errors": "replace"}),
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )
    if binary:
        return p.returncode, p.stdout, p.stderr.decode("utf-8", "replace")
    return p.returncode, p.stdout, p.stderr


def _wt_exclude_planning(root: Path) -> str:
    """`.xz_planning/` 的 pathspec 排除项（不参与干净检查、不进 patch）。

    必须按运行目录实算：xz-planning 允许任意目录持有自己的 `.xz_planning/`，
    仓库根 ≠ 运行目录时（仓库根 `~/project`，用户在 `~/project/backend` 里跑），
    写死 `:(exclude).xz_planning` 排不掉 `backend/.xz_planning` —— 会让
    `wt create` 永远判脏，还会让子 agent 违规改的 PLAN 混进 patch。
    """
    try:
        rel = PLANNING_DIR.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        rel = ".xz_planning"
    return f":(exclude,top){rel}"


def _fail(msg: str, **extra):
    """输出失败 JSON 并以非零码退出（skill 靠 ok 字段判走向）。"""
    print(json.dumps({"ok": False, "error": msg, **extra}, ensure_ascii=False, indent=2))
    sys.exit(1)


def _repo_root() -> Path | None:
    rc, out, _ = _git(["rev-parse", "--show-toplevel"])
    return Path(out.strip()) if rc == 0 and out.strip() else None


def _wt_state_dir(phase: dict) -> Path:
    d = Path(phase["dir"]) / "worktree"
    d.mkdir(parents=True, exist_ok=True)
    # 自带忽略：patch 可能几 MB 且含二进制块，别让 `git add -A` 把它提交进用户仓库。
    # 写在自己目录里，不依赖用户项目根的 .gitignore 怎么配。
    gi = d / ".gitignore"
    if not gi.exists():
        gi.write_text("*\n", encoding="utf-8")
    return d


def _wt_handoff_file(phase: dict, group: str) -> Path:
    return _wt_state_dir(phase) / f"{group}.handoff.json"


def _wt_read_handoff(phase: dict, group: str) -> dict | None:
    f = _wt_handoff_file(phase, group)
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def _wt_write_handoff(phase: dict, h: dict) -> None:
    """原子落盘：写临时文件再 os.replace，避免中途被打断留下半个 JSON。"""
    f = _wt_handoff_file(phase, h["group"])
    tmp = f.with_name(f.name + ".tmp")
    tmp.write_text(json.dumps(h, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, f)


def _wt_all_handoffs(phase: dict) -> list[dict]:
    """读全部 handoff。**一个坏文件不许炸掉整批** —— 降级成 unreadable 记录。"""
    d = Path(phase["dir"]) / "worktree"
    if not d.exists():
        return []
    out = []
    for f in sorted(d.glob("*.handoff.json")):
        try:
            out.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception as e:
            out.append({"group": f.name[: -len(".handoff.json")], "integration": "unreadable",
                        "worktree_path": "", "branch": "", "base_commit": "", "patch_file": "",
                        "changed_files": [], "repo_root": "",
                        "error": f"handoff 读不出来（{type(e).__name__}: {e}），请手工看 {f}"})
    return out


def _wt_phase_or_fail(n: str) -> dict:
    # include_archive：已归档的版本至少还要能 list / clean，否则现场永远收不掉
    phase = find_phase(n, include_archive=True)
    if not phase:
        _fail(f"版本 {n} 不存在")
    return phase


def _wt_cleanup(h: dict) -> str | None:
    """删 worktree 与临时分支；父目录空了才删。返回错误摘要，无错则 None。"""
    if not h.get("worktree_path") or not h.get("repo_root"):
        return "handoff 里没有 worktree 路径或仓库根，无法清理"
    errs = []
    rc, _, err = _git(["worktree", "remove", "--force", h["worktree_path"]], cwd=h["repo_root"])
    if rc != 0:
        errs.append(f"worktree remove: {err.strip()}")
    rc, _, err = _git(["branch", "-D", h["branch"]], cwd=h["repo_root"])
    if rc != 0:
        errs.append(f"branch delete: {err.strip()}")
    for p in (Path(h["worktree_path"]).parent, Path(h["worktree_path"]).parent.parent):
        try:
            p.rmdir()          # 非递归：只删空目录
        except OSError:
            break
    return "\n".join(errs) if errs else None


def wt_create(n: str, groups: list[str]):
    """为每个组建一个同级 worktree。主工作区必须干净，否则拒绝。"""
    phase = _wt_phase_or_fail(n)
    root = _repo_root()
    if root is None:
        _fail("当前目录不是 git 仓库，worktree 并行开发不可用")
    if not groups:
        _fail("至少要一个组名。用法: wt create <N> <组名>...")
    if len(groups) > _WT_MAX_GROUPS:
        _fail(f"并行组数上限 {_WT_MAX_GROUPS}，收到 {len(groups)} 个：把小组并起来")
    seen = set()
    for g in groups:
        if not _GROUP_RE.match(g):
            _fail(f"组名不合法（只许字母/数字/下划线/连字符，1-40 字符）: {g}")
        if g in seen:
            _fail(f"组名重复: {g}")
        seen.add(g)
        # 同名组会覆盖 handoff 与 patch，上一轮的现场就此失联（wt list 看不到、
        # wt clean 删不掉，只剩 git worktree list 里还挂着）。重跑时最容易踩。
        old = _wt_read_handoff(phase, g)
        if old and old.get("integration") not in ("applied", "no_changes"):
            _fail(f"组 {g} 还有未收尾的现场（{old.get('integration')}）: {old.get('worktree_path')}。"
                  f"先跑 `wt clean {n} {g}` 收掉，或换个组名——"
                  "同名会覆盖上一轮的 handoff 与 patch，现场就再也定位不到了。",
                  group=g, old_worktree=old.get("worktree_path"), old_branch=old.get("branch"))

    # 干净检查排除 .xz_planning/：它是本工具的元数据目录，常年未跟踪，
    # 且子 agent 明令禁止碰它、patch 也不含它，参与判定只会让 create 永远被拒。
    exclude = _wt_exclude_planning(root)
    rc, out, err = _git(["status", "--porcelain", "--untracked-files=all",
                         "--", ".", exclude], cwd=root)
    if rc != 0:
        _fail(f"git status 失败: {err.strip()}")
    dirty = [ln for ln in out.splitlines() if ln.strip()]
    if dirty:
        _fail("主工作区不干净，无法开始并行开发。请先 commit 或 stash 这些改动后重跑。",
              dirty_files=dirty[:50],
              hint="patch 集成依赖 base commit 对齐；工作区有未提交改动会把你的改动和 agent 的改动搅在一起")

    rc, out, err = _git(["rev-parse", "HEAD"], cwd=root)
    if rc != 0:
        _fail(f"取 HEAD 失败（仓库可能还没有任何提交）: {err.strip()}")
    base = out.strip()

    # 运行目录相对仓库根的前缀：仓库根 ≠ 运行目录时，子 agent 该待的是 worktree
    # 里的同名子目录，不是 worktree 根
    rc, prefix_out, _ = _git(["rev-parse", "--show-prefix"], cwd=PROJECT_ROOT)
    prefix = prefix_out.strip() if rc == 0 else ""

    parent = root.parent / "worktree" / root.name
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        _fail(f"建不了 worktree 父目录 {parent}: {e}（仓库上级目录不可写？）")
    created: list[dict] = []
    for g in groups:
        sid = uuid.uuid4().hex[:8]
        path = parent / f"{g}-{sid}"
        branch = f"{_WT_BRANCH_PREFIX}/{g}-{sid}"
        rc, _, err = _git(["worktree", "add", "-b", branch, str(path), base], cwd=root)
        if rc != 0:
            for c in created:                      # 建到一半就整批回滚，不留残骸
                _wt_cleanup(c)
                _wt_handoff_file(phase, c["group"]).unlink(missing_ok=True)
            _fail(f"建 worktree 失败（组 {g}）: {err.strip()}")
        h = {
            "group": g, "version": phase["version"], "repo_root": str(root),
            "worktree_path": str(path),
            # exec_cwd 才是交给子 agent 的工作目录（仓库根 = 运行目录时两者相同）
            "exec_cwd": str(path / prefix) if prefix else str(path),
            "branch": branch, "base_commit": base,
            "patch_file": str(_wt_state_dir(phase) / f"{g}.patch"),
            "changed_files": [], "ignored_files": [],
            "integration": "pending", "captured": False,
        }
        _wt_write_handoff(phase, h)
        created.append(h)

    print(json.dumps({"ok": True, "version": phase["version"], "base_commit": base,
                      "repo_root": str(root), "worktrees": created},
                     ensure_ascii=False, indent=2))


def wt_capture(n: str, group: str):
    """把某组 worktree 的改动（含未跟踪、删除、二进制）抓成一个 patch。"""
    phase = _wt_phase_or_fail(n)
    h = _wt_read_handoff(phase, group)
    if not h:
        _fail(f"组 {group} 没有 worktree 记录（先跑 wt create）")
    wt_path = Path(h["worktree_path"])
    if not wt_path.exists():
        _fail(f"worktree 目录不存在（可能已被清理）: {wt_path}")

    exclude = _wt_exclude_planning(Path(h["repo_root"]))
    rc, _, err = _git(["add", "-N", "--all"], cwd=wt_path)   # 未跟踪文件也进 diff
    if rc != 0:
        _fail(f"git add -N 失败: {err.strip()}")
    # patch 与文件名都走字节通道：非 UTF-8 的纯文本文件不能经过有损解码（见 _git 注释）
    rc, patch, err = _git(["diff", "--binary", "--no-ext-diff", h["base_commit"],
                           "--", ".", exclude], cwd=wt_path, binary=True)
    if rc != 0:
        _fail(f"抓 patch 失败: {err.strip()}")
    rc, names, err = _git(["diff", "--name-only", "-z", h["base_commit"],
                           "--", ".", exclude], cwd=wt_path, binary=True)
    if rc != 0:
        _fail(f"取改动文件列表失败: {err.strip()}")
    # 被 .gitignore 挡住的新文件进不了 patch，必须报出来——否则会被当成「一个文件都没改」
    rc_i, ign, _ = _git(["ls-files", "-o", "-i", "--exclude-standard", "-z"],
                        cwd=wt_path, binary=True)
    ignored = [os.fsdecode(f) for f in ign.split(b"\0") if f] if rc_i == 0 else []

    files = [os.fsdecode(f) for f in names.split(b"\0") if f]
    Path(h["patch_file"]).write_bytes(patch)
    h["changed_files"] = files
    h["ignored_files"] = ignored
    h["captured"] = True
    _wt_write_handoff(phase, h)
    out = {"ok": True, "group": group, "changed_files": files,
           "patch_file": h["patch_file"], "empty": not files, "ignored_files": ignored}
    if not files and ignored:
        out["warning"] = ("这一组的改动全落在被 .gitignore 挡住的路径上，抓不进 patch。"
                          "现场会保留下来，别当成「没改动」——要么把这些路径从 .gitignore 摘出来，"
                          "要么手工从 worktree 里取走这些文件。")
    print(json.dumps(out, ensure_ascii=False, indent=2))


def wt_apply(n: str, groups=None, preserve=None):
    """按组序串行把各组 patch 应用到主工作区。不 commit。一组冲突不阻止后续组。"""
    phase = _wt_phase_or_fail(n)
    root = _repo_root()
    if root is None:
        _fail("当前目录不是 git 仓库")
    all_h = _wt_all_handoffs(phase)
    if not all_h:
        _fail(f"版本 {n} 没有 worktree 记录")
    preserve = set(preserve or [])
    # preserve 必须校验：写错一个字母（或大小写不符）保护就静默失效，
    # 开发失败那组的 patch 会被当成正常组合并进去——正是它要防的事
    unknown_preserve = sorted(preserve - {h["group"] for h in all_h})
    if unknown_preserve:
        _fail(f"--preserve 里这些组没有 worktree 记录（写错了？）: {', '.join(unknown_preserve)}",
              known_groups=sorted(h["group"] for h in all_h))
    if groups:
        missing = [g for g in groups if not any(h["group"] == g for h in all_h)]
        if missing:
            _fail(f"这些组没有 worktree 记录: {', '.join(missing)}")
        outside = sorted(preserve - set(groups))
        if outside:
            _fail(f"--preserve 里这些组不在本次要集成的组里: {', '.join(outside)}")
        order = {g: i for i, g in enumerate(groups)}
        wanted = sorted([h for h in all_h if h["group"] in order], key=lambda h: order[h["group"]])
    else:
        wanted = all_h

    rc, out, err = _git(["rev-parse", "HEAD"], cwd=root)
    if rc != 0:
        _fail(f"取 HEAD 失败: {err.strip()}")
    head = out.strip()
    drifted = sorted({h["base_commit"] for h in wanted if h["base_commit"] != head})
    if drifted:
        _fail("主分支 HEAD 在并行开发期间变了，patch 的 base 已漂移，拒绝集成。"
              "先查清是谁动了 git，或用 wt list 看现场后手工处理。",
              head=head, expected_base=drifted)

    results = []
    for h in wanted:
        g = h["group"]
        if h.get("integration") == "unreadable":
            results.append({"group": g, "integration": "unreadable",
                            "note": h.get("error", "handoff 读不出来，本组跳过")})
            continue
        # 幂等：apply 不 commit、patch 也不删，所以重跑（bash 超时后模型重试、
        # 用户手工再跑一次）会让已成功的组第二次 apply 必然失败，把 applied
        # 覆写成 conflict，「已合并」这个事实就被擦掉了。这里直接短路。
        if h.get("integration") in ("applied", "no_changes"):
            results.append({"group": g, "integration": f"already_{h['integration']}",
                            "changed_files": h.get("changed_files", []),
                            "note": f"本组之前已判定 {h['integration']}，跳过（重跑安全）"})
            continue
        if g in preserve:                              # 该组开发失败：只留现场，不集成
            h["integration"] = "preserved"
            _wt_write_handoff(phase, h)
            results.append({"group": g, "integration": "preserved",
                            "changed_files": h.get("changed_files", []),
                            "worktree_path": h["worktree_path"],
                            "note": "该组开发失败，现场已保留供检查"})
            continue
        if not h.get("captured"):
            results.append({"group": g, "integration": "not_captured",
                            "note": "还没跑 wt capture，本组跳过"})
            continue
        if not h["changed_files"]:
            h["integration"] = "no_changes"
            _wt_write_handoff(phase, h)
            ignored = h.get("ignored_files") or []
            row = {"group": g, "integration": "no_changes", "changed_files": [],
                   "note": "该组一个文件都没改——实现类任务应判失败"}
            if ignored:
                # 改动全被 .gitignore 挡住时**不能删 worktree**，否则 agent 的活白干了
                row["ignored_files"] = ignored
                row["worktree_path"] = h["worktree_path"]
                row["note"] = ("改动全落在被 .gitignore 挡住的路径上，抓不进 patch。"
                               "**现场已保留**，别当成没干活——手工从 worktree 里取，"
                               "或把这些路径从 .gitignore 摘出来后重跑 capture")
            else:
                row["cleanup_error"] = _wt_cleanup(h)
            results.append(row)
            continue

        patch_file = Path(h["patch_file"])
        # 必须按字节读：patch 里可能有非 UTF-8 的纯文本内容（GBK 源码等）
        if not patch_file.exists() or not patch_file.read_bytes().strip():
            h["integration"] = "conflict"
            _wt_write_handoff(phase, h)
            results.append({"group": g, "integration": "conflict",
                            "error": "有改动文件但 patch 是空的，现场保留",
                            "worktree_path": h["worktree_path"]})
            continue

        rc, _, err = _git(["apply", "--check", str(patch_file)], cwd=root)
        if rc == 0:
            rc, _, err = _git(["apply", str(patch_file)], cwd=root)
        if rc != 0:
            h["integration"] = "conflict"
            _wt_write_handoff(phase, h)
            results.append({"group": g, "integration": "conflict", "error": err.strip(),
                            "changed_files": h["changed_files"],
                            "worktree_path": h["worktree_path"],
                            "patch_file": str(patch_file)})
            continue

        h["integration"] = "applied"
        _wt_write_handoff(phase, h)
        results.append({"group": g, "integration": "applied",
                        "changed_files": h["changed_files"],
                        "cleanup_error": _wt_cleanup(h)})

    print(json.dumps({
        "ok": True, "version": phase["version"], "committed": False,
        "applied": sum(1 for r in results if r["integration"] == "applied"),
        "total": len(results), "results": results,
    }, ensure_ascii=False, indent=2))


def wt_clean(n: str, groups=None):
    """删掉本版本（或指定组）的 worktree 与临时分支，handoff 记录保留。"""
    phase = _wt_phase_or_fail(n)
    want = set(groups or [])
    targets = [h for h in _wt_all_handoffs(phase) if not want or h["group"] in want]
    if not targets:
        _fail("没有匹配的 worktree 记录")
    out = []
    for h in targets:
        err = _wt_cleanup(h)
        h["cleaned"] = err is None
        _wt_write_handoff(phase, h)
        out.append({"group": h["group"], "cleaned": err is None, "cleanup_error": err})
    print(json.dumps({"ok": True, "version": phase["version"], "cleaned": out},
                     ensure_ascii=False, indent=2))


def wt_list(n: str):
    """列出本版本所有 worktree 及集成状态。"""
    phase = _wt_phase_or_fail(n)
    rows = [{
        "group": h["group"], "integration": h.get("integration", "pending"),
        "captured": h.get("captured", False), "changed_files": h.get("changed_files", []),
        "worktree_path": h["worktree_path"], "worktree_exists": Path(h["worktree_path"]).exists(),
        "branch": h["branch"], "base_commit": h["base_commit"], "patch_file": h["patch_file"],
    } for h in _wt_all_handoffs(phase)]
    print(json.dumps({"ok": True, "version": phase["version"], "worktrees": rows},
                     ensure_ascii=False, indent=2))


def wt(args: list[str]):
    """wt <create|capture|apply|clean|list> <N> [组名...] [--preserve=g1,g2]"""
    if len(args) < 2:
        _fail("用法: xz-tools.py wt <create|capture|apply|clean|list> <N> [组名...]")
    action, n = args[0], args[1]
    rest = [a for a in args[2:] if not a.startswith("--")]
    flags = [a for a in args[2:] if a.startswith("--")]
    if action == "create":
        wt_create(n, rest)
    elif action == "capture":
        if len(rest) != 1:
            _fail("用法: wt capture <N> <组名>")
        wt_capture(n, rest[0])
    elif action == "apply":
        preserve = []
        for f in flags:
            if f.startswith("--preserve="):
                preserve = [g for g in f.split("=", 1)[1].split(",") if g]
        wt_apply(n, rest or None, preserve)
    elif action == "clean":
        wt_clean(n, rest or None)
    elif action == "list":
        wt_list(n)
    else:
        _fail(f"未知 wt 动作: {action}（只有 create/capture/apply/clean/list）")


def _get_plugin_root() -> Path:
    """通过脚本自身位置推算插件根目录（bin/ 的上级）。"""
    return Path(__file__).resolve().parent.parent


def plugin_root():
    """输出插件根目录路径。"""
    root = _get_plugin_root()
    print(json.dumps({"ok": True, "plugin_root": str(root)}, ensure_ascii=False))


def skill_dir(skill_name: str):
    """输出指定 skill 的目录路径。"""
    root = _get_plugin_root()
    sd = root / "skills" / skill_name
    if not sd.exists():
        print(json.dumps({"ok": False, "error": f"skill '{skill_name}' 不存在: {sd}"}, ensure_ascii=False))
        return
    print(json.dumps({"ok": True, "skill_dir": str(sd)}, ensure_ascii=False))


def skill_path(skill_name: str):
    """输出指定 skill 的目录绝对路径（纯文本，适合 shell 直接使用）。不存在则退出码非零。"""
    root = _get_plugin_root()
    sd = root / "skills" / skill_name
    if not sd.exists():
        sys.stderr.write(f"skill '{skill_name}' 不存在: {sd}\n")
        sys.exit(1)
    print(str(sd))


def get_readme():
    """输出 README 模板内容到 stdout。"""
    root = _get_plugin_root()
    readme = root / "resources" / "README-template.md"
    if not readme.exists():
        print(json.dumps({"ok": False, "error": f"README 模板不存在: {readme}"}, ensure_ascii=False))
        return
    sys.stdout.write(readme.read_text(encoding="utf-8"))


def main():
    if len(sys.argv) < 2:
        print("用法: xz-tools.py <command> [args]")
        print("命令: init, status, parse <N>, list-phases, complete <N|all>, delete <N>, update-state,")
        print("      remove-all, plugin-root, skill-dir <name>, skill-path <name>, get-readme,")
        print("      wt <create|capture|apply|clean|list> <N> [组名...]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "init":
        init()
    elif cmd == "status":
        status()
    elif cmd == "parse" and len(sys.argv) >= 3:
        include_archive = "--include-archive" in sys.argv
        parse_plan(sys.argv[2], include_archive=include_archive)
    elif cmd == "list-phases":
        list_phases()
    elif cmd == "complete" and len(sys.argv) >= 3:
        complete(sys.argv[2])
    elif cmd == "delete" and len(sys.argv) >= 3:
        delete(sys.argv[2])
    elif cmd == "update-state":
        update_state()
    elif cmd == "remove-all":
        remove_all()
    elif cmd == "plugin-root":
        plugin_root()
    elif cmd == "skill-dir" and len(sys.argv) >= 3:
        skill_dir(sys.argv[2])
    elif cmd == "skill-path" and len(sys.argv) >= 3:
        skill_path(sys.argv[2])
    elif cmd == "get-readme":
        get_readme()
    elif cmd == "wt" and len(sys.argv) >= 3:
        # skill 靠 ok 字段判走向，所以任何异常都要变成 {"ok": false, ...} 而不是 traceback
        try:
            wt(sys.argv[2:])
        except SystemExit:
            raise
        except Exception as e:
            _fail(f"wt 命令异常: {type(e).__name__}: {e}")
    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
