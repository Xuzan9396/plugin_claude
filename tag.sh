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
  if [ "$fail" -eq 0 ]; then
    echo "  ✅ 三端 skill 名单一致（$(echo "$a" | wc -l | tr -d ' ') 个）"
  fi
}

# 扫描范围：不能只扫 SKILL.md —— 附属文件（agents/*.yaml、scripts/*.sh、
# examples/*.js）里的串味同样要拦，历史上就漏过一次
SCAN_INCLUDES=(--include='*.md' --include='*.yaml' --include='*.yml'
               --include='*.js' --include='*.sh' --include='*.toml')

# 在 $1 目录里搜 $2 正则，命中即算串味
check_no_pattern() {
  local dir="$1" pattern="$2" desc="$3" hits
  hits=$(grep -rnE "$pattern" "$dir" "${SCAN_INCLUDES[@]}" 2>/dev/null | head -5 || true)
  if [ -n "$hits" ]; then
    gate_err "$desc"
    echo "$hits" | sed "s|$MYAI_ROOT/||; s/^/       /"
  fi
}

check_dialect() {
  local fail_before="$fail"
  # claude 端不许出现 codex / pi 的语法
  check_no_pattern "$CLAUDE_SKILLS" '\$xz-|\$mmdc|/skill:|\$chrome|chrome@openai-bundled' \
    "claude 端混入了 codex/pi 语法"
  # codex 端不许出现 claude / pi 的语法
  check_no_pattern "$CODEX_SKILLS" '(^|[^[:alnum:].])/xz-|/skill:|AskUserQuestion|claude-in-chrome|mcp__' \
    "codex 端混入了 claude/pi 语法"
  # pi 端不许出现 claude / codex 的语法
  check_no_pattern "$PI_SKILLS" '(^|[^[:alnum:].])/xz-|\$xz-|\$mmdc|\$ARGUMENTS|\$chrome|chrome@openai-bundled|AskUserQuestion|claude-in-chrome|mcp__' \
    "pi 端混入了 claude/codex 语法"

  # pi 端凡是用到参数占位符的，必须有参数约定说明块
  local missing=""
  for f in "$PI_SKILLS"/xz-*/SKILL.md; do
    if grep -q '<调用参数>\|<第一个参数>' "$f" && ! grep -q 'Pi 参数约定' "$f"; then
      missing="$missing $(basename "$(dirname "$f")")"
    fi
  done
  if [ -n "$missing" ]; then
    gate_err "pi 端缺少「Pi 参数约定」说明块:$missing"
  fi

  if [ "$fail" -eq "$fail_before" ]; then
    echo "  ✅ 三端语法各守各的，没有串味"
  fi
}

# frontmatter 字段白名单 + Agent Skills spec 硬约束
#
# 白名单按「各端实测真解析的字段」定，不放宽到 spec 全集：多写的键不会报错、
# 会被静默忽略，等于埋一个假功能。依据见 CLAUDE.md 的「skill 定义硬约束」。
# 用 python 而非 grep：正文里的 `version:`、`go:` 会被裸 grep 误判成字段。
check_frontmatter() {
  local out
  out=$(python3 - "$CLAUDE_SKILLS" "$CODEX_SKILLS" "$PI_SKILLS" <<'PYEOF' 2>&1 || true
import re, sys, glob, os

WHITELIST = {
    "claude": {"name", "description", "disable-model-invocation",
               "argument-hint", "user-invocable", "context", "agent"},
    "codex":  {"name", "description", "disable-model-invocation"},
    "pi":     {"name", "description", "disable-model-invocation", "argument-hint"},
}
errs = []

for tag, base in zip(("claude", "codex", "pi"), sys.argv[1:4]):
    for f in sorted(glob.glob(os.path.join(base, "xz-*", "SKILL.md"))):
        d = os.path.basename(os.path.dirname(f))
        rel = f"{tag}:{d}"
        m = re.match(r"^---\n(.*?)\n---", open(f, encoding="utf-8").read(), re.S)
        if not m:
            errs.append(f"{rel} 没有 frontmatter")
            continue
        fm = m.group(1)

        keys = {ln.split(":", 1)[0] for ln in fm.splitlines()
                if re.match(r"^[a-z][a-z-]*:", ln)}
        extra = keys - WHITELIST[tag]
        if extra:
            errs.append(f"{rel} 字段越出白名单: {', '.join(sorted(extra))}"
                        f"（{tag} 端只许 {', '.join(sorted(WHITELIST[tag]))}）")

        nm = re.search(r"^name:\s*(.+)$", fm, re.M)
        name = nm.group(1).strip() if nm else ""
        if not name:
            errs.append(f"{rel} 缺 name")
        else:
            if name != d:
                errs.append(f"{rel} name({name}) 与目录名({d}) 不一致")
            if not re.fullmatch(r"[a-z0-9-]+", name):
                errs.append(f"{rel} name 含非法字符（只许 a-z 0-9 -）")
            if len(name) > 64:
                errs.append(f"{rel} name 超 64 字符")
            if name.startswith("-") or name.endswith("-") or "--" in name:
                errs.append(f"{rel} name 首尾为连字符或含连续连字符")

        dm = re.search(r"^description:\s*(.+)$", fm, re.M)
        desc = dm.group(1).strip() if dm else ""
        if not desc:
            errs.append(f"{rel} 缺 description 或为空")
        elif len(desc) > 1024:
            errs.append(f"{rel} description {len(desc)} 字符，超 spec 上限 1024")

print("\n".join(errs))
PYEOF
)
  if [ -n "$out" ]; then
    gate_err "frontmatter 不合规:"
    echo "$out" | head -10 | sed 's/^/       /'
  else
    echo "  ✅ frontmatter 字段白名单与 spec 约束都合规"
  fi
}

