#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
用法:
  render-flowchart.sh <input.mmd> [output.svg|output.png|output.pdf] [theme] [backgroundColor]

说明:
  只渲染单个 Mermaid flowchart 流程图，渲染成功后打印输出文件路径，不会自动打开。
  默认会按流程图复杂度自动估算画布，并把字体调大，避免长流程图打开后看不清。

环境变量:
  MMDC_FONT_SIZE  默认 18
  MMDC_WIDTH      手动指定渲染视口宽度
  MMDC_HEIGHT     手动指定渲染视口高度
  MMDC_SVG_SIZE_MODE  responsive 或 fixed，默认 responsive
USAGE
}

if [[ $# -lt 1 || $# -gt 4 ]]; then
  usage
  exit 2
fi

input_file="$1"
output_file="${2:-}"
theme="${3:-default}"
background_color="${4:-white}"

if ! command -v mmdc >/dev/null 2>&1; then
  echo "错误: 未找到 mmdc，请先安装 Mermaid CLI 后再渲染流程图。" >&2
  exit 127
fi

if [[ ! -f "$input_file" ]]; then
  echo "错误: 输入文件不存在: $input_file" >&2
  exit 1
fi

case "$theme" in
  default|forest|dark|neutral) ;;
  *)
    echo "错误: 不支持的主题: $theme，可选 default、forest、dark、neutral。" >&2
    exit 2
    ;;
esac

if [[ -z "$output_file" ]]; then
  output_file="${input_file%.*}.svg"
fi

case "$output_file" in
  *.svg|*.png|*.pdf) ;;
  *)
    echo "错误: 输出文件必须是 .svg、.png 或 .pdf: $output_file" >&2
    exit 2
    ;;
esac

first_statement="$(
  grep -Ev '^[[:space:]]*$|^[[:space:]]*%%' "$input_file" | head -n 1 || true
)"

if [[ ! "$first_statement" =~ ^[[:space:]]*(flowchart|graph)[[:space:]]+ ]]; then
  echo "错误: 该 skill 只允许渲染 Mermaid flowchart，第一条有效语句必须是 flowchart 或 graph。" >&2
  echo "当前第一条有效语句: ${first_statement:-<空>}" >&2
  exit 2
fi

mkdir -p "$(dirname "$output_file")"

content_lines="$(
  grep -Ev '^[[:space:]]*$|^[[:space:]]*%%' "$input_file" | tail -n +2 | wc -l | tr -d '[:space:]'
)"
max_line_len="$(
  awk 'length($0) > max { max = length($0) } END { print max + 0 }' "$input_file"
)"

direction="TD"
if [[ "$first_statement" =~ [[:space:]](LR|RL)[[:space:]]*$ ]]; then
  direction="LR"
fi

clamp() {
  local value="$1"
  local min="$2"
  local max="$3"
  if (( value < min )); then
    echo "$min"
  elif (( value > max )); then
    echo "$max"
  else
    echo "$value"
  fi
}

font_size="${MMDC_FONT_SIZE:-18}"
if ! [[ "$font_size" =~ ^[0-9]+$ ]]; then
  echo "错误: MMDC_FONT_SIZE 必须是数字: $font_size" >&2
  exit 2
fi

if [[ "$direction" == "LR" ]]; then
  auto_width=$(( content_lines * 140 + max_line_len * 8 + 800 ))
  auto_height=$(( content_lines * 42 + 600 ))
  auto_width="$(clamp "$auto_width" 1400 12000)"
  auto_height="$(clamp "$auto_height" 900 6000)"
else
  auto_width=$(( max_line_len * 18 + 1200 ))
  auto_height=$(( content_lines * 120 + 700 ))
  auto_width="$(clamp "$auto_width" 1400 6000)"
  auto_height="$(clamp "$auto_height" 900 16000)"
fi

render_width="${MMDC_WIDTH:-$auto_width}"
render_height="${MMDC_HEIGHT:-$auto_height}"
if ! [[ "$render_width" =~ ^[0-9]+$ && "$render_height" =~ ^[0-9]+$ ]]; then
  echo "错误: MMDC_WIDTH 和 MMDC_HEIGHT 必须是数字。" >&2
  exit 2
fi

config_file="$(mktemp "${TMPDIR:-/tmp}/mmdc-flowchart-config.XXXXXX.json")"
trap 'rm -f "$config_file"' EXIT

cat >"$config_file" <<CONFIG
{
  "themeVariables": {
    "fontSize": "${font_size}px",
    "fontFamily": "Arial, PingFang SC, Microsoft YaHei, sans-serif"
  },
  "flowchart": {
    "htmlLabels": true,
    "nodeSpacing": 80,
    "rankSpacing": 90,
    "padding": 24
  }
}
CONFIG

mmdc \
  --input "$input_file" \
  --output "$output_file" \
  --theme "$theme" \
  --backgroundColor "$background_color" \
  --width "$render_width" \
  --height "$render_height" \
  --configFile "$config_file"

if [[ "$output_file" == *.svg ]]; then
  viewbox="$(grep -o 'viewBox="0 0 [^"]*"' "$output_file" | head -n 1 || true)"
  if [[ "$viewbox" =~ viewBox=\"0[[:space:]]0[[:space:]]([0-9.]+)[[:space:]]([0-9.]+)\" ]]; then
    svg_width="${BASH_REMATCH[1]%.*}"
    svg_height="${BASH_REMATCH[2]%.*}"
    svg_size_mode="${MMDC_SVG_SIZE_MODE:-responsive}"
    case "$svg_size_mode" in
      responsive)
        perl -0pi -e 's/<svg([^>]*)width="[^"]*"([^>]*)>/<svg${1}width="100%" height="auto" preserveAspectRatio="xMidYMin meet"${2}>/s; s/max-width:\s*[^;"]+;/max-width: 100%;/s' "$output_file"
        ;;
      fixed)
        perl -0pi -e "s/<svg([^>]*)width=\"[^\"]*\"([^>]*)>/<svg\${1}width=\"${svg_width}px\" height=\"${svg_height}px\" preserveAspectRatio=\"xMidYMin meet\"\${2}>/s" "$output_file"
        ;;
      *)
        echo "错误: MMDC_SVG_SIZE_MODE 只能是 responsive 或 fixed: $svg_size_mode" >&2
        exit 2
        ;;
    esac
  fi
fi

echo "$output_file"
