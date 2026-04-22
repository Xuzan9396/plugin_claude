#!/usr/bin/env bash
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "用法: $0 vX.Y.Z" >&2
  echo "示例: $0 v1.1.1" >&2
  exit 1
fi

tag="$1"
if [[ ! "$tag" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "版本号格式错误，应为 vX.Y.Z（例: v1.1.1）" >&2
  exit 1
fi

version="${tag#v}"
marketplace=".claude-plugin/marketplace.json"
plugin_json="plugins/planning/.claude-plugin/plugin.json"

for f in "$marketplace" "$plugin_json"; do
  if [ ! -f "$f" ]; then
    echo "未找到 $f，请在插件仓库根目录执行" >&2
    exit 1
  fi
done

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

echo "[1/3] marketplace.json + plugin.json 已改为 $version"

git add -A
if git diff --cached --quiet; then
  echo "没有需要提交的改动，终止" >&2
  exit 1
fi
git commit -m "$version"
echo "[2/3] 已提交 commit"

git push
echo "[3/3] 已 push 到远端"