# 自动触发策略的三端一致性
#
# Claude / Pi 靠 SKILL.md 的 disable-model-invocation；Codex 不解析该字段，
# 靠 agents/openai.yaml 的 policy.allow_implicit_invocation。两套机制必须
# 表达同一个意图，否则同一个 skill 在 codex 上会照旧自动触发、白吃上下文。
check_invocation_policy() {
  local out
  out=$(python3 - "$CLAUDE_SKILLS" "$CODEX_SKILLS" "$PI_SKILLS" <<'PYEOF' 2>&1 || true
import re, sys, glob, os

def dmi(f):
    m = re.match(r"^---\n(.*?)\n---", open(f, encoding="utf-8").read(), re.S)
    if not m:
        return None
    v = re.search(r"^disable-model-invocation:\s*(\S+)\s*$", m.group(1), re.M)
    return v.group(1) if v else None

claude_dir, codex_dir, pi_dir = sys.argv[1:4]
errs = []

for cf in sorted(glob.glob(os.path.join(claude_dir, "xz-*", "SKILL.md"))):
    name = os.path.basename(os.path.dirname(cf))
    want = dmi(cf)
    if want is None:
        errs.append(f"{name}: claude 端缺 disable-model-invocation")
        continue

    # 1) 三端字段值必须逐字一致
    for tag, base in (("codex", codex_dir), ("pi", pi_dir)):
        f = os.path.join(base, name, "SKILL.md")
        if not os.path.exists(f):
            continue
        got = dmi(f)
        if got != want:
            errs.append(f"{name}: disable-model-invocation 三端不一致"
                        f"（claude={want} {tag}={got}）")

    # 2) codex 端用 openai.yaml 的 policy 表达同一意图
    y = os.path.join(codex_dir, name, "agents", "openai.yaml")
    txt = open(y, encoding="utf-8").read() if os.path.exists(y) else ""
    pm = re.search(r"^\s*allow_implicit_invocation:\s*(\S+)\s*$", txt, re.M)
    allow = pm.group(1) if pm else None
    if want == "true":
        if allow != "false":
            errs.append(f"{name}: claude 端禁用了自动触发，但 codex 的 "
                        f"agents/openai.yaml 没有 policy.allow_implicit_invocation: false"
                        f"（当前 {allow or '缺该文件或该字段'}）")
    elif want == "false":
        if allow == "false":
            errs.append(f"{name}: claude 端允许自动触发，但 codex 的 "
                        f"openai.yaml 把它禁掉了（allow_implicit_invocation: false）")

print("\n".join(errs))
PYEOF
)
  if [ -n "$out" ]; then
    gate_err "自动触发策略三端不一致:"
    echo "$out" | head -10 | sed 's/^/       /'
  else
    echo "  ✅ 自动触发策略三端一致（codex 走 openai.yaml policy）"
  fi
}

# Pi 无 skill 内 agents/ 的加载机制（依据: pi 的 dist/core/skills.js 与
# docs/skills.md）。agents/openai.yaml 是 Codex 插件规范，只许在 codex 端。
check_pi_no_agents() {
  local hits
  hits=$(find "$PI_SKILLS" -mindepth 2 -maxdepth 2 -type d -name agents 2>/dev/null || true)
  if [ -n "$hits" ]; then
    gate_err "pi 端出现了 agents/ 目录（Pi 不认这个格式，只许在 codex 端）:"
    echo "$hits" | sed "s|$MYAI_ROOT/||; s/^/       /"
  else
    echo "  ✅ pi 端没有 agents/ 目录"
  fi
}

# xz-tools.py 里按 _get_plugin_root() 定位的资源，codex/pi 端的 root 是
# ~/.xz_planning/，install.sh 不装就必然运行时失败（xz-init 踩过一次）。
check_global_resources() {
  if grep -rqE 'get-readme' "$CLAUDE_SKILLS" "$CODEX_SKILLS" "$PI_SKILLS" \
       --include=SKILL.md 2>/dev/null; then
    if ! grep -q 'README-template.md' "$INSTALL_SH"; then
      gate_err "有 skill 调 get-readme，但 install.sh 没装 resources/README-template.md"
      echo "       codex/pi 端的 _get_plugin_root() 是 ~/.xz_planning/，缺这个文件 xz-init 会失败" >&2
      return
    fi
  fi
  echo "  ✅ skill 依赖的全局资源都在 install.sh 里"
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
  check_frontmatter
  check_invocation_policy
  check_pi_no_agents
  check_global_resources
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
