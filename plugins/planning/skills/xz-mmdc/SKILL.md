---
name: xz-mmdc
description: "使用本地 Mermaid CLI mmdc 根据用户的文字描述生成一个 Mermaid flowchart 流程图，并同时生成一份关键链路说明文档。当用户显式输入 /xz-mmdc、要求使用 mmdc、或要求生成/渲染一个流程图时使用。支持 /xz-mmdc <序号> <中文描述/流程需求>，必须把第一个数字参数解析为输出序号。Use when the user explicitly invokes /xz-mmdc, asks to use mmdc, or asks to generate/draw/render one flowchart. Do not use for non-flowchart Mermaid diagrams, multi-diagram batches, or requests that only ask for Mermaid source without rendering. /xz-mmdc N 描述"
disable-model-invocation: false
argument-hint: "<序号> <中文描述/流程需求>"
---

# MMDC 流程图

## 路径说明

**辅助脚本：** `xz-mmdc-path.sh` 和 `xz-mmdc-render.sh`（插件启用时 `bin/` 自动加入 PATH，直接裸命令调用即可，无需 `python3` 前缀、无需绝对路径、也不需要先解析 skill 目录）。两个脚本都在**当前工作目录**下操作 `.xz_planning/`。

> 注意：**不要**调用 `~/.codex/skills/mmdc/scripts/...` 这类 codex 端绝对路径，那是 Codex 的脚本，在 Claude 端不存在。Claude 端一律用上面的裸命令。

## 强制规则

- 只生成一个 Mermaid `flowchart` 流程图；不要生成 sequenceDiagram、classDiagram、stateDiagram、gantt、pie、mindmap、ER 图或其它 Mermaid 图类型。
- 用户用 `/xz-mmdc 1 aaa 流程` 这类格式调用时，第一个参数 `1` 必须当作输出序号，不要把它当作流程内容。
- 用户没有显式指定输出路径时，必须由 `make-output-path.sh` 在当前工作目录创建 `.xz_planning/mmdc-output/<序号>.<中文描述>/`，目录名整体最多 30 个 Unicode 字符；目录内文件名固定为 `<序号>-mmdc.mmd`、`<序号>-mmdc.svg` 和 `<序号>-process.md`，例如 `.xz_planning/mmdc-output/1.aaa流程/1-mmdc.mmd`。
- 序号不能重复；如果路径生成脚本提示“序号已存在，请使用下一个序号”，必须停止本次生成，并把脚本提示的下一个可用序号告诉用户，不要覆盖旧图。
- 不要只回复 Mermaid 源码；必须把 `.mmd` 文件落盘，使用 `mmdc` 渲染出 `.svg`，并写出同级的 `<序号>-process.md` 关键链路说明文档。
- **不要自动打开渲染结果**：渲染脚本只输出文件路径，不再调用 `open`/`xdg-open`。完成后把 `.svg` 和 `.md` 路径告诉用户，让用户自行打开。
- 如果用户要求多个流程图，默认合并成一个总流程图；只有用户明确要求分批时，才提示用户下一次再生成另一个流程图。
- 如果用户描述不足以确定节点和分支，可以先问一个最小澄清问题；其它情况直接生成。
- 渲染失败时，报告失败原因、`mmdc` 的关键错误输出和已写入的源文件路径，不要声称已经完成。
- 长流程图必须优先保证可读性：节点文案要短，复杂说明拆节点；超过 25 个节点时优先使用 `flowchart LR` 或横向分组，避免生成一条过长的纵向细线。
- 默认渲染字体不得小于 18px，并使用自适应渲染视口；SVG 输出默认保持响应式 `width="100%" height="auto"`，不要改成固定巨大像素尺寸。

## 生成流程

1. 解析 `$ARGUMENTS`：如果第一个非空 token 是数字或点分数字（例如 `1`、`2`、`1.1`），它就是输出序号；后面的内容才是流程描述。如果没有序号，用 `1` 作为默认序号。
2. 运行路径生成脚本，拿到默认输出目录、`.mmd`、`.svg` 和 `process.md` 路径。不要手写截断逻辑，也不要绕过重复序号检查：

