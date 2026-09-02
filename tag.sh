#!/usr/bin/env bash
# 一键发版：语法闸门 → 改版本号 → commit/push → 装 codex → 装 pi
# 用法: ./tag.sh vX.Y.Z   或   ./tag.sh --check（只体检，不改任何东西）

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
MYAI_ROOT="$(cd "$REPO_ROOT/.." && pwd)"

CLAUDE_SKILLS="$REPO_ROOT/plugins/planning/skills"
CODEX_SKILLS="$MYAI_ROOT/skills/codex"
PI_SKILLS="$MYAI_ROOT/pi_skills"
INSTALL_SH="$MYAI_ROOT/skills/install.sh"
PLUGIN_TOOLS="$REPO_ROOT/plugins/planning/bin/xz-tools.py"
SKILLS_TOOLS="$MYAI_ROOT/skills/script/xz-tools.py"

marketplace="$REPO_ROOT/.claude-plugin/marketplace.json"
plugin_json="$REPO_ROOT/plugins/planning/.claude-plugin/plugin.json"

usage() {
  cat <<'EOF'
用法:
  ./tag.sh vX.Y.Z    闸门 → 改版本号 → commit/push → 装 codex → 装 pi
  ./tag.sh --check   只跑闸门体检，不改任何东西

示例: ./tag.sh v1.5.3
EOF
}

# ---------------------------------------------------------------- 闸门

fail=0
gate_err() { echo "  ❌ $1"; fail=1; }

check_dirs_match() {
  local a b c
  a=$(cd "$CLAUDE_SKILLS" && ls -d xz-* | sort)
  b=$(cd "$CODEX_SKILLS" && ls -d xz-* | sort)
  c=$(cd "$PI_SKILLS" && ls -d xz-* | sort)
  if [ "$a" != "$b" ]; then
    gate_err "claude 与 codex 的 skill 名单不一致:"
    diff <(echo "$a") <(echo "$b") | sed 's/^/       /'
  fi
  if [ "$a" != "$c" ]; then
    gate_err "claude 与 pi 的 skill 名单不一致:"
    diff <(echo "$a") <(echo "$c") | sed 's/^/       /'
  fi
  [ "$fail" -eq 0 ] && echo "  ✅ 三端 skill 名单一致（$(echo "$a" | wc -l | tr -d ' ') 个）"
}

# 在 $1 目录里搜 $2 正则，命中即算串味
check_no_pattern() {
  local dir="$1" pattern="$2" desc="$3" hits
  hits=$(grep -rnE "$pattern" "$dir" --include=SKILL.md 2>/dev/null | head -5 || true)
  if [ -n "$hits" ]; then
    gate_err "$desc"
    echo "$hits" | sed "s|$MYAI_ROOT/||; s/^/       /"
  fi
}

check_dialect() {
  # claude 端不许出现 codex / pi 的语法
  check_no_pattern "$CLAUDE_SKILLS" '\$xz-|/skill:|\$chrome|chrome@openai-bundled' \
    "claude 端混入了 codex/pi 语法"
  # codex 端不许出现 claude / pi 的语法
  check_no_pattern "$CODEX_SKILLS" '(^|[^[:alnum:].])/xz-|/skill:|AskUserQuestion|claude-in-chrome|mcp__' \
    "codex 端混入了 claude/pi 语法"
  # pi 端不许出现 claude / codex 的语法
  check_no_pattern "$PI_SKILLS" '(^|[^[:alnum:].])/xz-|\$xz-|\$ARGUMENTS|\$chrome|chrome@openai-bundled|AskUserQuestion|claude-in-chrome|mcp__' \
    "pi 端混入了 claude/codex 语法"

  # pi 端凡是用到参数占位符的，必须有参数约定说明块
  local missing=""
  for f in "$PI_SKILLS"/xz-*/SKILL.md; do
    if grep -q '<调用参数>\|<第一个参数>' "$f" && ! grep -q 'Pi 参数约定' "$f"; then
      missing="$missing $(basename "$(dirname "$f")")"
    fi
  done
  [ -n "$missing" ] && gate_err "pi 端缺少「Pi 参数约定」说明块:$missing"

  [ "$fail" -eq 0 ] && echo "  ✅ 三端语法各守各的，没有串味"
}

check_tools_script() {
  if [ ! -f "$SKILLS_TOOLS" ]; then
    gate_err "缺少 $SKILLS_TOOLS"
    return
  fi
  if ! diff -q "$PLUGIN_TOOLS" "$SKILLS_TOOLS" >/dev/null; then
    if [ "${CHECK_ONLY:-0}" -eq 1 ]; then
      gate_err "xz-tools.py 两份不一致（plugins/planning/bin ↔ skills/script）"
    else
      cp "$PLUGIN_TOOLS" "$SKILLS_TOOLS"
      echo "  🔄 xz-tools.py 已从插件 bin/ 同步到 skills/script/"
    fi
  else
    echo "  ✅ xz-tools.py 两份一致"
  fi
}

run_gate() {
  echo "[闸门] 三端一致性检查"
  for d in "$CLAUDE_SKILLS" "$CODEX_SKILLS" "$PI_SKILLS"; do
    [ -d "$d" ] || { echo "  ❌ 目录不存在: $d"; exit 1; }
  done
  check_dirs_match
  check_dialect
  check_tools_script
  if [ "$fail" -ne 0 ]; then
    echo ""
    echo "闸门未通过，已终止。修完再跑。" >&2
    exit 1
  fi
  echo ""
}

# ---------------------------------------------------------------- 主流程

if [ $# -ne 1 ]; then
  usage >&2
  exit 1
fi

if [ "$1" = "--check" ] || [ "$1" = "-c" ]; then
  CHECK_ONLY=1
  run_gate
  echo "体检通过。"
  exit 0
fi

tag="$1"
if [[ ! "$tag" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "版本号格式错误，应为 vX.Y.Z（例: v1.1.1）" >&2
  exit 1
fi
version="${tag#v}"

for f in "$marketplace" "$plugin_json"; do
  if [ ! -f "$f" ]; then
    echo "未找到 $f，请在插件仓库根目录执行" >&2
    exit 1
  fi
done

run_gate

python3 - "$marketplace" "$plugin_json" "$version" <<'PYEOF'
import json, sys
marketplace, plugin_json, version = sys.argv[1], sys.argv[2], sys.argv[3]

with open(marketplace) as f:
    data = json.load(f)
data["plugins"][0]["version"] = version
with open(marketplace, "w") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write("\n")

with open(plugin_json) as f:
    data = json.load(f)
data["version"] = version
with open(plugin_json, "w") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write("\n")
PYEOF

echo "[1/4] marketplace.json + plugin.json 已改为 $version"

cd "$REPO_ROOT"
git add -A
if git diff --cached --quiet; then
  echo "没有需要提交的改动，终止" >&2
  exit 1
fi
git commit -m "$version"
echo "[2/4] 已提交 commit"

git push
echo "[3/4] 已 push 到远端"

echo "[4/4] 安装到本机 codex / pi"
if [ -x "$INSTALL_SH" ]; then
  "$INSTALL_SH" --codex --yes | sed 's/^/  /'
  "$INSTALL_SH" --pi --yes | sed 's/^/  /'
else
  echo "  ⚠️  未找到可执行的 $INSTALL_SH，跳过本机安装" >&2
fi

echo ""
echo "完成: $tag —— claude 已推 GitHub，codex / pi 已装到本机"
