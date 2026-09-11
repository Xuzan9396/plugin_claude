#!/usr/bin/env python3
"""XZ Planning - 辅助脚本，处理文件操作、状态解析、交互式菜单。"""

import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# 项目根目录：始终使用当前工作目录，不依赖脚本位置
PROJECT_ROOT = Path.cwd()
PLANNING_DIR = PROJECT_ROOT / ".xz_planning"
PHASES_DIR = PLANNING_DIR / "phases"
ARCHIVE_DIR = PLANNING_DIR / "archive"
STATE_FILE = PLANNING_DIR / "STATE.md"

# worktree 配置：项目本地、不入库（.xz_planning/ 通常被 gitignore）
WORKTREE_DIR = PLANNING_DIR / "worktree"
WT_CONFIG_FILE = WORKTREE_DIR / "setting.json"
WT_LOCK_DIR = WORKTREE_DIR / "merge.lock"


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


# ================================================================ worktree
#
# 配置在 .xz_planning/worktree/setting.json（项目本地，不入库）。
# 所有 wt-* 子命令统一输出一行 JSON。脚本只做明确安全的 git 操作，
# 需要人拿主意的（主仓库脏了要不要继续、要不要强制删）一律拒绝执行并
# 把原因吐出来，决策留给上层 skill。

WT_DEFAULT_CONFIG = {
    "version": 1,
    "baseBranch": "main",
    "branchPrefix": "xz/",
    "worktreeParent": "../.xz_worktrees",
    "mergeStrategy": "rebase-ff",
    "cleanupAfterMerge": True,
    "replicate": [],
    "postCreate": [],
}

# worktree 名：字母数字开头，1~40 位，只许字母数字和 . _ -
_WT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,39}$")


def _wt_out(ok: bool, **fields):
    """统一的单行 JSON 输出。"""
    print(json.dumps({"ok": ok, **fields}, ensure_ascii=False))


def _git_env():
    """禁掉凭据交互，避免 git 卡在等待输入。"""
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_OPTIONAL_LOCKS"] = "0"
    return env


