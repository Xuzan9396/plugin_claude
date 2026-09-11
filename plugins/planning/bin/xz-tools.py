#!/usr/bin/env python3
"""XZ Planning - 辅助脚本，处理文件操作、状态解析、交互式菜单。"""

import json
import os
import re
import shutil
import sys
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
        print("      remove-all, plugin-root, skill-dir <name>, skill-path <name>, get-readme")
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
    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