```bash
xz-mmdc-path.sh <序号> <中文描述...>
```

脚本输出格式固定为：

```text
dir=.xz_planning/mmdc-output/1.aaa流程
mmd=.xz_planning/mmdc-output/1.aaa流程/1-mmdc.mmd
svg=.xz_planning/mmdc-output/1.aaa流程/1-mmdc.svg
process=.xz_planning/mmdc-output/1.aaa流程/1-process.md
```

3. 从流程描述中提炼开始、处理步骤、判断分支、异常/失败路径和结束状态。如果描述涉及具体代码链路，记录每个关键步骤对应的 `文件:行号`、SQL/代码片段和说明，供 `process.md` 使用。
4. 生成 Mermaid 源码，第一条有效语句必须是 `flowchart TD` 或 `flowchart LR`。流程偏纵向时用 `TD`，跨系统/左右流转明显时用 `LR`。
5. 如果流程很长、分支多、节点超过 25 个，优先改用 `flowchart LR`，并用 `subgraph` 按阶段分组；只有用户明确要求纵向图时才继续使用 `TD`。
6. 节点文案使用用户语言，中文业务词不要随意翻译；节点保持短句，复杂说明拆成多个节点。单个节点尽量控制在 2 行内，避免一个节点里塞长段说明。
7. 分支边使用清晰标签，例如 `-->|是|`、`-->|否|`、`-->|失败|`、`-->|重试|`。
8. 把 Mermaid 源码写入路径脚本返回的 `.mmd` 文件后运行渲染脚本：

```bash
xz-mmdc-render.sh <input.mmd> [output.svg|output.png|output.pdf] [theme] [backgroundColor]
```

9. 脚本会自动按节点数量、最长行和方向估算 `--width/--height`，默认字体 18px，并把 SVG 设置为响应式宽度。脚本不会自动打开文件，只打印渲染结果路径。
10. 写出 `<序号>-process.md` 关键链路说明文档（见下方「关键链路说明文档」一节），与 `.svg` 放在同一目录。
11. 完成后简短告知 `.mmd`、`.svg` 和 `process.md` 三个文件路径，提示用户可自行打开 `.svg`。

## 关键链路说明文档（N-process.md）

`.svg` 渲染的是图，`<序号>-process.md` 用自然语言把图里的关键链路讲清楚，和 `.svg` 同级。它不是流程图的简单复述，而是按真实链路逐步说明每一步做了什么、对应哪段代码、关键 SQL/代码是什么、有什么注意点。

**写作规则：**

- 用有序列表把关键链路按执行顺序拆成若干步。
- 每一步：标题一句话讲清这步做什么；紧跟一行 `文件:行号`（如果描述里给了代码位置）；需要时附 SQL/代码块；再用「说明：」加无序列表补充要点。
- 涉及代码位置时务必保留用户给的 `文件:行号`，不要编造行号；用户没给就省略该行。
- 末尾可以加一句总结，点出链路的关键结论（例如某个值不是被直接使用，而是先同步到 Redis 再被消费）。
- 如果链路存在多个并行分支，用 `a`、`b` 等标注分支，分别说明。

**格式示例（用户给了带代码位置的链路时）：**

```markdown
关键链路是：

1. 从 live_room 读出 robot_num
   mysql/db_zmysql/zmysql.go:44

这里 SQL：

select a.room_id,b.user_id,a.updated_at,b.robot_num
from live_room_fake a
left join live_room b on a.room_id = b.id
where a.status = 1;

说明：

- 先从 live_room_fake 找启用中的假房
- 再关联 live_room
- 把 live_room.robot_num 读出来

2. 同步到 Redis
   routes/crontab/live_robot_fake.go:86

这里把它写进：
go:room_robot_num:%d

代码：

- v.RobotNum > 0 时才写
- TTL 是 10*60

也就是说，live_room.robot_num 本身不是直接被机器人主循环查 MySQL 使用，而是先被 robotFake() 同步到 Redis。

多分支示例（同一步分出 a、b 两条）：

3. 写入后的两条消费路径
   a. 机器人主循环读 Redis go:room_robot_num:%d
      routes/robot/loop.go:120
   b. 监控任务定时校验 Redis 与 MySQL 是否一致
      routes/crontab/check.go:30
```

