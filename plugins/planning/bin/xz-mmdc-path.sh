#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
用法:
  make-output-path.sh <序号> <中文描述...>

说明:
  根据 mmdc 参数生成默认输出路径：
  .xz_planning/mmdc-output/<序号>.<中文描述>/<序号>-mmdc.mmd
  .xz_planning/mmdc-output/<序号>.<中文描述>/<序号>-mmdc.svg
  .xz_planning/mmdc-output/<序号>.<中文描述>/<序号>-process.md

规则:
  - 序号必须是数字或点分数字，例如 1、2、1.1
  - 序号不能重复；如果 mmdc-output 中已存在该序号，会提示下一个可用序号
  - 目录名整体最多 30 个 Unicode 字符
  - 描述会清理文件名不安全字符，保留中文、英文和数字
USAGE
}

if [[ $# -lt 2 ]]; then
  usage
  exit 2
fi

seq="$1"
shift
desc="$*"

if [[ ! "$seq" =~ ^[0-9]+([.][0-9]+)*$ ]]; then
  echo "错误: 第一个参数必须是流程图序号，例如 1、2、1.1。当前值: $seq" >&2
  exit 2
fi

python3 - "$seq" "$desc" <<'PY'
import re
import sys
from pathlib import Path

seq = sys.argv[1]
desc = sys.argv[2]
base_dir = Path(".xz_planning/mmdc-output")

def infer_seq_from_dir_name(name: str) -> str:
    marker = re.match(r"^([0-9]+(?:\.[0-9]+)*)\.", name)
    return marker.group(1) if marker else ""

def collect_used_seqs(base: Path) -> set[str]:
    used = set()
    if not base.exists():
        return used
    for child in base.iterdir():
        if not child.is_dir():
            continue
        marker = child / ".mmdc-seq"
        if marker.exists():
            marked_seq = marker.read_text(encoding="utf-8").strip()
            if marked_seq:
                used.add(marked_seq)
                continue
        inferred_seq = infer_seq_from_dir_name(child.name)
        if inferred_seq:
            used.add(inferred_seq)
    return used

def next_seq(seq_value: str, used: set[str]) -> str:
    if "." not in seq_value:
        numeric_values = [int(item) for item in used if re.fullmatch(r"[0-9]+", item)]
        numeric_values.append(int(seq_value))
        return str(max(numeric_values) + 1)

    parts = seq_value.split(".")
    parent = ".".join(parts[:-1])
    current = int(parts[-1])
    sibling_values = []
    for item in used:
        if item.startswith(parent + "."):
            tail = item[len(parent) + 1:]
            if re.fullmatch(r"[0-9]+", tail):
                sibling_values.append(int(tail))
    sibling_values.append(current)
    return f"{parent}.{max(sibling_values) + 1}"

used_seqs = collect_used_seqs(base_dir)
if seq in used_seqs:
    suggestion = next_seq(seq, used_seqs)
    print(f"错误: 序号 {seq} 已存在，请使用下一个序号: {suggestion}", file=sys.stderr)
    sys.exit(3)

desc = desc.strip()
if not desc:
    desc = "流程图"

# 文件系统路径不能包含 / 和控制字符；其余标点尽量清理掉，避免命令行和浏览器打开时产生歧义。
desc = re.sub(r"[\x00-\x1f\x7f/\\:*?\"<>|`$!#&;()\[\]{}]", "", desc)
desc = re.sub(r"\s+", "", desc)
desc = desc.strip(".-_，。；;、 ")
if not desc:
    desc = "流程图"

prefix = f"{seq}."
max_chars = 30
room = max_chars - len(prefix)
if room < 1:
    print(f"错误: 序号过长，目录名无法控制在 {max_chars} 字内: {seq}", file=sys.stderr)
    sys.exit(2)

name = prefix + desc[:room]
name = name.rstrip(".-_，。；;、 ")
if name == seq:
    name = f"{seq}.流程图"

out_dir = base_dir / name
mmd = out_dir / f"{seq}-mmdc.mmd"
svg = out_dir / f"{seq}-mmdc.svg"
process = out_dir / f"{seq}-process.md"

out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / ".mmdc-seq").write_text(seq + "\n", encoding="utf-8")

print(f"dir={out_dir}")
print(f"mmd={mmd}")
print(f"svg={svg}")
print(f"process={process}")
PY