def _git(args, cwd=None, timeout=120):
    """跑一条 git 命令，返回 (returncode, stdout, stderr)，不抛异常。"""
    try:
        p = subprocess.run(
            ["git", *args],
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            env=_git_env(),
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return 124, "", f"git {' '.join(args)} 超时（{timeout}s）"
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def _git_ok(args, cwd=None):
    """跑 git 只取 stdout，失败返回空串。"""
    code, out, _ = _git(args, cwd)
    return out if code == 0 else ""


def _repo_root():
    """当前目录所属仓库根；不在仓库里返回 None。"""
    code, out, _ = _git(["rev-parse", "--show-toplevel"])
    return Path(out) if code == 0 and out else None


def _wt_load_config():
    """读 setting.json，缺字段用默认值补齐；文件不存在返回 None，格式错抛 ValueError。"""
    if not WT_CONFIG_FILE.exists():
        return None
    try:
        cfg = json.loads(WT_CONFIG_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"setting.json 不是合法 JSON: {e}")
    if not isinstance(cfg, dict):
        raise ValueError("setting.json 顶层必须是对象")
    return {**WT_DEFAULT_CONFIG, **cfg}


def _wt_validate(cfg: dict) -> list:
    """校验配置，返回错误列表（空即合法）。"""
    errs = []
    for key in ("baseBranch", "branchPrefix", "worktreeParent", "mergeStrategy"):
        v = cfg.get(key)
        if not isinstance(v, str) or not v.strip():
            errs.append(f"{key} 必须是非空字符串")
    if cfg.get("mergeStrategy") not in ("rebase-ff", "merge-commit"):
        errs.append("mergeStrategy 只能是 rebase-ff 或 merge-commit")
    if not isinstance(cfg.get("cleanupAfterMerge"), bool):
        errs.append("cleanupAfterMerge 必须是布尔值")

    rep = cfg.get("replicate")
    if not isinstance(rep, list):
        errs.append("replicate 必须是数组")
    else:
        for i, item in enumerate(rep):
            if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not item["path"].strip():
                errs.append(f"replicate[{i}] 缺少非空的 path")
                continue
            if item.get("mode", "copy") not in ("copy", "link"):
                errs.append(f"replicate[{i}].mode 只能是 copy 或 link")
            p = item["path"].strip()
            if p.startswith("/") or ".." in Path(p).parts:
                errs.append(f"replicate[{i}].path 必须是仓库内的相对路径: {p}")

    post = cfg.get("postCreate")
    if not isinstance(post, list) or any(not isinstance(c, str) for c in post):
        errs.append("postCreate 必须是字符串数组")
    return errs


def _wt_parent_dir(cfg: dict, repo_root: Path) -> Path:
    """worktree 存放目录：相对 repo root 解析，支持 ~。"""
    p = Path(os.path.expanduser(cfg["worktreeParent"]))
    return p if p.is_absolute() else Path(os.path.normpath(repo_root / p))


def _wt_target(cfg: dict, repo_root: Path, name: str):
    """返回 (worktree 路径, 分支名)。"""
    path = _wt_parent_dir(cfg, repo_root) / f"{repo_root.name}-{name}"
    return path, f"{cfg['branchPrefix']}{name}"


def _wt_entries(repo_root: Path):
    """解析 git worktree list --porcelain -> [{path, head, branch}]。主仓库也在其中。"""
    entries, cur = [], {}
    for line in _git_ok(["worktree", "list", "--porcelain"], repo_root).splitlines():
        if not line.strip():
            if cur:
                entries.append(cur)
                cur = {}
            continue
        key, _, val = line.partition(" ")
        if key == "worktree":
            cur = {"path": val, "head": "", "branch": ""}
        elif key == "HEAD":
            cur["head"] = val
        elif key == "branch":
            cur["branch"] = val.replace("refs/heads/", "", 1)
        elif key == "detached":
            cur["branch"] = ""
    if cur:
        entries.append(cur)
    return entries


def _wt_find(repo_root: Path, branch: str):
    """按分支名找 worktree 条目，找不到返回 None。"""
    for e in _wt_entries(repo_root):
        if e["branch"] == branch:
            return e
    return None


def _porcelain_path(line: str) -> str:
    """从 porcelain 行取路径：'?? node_modules' -> 'node_modules'；
    重命名行 'R  a -> b' 取目标路径。"""
    rel = line[3:].strip()
    if " -> " in rel:
        rel = rel.split(" -> ", 1)[1]
    return rel.strip('"').rstrip("/")


def _wt_dirty(path, cfg: dict | None = None):
    """工作区改动清单（含未跟踪文件）。
    给了 cfg 就排除复刻条目——那是本工具自己放进去的，不是用户的工作成果。
    尤其 link 模式：symlink 不匹配 .gitignore 里带斜杠的目录模式（如
    `node_modules/`），不排除的话新建的 worktree 一出生就是脏的。"""
    out = _git_ok(["status", "--porcelain", "--untracked-files=all"], path)
    lines = [ln for ln in out.splitlines() if ln.strip()]
    if not cfg:
        return lines
    skip = {item["path"].strip().strip("/") for item in cfg.get("replicate", [])}
    return [
        ln
        for ln in lines
        if (rel := _porcelain_path(ln)) not in skip
        and not any(rel.startswith(f"{s}/") for s in skip)
    ]


def _wt_split_dirty(lines):
    """拆成 (已跟踪的改动, 未跟踪文件)。未跟踪文件不进任何提交，
    不影响合并正确性，只在删除 worktree 时才会真丢东西。"""
    return (
        [ln for ln in lines if not ln.startswith("??")],
        [ln for ln in lines if ln.startswith("??")],
    )


def _wt_count(repo_root: Path, rng: str) -> int:
    """rev-list --count，解析失败返回 0。"""
    out = _git_ok(["rev-list", "--count", rng], repo_root)
    return int(out) if out.isdigit() else 0


def _wt_branch_exists(repo_root: Path, branch: str) -> bool:
    code, _, _ = _git(["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], repo_root)
    return code == 0


def _wt_replicate(cfg: dict, repo_root: Path, dest: Path):
    """把配置里的忽略项复刻进新 worktree，返回 (done, skipped, errors)。"""
    done, skipped, errors = [], [], []
    for item in cfg.get("replicate", []):
        rel = item["path"].strip().strip("/")
        mode = item.get("mode", "copy")
        src, dst = repo_root / rel, dest / rel
        if not src.exists() and not src.is_symlink():
            skipped.append({"path": rel, "reason": "源不存在"})
            continue
        if dst.exists() or dst.is_symlink():
            skipped.append({"path": rel, "reason": "目标已存在"})
            continue
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            if mode == "link":
                dst.symlink_to(src.resolve())
            elif src.is_dir():
                shutil.copytree(src, dst, symlinks=True)
            else:
                shutil.copy2(src, dst)
            done.append({"path": rel, "mode": mode})
        except OSError as e:
            errors.append({"path": rel, "mode": mode, "error": str(e)})
    return done, skipped, errors


def _wt_post_create(cfg: dict, dest: Path):
    """在新 worktree 内依次执行 postCreate 命令，任一失败即停。"""
    results = []
    for cmd in cfg.get("postCreate", []):
        try:
            p = subprocess.run(
                cmd, shell=True, cwd=str(dest), capture_output=True, text=True, timeout=900
            )
            tail = (p.stdout + p.stderr).strip().splitlines()[-20:]
            results.append({"cmd": cmd, "code": p.returncode, "output": "\n".join(tail)})
            if p.returncode != 0:
                break
        except subprocess.TimeoutExpired:
            results.append({"cmd": cmd, "code": 124, "output": "执行超时（900s）"})
            break
    return results


def _wt_cleanup(repo_root: Path, path: Path, branch: str, force: bool):
    """移除 worktree 目录并删分支，返回错误列表。非 force 时用 branch -d，
    未合并的分支删不掉——这正是要的保护。"""
    errors = []
    if path.exists():
        args = ["worktree", "remove", *(["--force"] if force else []), str(path)]
        code, _, err = _git(args, repo_root)
        if code != 0:
            errors.append(f"worktree remove: {err}")
    _git(["worktree", "prune"], repo_root)
    if _wt_branch_exists(repo_root, branch):
        code, _, err = _git(["branch", "-D" if force else "-d", branch], repo_root)
        if code != 0:
            errors.append(f"branch delete: {err}")
    return errors


class _MergeLock:
    """merge.lock 目录锁。mkdir 是原子操作，防多个 worktree 同时合并互相踩。"""

    def __init__(self, timeout=120):
        self.timeout = timeout
        self.held = False

    def __enter__(self):
        WORKTREE_DIR.mkdir(parents=True, exist_ok=True)
        deadline = time.time() + self.timeout
        while True:
            try:
                WT_LOCK_DIR.mkdir()
                self.held = True
                return self
            except FileExistsError:
                if time.time() >= deadline:
                    raise TimeoutError(
                        f"等待合并锁超时（{self.timeout}s）。若确认没有其他合并在跑，"
                        f"手工删除 {WT_LOCK_DIR} 后重试"
                    )
                time.sleep(1)

    def __exit__(self, *exc):
        if self.held:
            try:
                WT_LOCK_DIR.rmdir()
            except OSError:
                pass
        return False


# 复刻方式的自动判断表。
#
# 判据不是「大不大、能不能重建」，而是 **两个工作区共用同一份会不会出事**：
#   link —— 内容由锁文件确定、构建时只读，共用无害，省时省空间
#   copy —— 各自需要独立一份，共用会互相干扰
#   skip —— 压根不该复刻：构建产物共用必然互相覆盖，虚拟环境内含绝对路径搬过去也是坏的
#
# 早期版本把「大 + 可重建」当成 link 的判据，于是把 dist/target 也建议成软链——
# 那会让两个工作区的编译产物互相覆盖。这张表就是纠正它的。
_WT_HINT_DIRS = {
    # 依赖目录：内容由锁文件决定，构建时只读，软链最划算
    "node_modules": ("link", True, "依赖树由 lock 文件决定、构建时只读，软链省下几百 MB 和一次安装。"
                                   "注意两边共用同一份：若这两个分支的 package.json 不同，"
                                   "在工作区里 install 会改到主仓库那份——那种情况改用 copy，"
                                   "或删掉本条、改在 postCreate 里 install"),
    "vendor": ("link", True, "第三方依赖（Composer / Go vendor），内容由锁文件确定，构建时只读"),
    "bower_components": ("link", True, "前端依赖，可由锁文件重建，构建时只读"),
    "Pods": ("link", True, "CocoaPods 依赖，由 Podfile.lock 确定，构建时只读"),
    ".terraform": ("link", True, "provider 插件二进制，体积大且只读"),

    # 构建产物：两个工作区共用必然互相覆盖，并行构建直接打架
    "dist": ("skip", False, "构建产物，共用会互相覆盖；要的话在 postCreate 里重新构建"),
    "build": ("skip", False, "构建产物，共用会互相覆盖"),
    "out": ("skip", False, "构建产物，共用会互相覆盖"),
    "target": ("skip", False, "Rust/Java 构建产物，共用会让两边的编译互相打架"),
    ".next": ("skip", False, "Next.js 构建缓存，共用会互相覆盖"),
    ".nuxt": ("skip", False, "Nuxt 构建缓存，共用会互相覆盖"),
    ".svelte-kit": ("skip", False, "SvelteKit 构建缓存，共用会互相覆盖"),
    ".output": ("skip", False, "构建产物，共用会互相覆盖"),
    ".turbo": ("skip", False, "Turborepo 缓存，共用会互相覆盖"),
    ".vite": ("skip", False, "Vite 缓存，共用会互相覆盖"),
    ".parcel-cache": ("skip", False, "Parcel 缓存，共用会互相覆盖"),
    "coverage": ("skip", False, "覆盖率报告，每次跑测试都会重写"),
    "htmlcov": ("skip", False, "覆盖率报告，每次跑测试都会重写"),

    # 虚拟环境：内部脚本硬编码了绝对路径，复制或软链过去都指回原处
    "venv": ("skip", False, "虚拟环境内的脚本硬编码了绝对路径，搬过去会指回原目录；"
                            "在 postCreate 里重建更可靠"),
    ".venv": ("skip", False, "同 venv：内含绝对路径，搬过去是坏的，应在 postCreate 里重建"),
    "virtualenv": ("skip", False, "同 venv：内含绝对路径，应在 postCreate 里重建"),

    # 缓存与垃圾：重建代价极低，没必要带
    "__pycache__": ("skip", False, "字节码缓存，自动重建"),
    ".pytest_cache": ("skip", False, "测试缓存，自动重建"),
    ".mypy_cache": ("skip", False, "类型检查缓存，自动重建"),
    ".ruff_cache": ("skip", False, "lint 缓存，自动重建"),
    ".cache": ("skip", False, "缓存目录，自动重建"),
    ".gradle": ("skip", False, "Gradle 本地缓存，自动重建"),
    "tmp": ("skip", False, "临时目录"),
    ".tmp": ("skip", False, "临时目录"),
    "logs": ("skip", False, "日志目录，工作区该有自己的"),

    # 本地配置：各自一份，互不干扰
    ".xz_planning": ("copy", True, "本地计划数据。不带上它，新工作区里整套计划流程都用不了"),
    ".claude": ("copy", True, "本地 agent 配置，各自一份互不干扰"),
    ".vscode": ("copy", False, "编辑器配置，各自一份"),
    ".idea": ("copy", False, "编辑器配置，各自一份"),
}

# 文件后缀 → 建议。数据库文件各自独立，否则两个工作区会写同一份数据
_WT_HINT_SUFFIXES = {
    ".db": ("copy", False, "数据库文件，共用的话两个工作区会写同一份数据"),
    ".sqlite": ("copy", False, "数据库文件，共用的话两个工作区会写同一份数据"),
    ".sqlite3": ("copy", False, "数据库文件，共用的话两个工作区会写同一份数据"),
    ".log": ("skip", False, "日志文件"),
}


def _wt_suggest(name: str, is_dir: bool):
    """给一个被忽略的条目判断复刻方式，返回 (mode, recommended, reason)。"""
    if is_dir:
        hit = _WT_HINT_DIRS.get(name)
        if hit:
            return hit
        return ("copy", False, "未知目录，默认各自独立一份更安全；确认它是只读依赖再改 link")

    if name == ".env" or name.startswith(".env."):
        return ("copy", True, "本地环境变量，工作区要自己一份；软链的话改一边等于改两边")
    if name in (".envrc", ".tool-versions", ".nvmrc"):
        return ("copy", True, "本地环境配置，各自一份")
    hit = _WT_HINT_SUFFIXES.get(Path(name).suffix)
    if hit:
        return hit
    return ("copy", False, "未知文件，默认各自独立一份")


def _wt_size_kb(path: Path):
    """条目体积（KB）。du 在几万文件的目录上会很慢，2 秒拿不到就放弃——
    体积只是给用户看的参考，不值得卡住整个探测。"""
    try:
        p = subprocess.run(
            ["du", "-sk", str(path)], capture_output=True, text=True, timeout=2
        )
        if p.returncode == 0:
            return int(p.stdout.split()[0])
    except (subprocess.TimeoutExpired, ValueError, IndexError, OSError):
        pass
    return None


def _wt_prelude():
    """wt 子命令的共同前置：定位仓库 + 读校验配置。失败时已打印错误并返回 None。"""
    root = _repo_root()
    if root is None:
        _wt_out(False, error="当前目录不在 git 仓库里")
        return None
    try:
        cfg = _wt_load_config()
    except ValueError as e:
        _wt_out(False, error=str(e))
        return None
    if cfg is None:
        _wt_out(False, error=f"未找到 {WT_CONFIG_FILE}，请先初始化 worktree 配置")
        return None
    errs = _wt_validate(cfg)
    if errs:
        _wt_out(False, error="setting.json 不合规", details=errs)
        return None
    return root, cfg


def wt_scan():
    """探测仓库现状，供初始化生成默认值和候选清单。只读，不改任何东西。"""
    root = _repo_root()
    if root is None:
        _wt_out(False, error="当前目录不在 git 仓库里")
        return

    # 顶层被忽略且实际存在的条目。--directory 让 node_modules/ 整体算一条，
    # 不会展开成几万个文件
    ignored = []
    out = _git_ok(
        ["ls-files", "--others", "--ignored", "--exclude-standard", "--directory"], root
    )
    for rel in out.splitlines():
        rel = rel.strip().rstrip("/")
        if not rel or "/" in rel:  # 只收顶层
            continue
        is_dir = (root / rel).is_dir()
        mode, recommended, reason = _wt_suggest(rel, is_dir)
        ignored.append(
            {
                "path": rel,
                "type": "dir" if is_dir else "file",
                "size_kb": _wt_size_kb(root / rel),
                "suggested_mode": mode,
                "recommended": recommended,
                "reason": reason,
            }
        )

    planning_ignored, _, _ = _git(["check-ignore", "-q", ".xz_planning"], root)
    cfg, cfg_error = None, None
    try:
        cfg = _wt_load_config()
    except ValueError as e:
        cfg_error = str(e)

    _wt_out(
        True,
        repo_root=str(root),
        branch=_git_ok(["branch", "--show-current"], root),
        head=_git_ok(["rev-parse", "--short", "HEAD"], root),
        dirty=_wt_dirty(root),
        ignored_candidates=sorted(ignored, key=lambda x: x["path"]),
        planning_ignored=(planning_ignored == 0),
        exclude_file=_git_ok(["rev-parse", "--git-path", "info/exclude"], root),
        config_path=str(WT_CONFIG_FILE),
        config_exists=WT_CONFIG_FILE.exists(),
        config=cfg,
        config_error=cfg_error,
        defaults=WT_DEFAULT_CONFIG,
    )


def wt_config_read():
    """输出当前 worktree 配置。"""
    try:
        cfg = _wt_load_config()
    except ValueError as e:
        _wt_out(False, error=str(e))
        return
    if cfg is None:
        _wt_out(False, error=f"未找到 {WT_CONFIG_FILE}", config_path=str(WT_CONFIG_FILE))
        return
    _wt_out(True, config_path=str(WT_CONFIG_FILE), config=cfg)


def wt_config_write():
    """从 stdin 读整份 JSON 配置，校验后覆盖写入（合并旧值是调用方的事）。"""
    try:
        cfg = json.loads(sys.stdin.read())
    except json.JSONDecodeError as e:
        _wt_out(False, error=f"stdin 不是合法 JSON: {e}")
        return
    if not isinstance(cfg, dict):
        _wt_out(False, error="配置顶层必须是对象")
        return
    merged = {**WT_DEFAULT_CONFIG, **cfg}
    merged["version"] = 1
    errs = _wt_validate(merged)
    if errs:
        _wt_out(False, error="配置不合规", details=errs)
        return
    WORKTREE_DIR.mkdir(parents=True, exist_ok=True)
    WT_CONFIG_FILE.write_text(
        json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    _wt_out(True, config_path=str(WT_CONFIG_FILE), config=merged)


def wt_create(name: str, base: str | None = None):
    """创建 worktree、复刻忽略项、跑 postCreate。
    刻意不检查主仓库是否干净——那是 skill 层要跟用户确认的事。"""
    got = _wt_prelude()
    if not got:
        return
    root, cfg = got
    if not _WT_NAME_RE.match(name):
        _wt_out(False, error="名称须以字母或数字开头，1~40 位，只许字母数字和 . _ -")
        return

    path, branch = _wt_target(cfg, root, name)
    base = base or cfg["baseBranch"]
    code, base_sha, _ = _git(["rev-parse", "--verify", f"{base}^{{commit}}"], root)
    if code != 0:
        _wt_out(False, error=f"base 不存在或不是提交: {base}")
        return
    if _wt_branch_exists(root, branch):
        _wt_out(False, error=f"分支已存在: {branch}")
        return
    if path.exists():
        _wt_out(False, error=f"目标路径已存在: {path}")
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    code, _, err = _git(["worktree", "add", "-b", branch, str(path), base_sha], root)
    if code != 0:
        # 回滚残留，别留下半个 worktree
        if path.exists():
            _git(["worktree", "remove", "--force", str(path)], root)
        if _wt_branch_exists(root, branch):
            _git(["branch", "-D", branch], root)
        _git(["worktree", "prune"], root)
        _wt_out(False, error=f"git worktree add 失败: {err}")
        return

    done, skipped, rep_errors = _wt_replicate(cfg, root, path)
    post = _wt_post_create(cfg, path)
    _wt_out(
        True,
        name=name,
        path=str(path),
        branch=branch,
        base=base,
        base_commit=base_sha[:8],
        replicated=done,
        skipped=skipped,
        replicate_errors=rep_errors,
        post_create=post,
    )


def wt_list():
    """列出仓库全部 worktree，标出哪些由本插件管理。"""
    got = _wt_prelude()
    if not got:
        return
    root, cfg = got
    prefix, base = cfg["branchPrefix"], cfg["baseBranch"]
    base_exists = _wt_branch_exists(root, base)

    items = []
    for e in _wt_entries(root):
        p = Path(e["path"])
        managed = bool(e["branch"]) and e["branch"].startswith(prefix)
        tracked, untracked = _wt_split_dirty(_wt_dirty(p, cfg) if p.exists() else [])
        item = {
            "path": e["path"],
            "branch": e["branch"],
            "is_main": p == root,
            "managed": managed,
            "name": e["branch"][len(prefix):] if managed else "",
            "exists": p.exists(),
            "dirty": len(tracked),
            "untracked": len(untracked),
            "ahead": 0,
            "behind": 0,
        }
        if e["branch"] and base_exists and e["branch"] != base:
            item["ahead"] = _wt_count(root, f"{base}..{e['branch']}")
            item["behind"] = _wt_count(root, f"{e['branch']}..{base}")
        items.append(item)

    _wt_out(True, repo_root=str(root), base_branch=base, count=len(items), worktrees=items)


def _wt_require(root: Path, cfg: dict, name: str):
    """定位受管 worktree，返回 (path, branch)；找不到打印错误并返回 None。"""
    path, branch = _wt_target(cfg, root, name)
    entry = _wt_find(root, branch)
    if entry is None:
        _wt_out(False, error=f"没有找到分支为 {branch} 的 worktree", expected_path=str(path))
        return None
    return Path(entry["path"]), branch


def wt_status(name: str):
    """单个 worktree 的详情与合并预检。只读。"""
    got = _wt_prelude()
    if not got:
        return
    root, cfg = got
    found = _wt_require(root, cfg, name)
    if not found:
        return
    path, branch = found
    base = cfg["baseBranch"]

    dirty, untracked = _wt_split_dirty(_wt_dirty(path, cfg) if path.exists() else [])
    main_dirty, _ = _wt_split_dirty(_wt_dirty(root, cfg))
    blockers = []
    if not path.exists():
        blockers.append(f"worktree 目录不存在: {path}")
    if dirty:
        blockers.append(f"worktree 有 {len(dirty)} 处未提交改动")
    if main_dirty:
        blockers.append(f"主仓库有 {len(main_dirty)} 处未提交改动")
    if not _wt_branch_exists(root, base):
        blockers.append(f"base 分支不存在: {base}")

    _wt_out(
        True,
        name=name,
        path=str(path),
        branch=branch,
        base_branch=base,
        exists=path.exists(),
        dirty=dirty,
        untracked=untracked,
        main_dirty=main_dirty,
        ahead=_wt_count(root, f"{base}..{branch}"),
        behind=_wt_count(root, f"{branch}..{base}"),
        main_branch_now=_git_ok(["branch", "--show-current"], root),
        merge_strategy=cfg["mergeStrategy"],
        cleanup_after_merge=cfg["cleanupAfterMerge"],
        can_merge=not blockers,
        blockers=blockers,
    )


def wt_merge(name: str, keep: bool = False, no_ff: bool = False):
    """合并回 base：预检 → 加锁 → rebase/merge → 清理 → 恢复主仓库原分支。
    这是唯一会改动主仓库的子命令，任何一步失败都把主仓库还原。"""
    got = _wt_prelude()
    if not got:
        return
    root, cfg = got
    found = _wt_require(root, cfg, name)
    if not found:
        return
    path, branch = found
    base = cfg["baseBranch"]

    # ---- 预检：任一不过就退出，一个写操作都不做
    blockers = []
    untracked = []
    if not path.exists():
        blockers.append(f"worktree 目录不存在: {path}")
    else:
        wt_tracked, untracked = _wt_split_dirty(_wt_dirty(path, cfg))
        if wt_tracked:
            blockers.append(f"worktree 内有 {len(wt_tracked)} 处未提交改动，先提交或丢弃")
    main_tracked, _ = _wt_split_dirty(_wt_dirty(root, cfg))
    if main_tracked:
        blockers.append(f"主仓库有 {len(main_tracked)} 处未提交改动，先处理")
    if not _wt_branch_exists(root, base):
        blockers.append(f"base 分支不存在: {base}")
    if blockers:
        _wt_out(False, error="预检未通过，未做任何改动", blockers=blockers)
        return

    if _wt_count(root, f"{base}..{branch}") == 0:
        _wt_out(
            True,
            name=name,
            branch=branch,
            base_branch=base,
            merged=0,
            cleaned=False,
            note=f"{branch} 相对 {base} 没有新提交，无需合并",
        )
        return

    original = _git_ok(["branch", "--show-current"], root)
    strategy = "merge-commit" if no_ff else cfg["mergeStrategy"]
    steps, switched = [], False

    try:
        with _MergeLock():
            if strategy == "rebase-ff":
                code, out, err = _git(["rebase", base], path, timeout=600)
                steps.append({"step": f"rebase {base}", "code": code})
                if code != 0:
                    conflicts = _git_ok(
                        ["diff", "--name-only", "--diff-filter=U"], path
                    ).splitlines()
                    _wt_out(
                        False,
                        error="rebase 出现冲突，已停在冲突现场；主仓库未被改动",
                        conflicts=conflicts,
                        detail=(err or out),
                        hint=f"进 {path} 解决冲突后 `git rebase --continue`（放弃则 `git rebase --abort`），再重跑合并",
                        steps=steps,
                    )
                    return

            ahead = _wt_count(root, f"{base}..{branch}")

            if original != base:
                code, _, err = _git(["checkout", base], root)
                steps.append({"step": f"checkout {base}", "code": code})
                if code != 0:
                    _wt_out(False, error=f"主仓库切到 {base} 失败: {err}", steps=steps)
                    return
                switched = True

            if strategy == "rebase-ff":
                args = ["merge", "--ff-only", branch]
            else:
                args = ["merge", "--no-ff", "-m", f"Merge branch '{branch}' into {base}", branch]
            code, out, err = _git(args, root, timeout=600)
            steps.append({"step": " ".join(args), "code": code})
            if code != 0:
                # 主仓库是用户的主工作区，不留冲突现场
                _git(["merge", "--abort"], root)
                if switched:
                    _git(["checkout", original], root)
                _wt_out(
                    False,
                    error="合并失败，主仓库已回到合并前状态",
                    detail=(err or out),
                    hint=f"worktree 与分支都完好，可进 {path} 处理后重试",
                    steps=steps,
                )
                return

            # 清理要在主仓库还停在 base 上时做：branch -d 需要分支已合入当前 HEAD。
            # 有未跟踪文件就不自动删——它们进不了任何提交，删了就是真丢。
            cleaned, cleanup_errors, kept_reason = False, [], ""
            if keep:
                kept_reason = "指定了 --keep"
            elif not cfg["cleanupAfterMerge"]:
                kept_reason = "配置 cleanupAfterMerge 为 false"
            elif untracked:
                kept_reason = f"worktree 里有 {len(untracked)} 个未跟踪文件，删了会丢，已保留"
            else:
                cleanup_errors = _wt_cleanup(root, path, branch, force=False)
                cleaned = not cleanup_errors

            if switched:
                code, _, err = _git(["checkout", original], root)
                steps.append({"step": f"checkout {original}", "code": code})
                if code != 0:
                    cleanup_errors.append(f"切回 {original} 失败: {err}")

            _wt_out(
                True,
                name=name,
                branch=branch,
                base_branch=base,
                strategy=strategy,
                merged=ahead,
                cleaned=cleaned,
                kept_path=None if cleaned else str(path),
                kept_reason=kept_reason,
                untracked=untracked,
                restored_branch=original,
                cleanup_errors=cleanup_errors,
                steps=steps,
            )
    except TimeoutError as e:
        _wt_out(False, error=str(e))


def wt_remove(name: str, force: bool = False):
    """删除 worktree 与其分支。默认拒绝删有改动或未合并提交的。"""
    got = _wt_prelude()
    if not got:
        return
    root, cfg = got
    path, branch = _wt_target(cfg, root, name)
    entry = _wt_find(root, branch)
    if entry:
        path = Path(entry["path"])
    elif not path.exists() and not _wt_branch_exists(root, branch):
        _wt_out(False, error=f"没有找到分支为 {branch} 的 worktree", expected_path=str(path))
        return

    base = cfg["baseBranch"]
    if not force:
        blockers = []
        # 删除会真的丢东西，所以未跟踪文件在这里也算阻塞项
        dirty = _wt_dirty(path, cfg) if path.exists() else []
        tracked, untracked = _wt_split_dirty(dirty)
        if tracked:
            blockers.append(f"有 {len(tracked)} 处未提交改动")
        if untracked:
            blockers.append(f"有 {len(untracked)} 个未跟踪文件会被删掉")
        if _wt_branch_exists(root, branch) and _wt_branch_exists(root, base):
            ahead = _wt_count(root, f"{base}..{branch}")
            if ahead:
                blockers.append(f"有 {ahead} 个提交尚未合并到 {base}")
        if blockers:
            _wt_out(
                False,
                error="拒绝删除：有内容会丢失",
                blockers=blockers,
                dirty=dirty,
                path=str(path),
                branch=branch,
            )
            return

    errors = _wt_cleanup(root, path, branch, force=force)
    if errors:
        _wt_out(False, error="清理未完成", details=errors, path=str(path), branch=branch)
        return
    _wt_out(True, name=name, path=str(path), branch=branch, forced=force)


def main():
    if len(sys.argv) < 2:
        print("用法: xz-tools.py <command> [args]")
        print("命令: init, status, parse <N>, list-phases, complete <N|all>, delete <N>, update-state,")
        print("      remove-all, plugin-root, skill-dir <name>, skill-path <name>, get-readme")
        print("worktree: wt-scan, wt-config-read, wt-config-write(<stdin JSON>),")
        print("      wt-create <name> [--base <ref>], wt-list, wt-status <name>,")
        print("      wt-merge <name> [--keep] [--no-ff], wt-remove <name> [--force]")
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
    elif cmd == "wt-scan":
        wt_scan()
    elif cmd == "wt-config-read":
        wt_config_read()
    elif cmd == "wt-config-write":
        wt_config_write()
    elif cmd == "wt-create" and len(sys.argv) >= 3:
        base = None
        if "--base" in sys.argv:
            i = sys.argv.index("--base")
            if i + 1 < len(sys.argv):
                base = sys.argv[i + 1]
        wt_create(sys.argv[2], base)
    elif cmd == "wt-list":
        wt_list()
    elif cmd == "wt-status" and len(sys.argv) >= 3:
        wt_status(sys.argv[2])
    elif cmd == "wt-merge" and len(sys.argv) >= 3:
        wt_merge(sys.argv[2], keep="--keep" in sys.argv, no_ff="--no-ff" in sys.argv)
    elif cmd == "wt-remove" and len(sys.argv) >= 3:
        wt_remove(sys.argv[2], force="--force" in sys.argv)
    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