## 参数和命名规则

- 触发词是 `/xz-mmdc`；用户写 `/xz-mmdc 1 aaa 流程` 时，`1` 是序号，`aaa 流程` 是描述。
- 默认输出目录格式：`.xz_planning/mmdc-output/<序号>.<中文描述>/`。
- 默认输出文件格式：`<序号>-mmdc.mmd`、`<序号>-mmdc.svg` 和 `<序号>-process.md`。文件名不带中文描述，中文描述只体现在目录名里。
- 目录名整体最多 30 个 Unicode 字符，包含序号和点号；中文描述过长时由 `make-output-path.sh` 自动截断。
- 描述中的空格和文件名不安全字符会被清理，例如 `/xz-mmdc 1 aaa 流程` 会生成 `.xz_planning/mmdc-output/1.aaa流程/` 下的三个文件。
- 如果 `.xz_planning/mmdc-output` 中已存在同序号目录，`make-output-path.sh` 会报错并提示下一个可用序号；此时必须停止生成，让用户改用提示的序号。
- 路径脚本会在目录内写入隐藏文件 `.mmdc-seq` 用于稳定识别序号，不要删除它。

## 长图可读性规则

- 超长流程图优先横向分阶段展示：例如“建连鉴权”“读包分发”“业务登录”“登录后处理”分别放入 `subgraph`。
- 如果必须使用 `TD`，要减少单链节点数量，能合并的连续普通步骤可以合并，但失败分支必须保留。
- 不要为了塞进一屏而过度缩小字体；长图默认按浏览器窗口宽度自适应，高度自然滚动。
- 默认字体大小为 18px。用户要求更大时，运行前设置环境变量，例如：

```bash
MMDC_FONT_SIZE=22 xz-mmdc-render.sh <input.mmd> <output.svg>
```

- 默认自适应宽高由脚本计算。用户指定尺寸时，运行前设置环境变量，例如：

```bash
MMDC_WIDTH=3600 MMDC_HEIGHT=9000 xz-mmdc-render.sh <input.mmd> <output.svg>
```

- SVG 默认响应式显示。只有用户明确要求“原始像素尺寸”“固定大小”时才设置：

```bash
MMDC_SVG_SIZE_MODE=fixed xz-mmdc-render.sh <input.mmd> <output.svg>
```

## mmdc 参数规则

- 必用：`-i, --input <input>` 指定输入 Mermaid 文件；`-o, --output [output]` 指定输出文件。
- 默认输出：用户未指定时使用 `input + .svg`；输出格式根据扩展名推断，也可用 `-e, --outputFormat svg|png|pdf`。
- 主题：`-t, --theme default|forest|dark|neutral`，默认 `default`。
- 背景：`-b, --backgroundColor <color>`，默认 `white`；PNG/SVG 可用 `transparent`、颜色名或 `#F0F0F0`。
- 尺寸：使用 `render-flowchart.sh` 的自适应渲染视口；SVG 默认响应式显示，不要直接回退到 Mermaid CLI 默认宽 800、高 600，也不要默认固定成实际像素宽高。
- 配置：脚本会自动生成临时 config，设置 18px 字体、中文友好的 font-family、节点间距和层级间距。只有用户明确提供额外配置时才补充 `-C, --cssFile`、`-p, --puppeteerConfigFile`。
- Markdown 输入会抽取多个图，不适合本 skill 的“只生成一个流程图”约束；新建图时不要写 `.md` 输入。
- `--iconPacks`、`--iconPacksNamesAndUrls` 仅在用户明确要求图标包时使用；不要为了普通流程图主动下载图标包。

## 失败处理

- 如果 `mmdc` 不存在，提示本机需要安装 Mermaid CLI，并停止渲染步骤。
- 如果 Mermaid 语法报错，先修正 `.mmd` 再重新运行脚本；不要留下无法渲染的最终结果。
- 渲染成功后只输出文件路径，不自动打开；把 `.svg` 和 `process.md` 路径告诉用户即可。
