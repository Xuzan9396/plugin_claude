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


def _sort_by_version(path: Path):
    """按目录名前缀数字排序：'10.xxx' 排在 '2.xxx' 之后。非数字前缀退化为 inf + 字符串。"""
    m = re.match(r"^(\d+)\.", path.name)
    return (int(m.group(1)) if m else float("inf"), path.name)


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


def find_phase(n: str, include_archive: bool = False) -> dict | None:
    """查找版本 N 对应的 phases 目录。include_archive=True 时也查 archive。"""
    if not PHASES_DIR.exists():
        return None
    # 先找活跃版本
    for d in PHASES_DIR.iterdir():
        if d.is_dir() and d.name != "archive" and d.name.startswith(f"{n}."):
            plan_file = d / f"{n}-PLAN.md"
            discuss_file = d / f"{n}-DISCUSS.md"
            return {
                "dir": str(d),
                "dir_name": d.name,
                "plan_file": str(plan_file),
                "plan_exists": plan_file.exists(),
                "discuss_file": str(discuss_file),
                "discuss_exists": discuss_file.exists(),
                "archived": False,
            }
    # 再找归档版本
    if include_archive and ARCHIVE_DIR.exists():
        for d in ARCHIVE_DIR.iterdir():
            if d.is_dir() and d.name.startswith(f"{n}."):
                plan_file = d / f"{n}-PLAN.md"
                discuss_file = d / f"{n}-DISCUSS.md"
                return {
                    "dir": str(d),
                    "dir_name": d.name,
                    "plan_file": str(plan_file),
                    "plan_exists": plan_file.exists(),
                    "discuss_file": str(discuss_file),
                    "discuss_exists": discuss_file.exists(),
                    "archived": True,
                }
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
            match = re.match(r"^(\d+)\.(.+)$", d.name)
            if not match:
                continue
            n = match.group(1)
            name = match.group(2)
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
            match = re.match(r"^(\d+)\.(.+)$", d.name)
            if match:
                archived.append({"version": match.group(1), "name": match.group(2)})

    print(
        json.dumps(
            {"ok": True, "active": active, "archived": archived, "initialized": True},
            ensure_ascii=False,
        )
    )


def complete(n: str):
    """将版本 N 移入 archive，更新 STATE.md。"""
    phase = find_phase(n)
    if not phase:
        print(json.dumps({"ok": False, "error": f"版本 {n} 不存在"}))
        return

    src = Path(phase["dir"])
    dst = ARCHIVE_DIR / src.name
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    if dst.exists():
        shutil.rmtree(dst)
    shutil.move(str(src), str(dst))

    _update_state()
    print(
        json.dumps(
            {"ok": True, "moved": f"{src.name} -> archive/{src.name}"},
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
            match = re.match(r"^(\d+)\.(.+)$", d.name)
            if not match:
                continue
            n, name = match.group(1), match.group(2)
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
            match = re.match(r"^(\d+)\.(.+)$", d.name)
            if match:
                n, name = match.group(1), match.group(2)
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
        print("命令: init, status, parse <N>, complete <N>, delete <N>, update-state, remove-all,")
        print("      plugin-root, skill-dir <name>, skill-path <name>, get-readme")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "init":
        init()
    elif cmd == "status":
        status()
    elif cmd == "parse" and len(sys.argv) >= 3:
        include_archive = "--include-archive" in sys.argv
        parse_plan(sys.argv[2], include_archive=include_archive)
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
