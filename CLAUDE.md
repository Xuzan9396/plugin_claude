# plugin_claude — XZ Planning 三端插件仓库

同一套「版本计划驱动开发」提示词，同时供 Claude Code / Codex / Pi 三个 agent 使用。

## 真源与三端目录

**Claude 端是唯一真源。** 规则先改 Claude，再按方言表转写到另外两端；codex/pi 端不允许出现 Claude 端没有的规则，发现多出来的一律删掉。

| 端 | skill 目录 | 附属资源 | 安装位置 |
|---|---|---|---|
| **Claude（真源）** | `plugin_claude/plugins/planning/skills/` | `bin/`（xz-tools.py、xz-mmdc-*.sh）、`agents/xz-code-reviewer.md` | GitHub marketplace 插件 |
| **Codex** | `skills/codex/` | `skills/script/xz-tools.py`、`codex/agents/xz-code-reviewer.toml`、`codex/xz-mmdc/scripts/` | `~/.codex/skills` + `~/.codex/agents` |
| **Pi** | `pi_skills/` | 复用 `~/.xz_planning/script/xz-tools.py`、`xz-mmdc/scripts/` | `~/.pi/agent/skills` |

`skills/script/xz-tools.py` 是 `plugins/planning/bin/xz-tools.py` 的副本，必须逐字节一致（`tag.sh` 会校验并自动同步）。

## skill 定义硬约束

### frontmatter 字段白名单

**三端都真解析的只有 `name` 和 `description`。** 下表以外的键一律不许加——加了不报错、会被静默忽略，等于埋一个假功能。

| 字段 | 必需 | Claude | Codex | Pi | 约束 |
|---|---|---|---|---|---|
| `name` | ✅ | ✅ | ✅ | ✅ | ≤64 字符、`^[a-z0-9-]+$`、首尾不得为连字符、不得含 `--`、**必须与目录名逐字一致** |
| `description` | ✅ | ✅ | ✅ | ✅ | 非空、≤1024 字符。写「什么时候该用」而不是「有什么功能」——它是触发器，模型只靠 `name`+`description` 决定要不要调 |
| `disable-model-invocation` | | ✅ | ❌ runtime 不读 | ✅ | 三端逐字跟随 Claude 真源值。**Codex 不认这个字段，它的等效开关在 `agents/openai.yaml`** —— 见下方「自动触发策略」 |
| `argument-hint` | | ✅ | ❌ 不解析 | ⚠️ 保留 | Claude 端生效。**Codex 端不写。Pi 端写但按现有证据不生效**（详见下方「argument-hint 的证据状况」），保留是为了三端 frontmatter 结构对齐 |
| `user-invocable` | | ✅ | ❌ | ❌ | 仅 xz-cdp-cli 有；codex/pi 不写 |
| `context: fork` / `agent:` | | ✅ | ❌ | ❌ | 仅 xz-review 有；codex/pi 不写。注意这两端会退化成主上下文直跑，行为不同且无警告 |

另有四个字段 **Pi 官方文档声明支持**（`docs/skills.md` 的 frontmatter 表）、但本仓库不使用，闸门白名单也不含它们，别往里加：`license`、`compatibility`、`metadata`、`allowed-tools`。Claude 端也支持 `allowed-tools`（会真的执行），Codex 只在打包校验里认它。

Agent Skills 开放标准只有六个键：`name`、`description`、`license`、`allowed-tools`、`metadata`、`compatibility`。本仓库用到的 `disable-model-invocation`、`argument-hint`、`user-invocable`、`context`、`agent` **全是 Claude Code 扩展**，spec 校验器会判为 unexpected key。将来若要走 `codex plugin` 发布路径，得先摘掉这些键。

实测依据（2026-09-07，claude 2.1.251 / codex-cli 0.150.1 / pi 0.85.1）：

- Pi 的 skill 加载器是明文 JS：`~/.npm-global/lib/node_modules/@earendil-works/pi-coding-agent/dist/core/skills.js`，构造出的 skill 对象只含 `name` / `description` / `disable-model-invocation`（第 262 行）。`name` / `description` 的长度与字符集校验在第 61、80 行，违规会被 Pi 拒绝加载。
- Codex 的 `argument-hint`、`user-invocable` 在二进制里各只命中 1 次，位置都在一段「教模型怎么写 skill」的内嵌提示词里（`grep -ac 'argument_hint'` 为 0，即无 serde 解析符号）。**注意：那段提示词自称支持 `argument-hint`、`user-invocable`、`allowed-tools`、`context`、`agent`、`model`——它的文档与实现不一致，不要拿它当依据。**
- Codex 的 `disable-model-invocation` 只被内嵌的插件打包校验脚本读取，且要求其为 `false`。本仓库用 `install.sh` 直接拷目录，不走打包，所以既不受该约束也享不到该功能。

#### 取证陷阱（这几条都真踩过，别重犯）

1. **先查官方文档，再逆向。** Pi 自带 `docs/skills.md`、`docs/prompt-templates.md`、`CHANGELOG.md`，比 grep 二进制可靠得多，还能查到某特性是哪个版本引入、限定在什么范围。
2. **别 grep `dist/bundle/cli.js`。** 它只有 660 字节，是个 launcher stub，grep 它得不出任何结论。Pi 的真实逻辑在 `dist/core/*.js`（明文、带 `.d.ts` 类型定义），实际执行的打包产物在 `dist/bundle/chunks/`（`package.json` 的 `bin.pi` 指向它）。
3. **Codex 的 rust 二进制用 `grep -a` 而不是 `strings`**，后者会漏字。
4. **区分「字段出现在字符串里」和「字段被代码解析」。** 同一个字段名可能出现在内嵌提示词、文档、打包校验脚本里，全都不等于运行时会读它。要找到真正的赋值/取值点。
5. **别用「三端文件里都写了这个字段」当证据。** 那些文件正是按方言表同步写进去的，属于循环论证——本仓库最初把 `argument-hint` 误判为三端支持就是这么来的。

#### `argument-hint` 的证据状况

Pi 端保留该字段是主动决定，不是因为它生效。现有证据指向**不生效**：

- `docs/skills.md` 的 frontmatter 字段表**没有** `argument-hint`；`docs/prompt-templates.md:33,37,42` 是唯一描述它的文档，全在 Prompt Templates 章节
- `CHANGELOG.md:1986,1993` —— 该特性在 **0.67.6（2026-04-16）** 引入，原文限定 "Prompt templates support an `argument-hint` frontmatter field…"，到 0.85.1 无条目将其扩展到 skill
- `dist/core/skills.js` 全文不含该字段，且与 `prompt-templates.js` 互不引用
- `dist/modes/interactive/interactive-mode.js:480` 把 skill 转成自动补全项时只带 `name` + `description`；同文件 `:460` 的 prompt template 分支明确带了 `argumentHint`
- 打包产物里 `argumentHint` 共 13 处，无一在 skill 上下文

未排除：没有实际运行 Pi 观察补全下拉框；第三方 extension 理论上可自行读 `SKILL.md` 注入 hint。

留着它零风险（Agent Skills spec 规定未知键静默忽略，Pi 也不对未知键报错），所以保留换取三端结构对齐。**但不要在文档或代码注释里把它写成「Pi 支持」。**

### 自动触发策略

目标：**装再多 skill，没手动调用之前都不吃模型上下文。** 未启用的 skill 连 `description` 都不进 context，模型也无法自行触发；只有手动点名的那一个才加载。

**只有 `xz-exec` 和 `xz-debug` 允许模型自动触发，其余 15 个全部禁用。**

判断依据：**带位置编号参数（版本号 N）的 skill 一律不许自动触发。** 模型自行触发时拿不准该用哪个版本号，猜错就会往错误的版本目录里写东西。`xz-plan`、`xz-update-plan` 就是因此禁掉的。

三端机制不同，但必须表达同一意图：

| 端 | 开关 | 手动调用 |
|---|---|---|
| Claude | `SKILL.md` 里 `disable-model-invocation: true` | `/xz-plan` |
| Pi | `SKILL.md` 里 `disable-model-invocation: true` | `/skill:xz-plan` |
| Codex | **`agents/openai.yaml` 里 `policy.allow_implicit_invocation: false`** | `$xz-plan` |

Codex 特殊：它的 runtime **不解析** `disable-model-invocation`，写了也没用。真正生效的是每个 skill 目录下的 `agents/openai.yaml`：

```yaml
interface:
  display_name: "创建版本计划"
  short_description: "创建新版本计划，含目标、上下文、约束与完成标准"
policy:
  allow_implicit_invocation: false
```

写这个文件的三条硬约束（来自 codex 二进制内的 `validate_skill_agent_manifest`）：

1. **`interface` 是必填的**，且 `display_name`、`short_description` 必须是非空字符串——只写 `policy` 段会被判不合规
2. 顶层只许 `interface` / `policy` / `dependencies`；`interface` 下只许 `display_name` / `short_description` / `icon_small` / `icon_large` / `brand_color` / `default_prompt`；`policy` 下**只许** `allow_implicit_invocation`
3. `allow_implicit_invocation` 必须是布尔值。默认为 `true`（即默认允许自动触发），所以**允许自动触发的 skill 不需要建这个文件**

codex 官方对该字段的说明是「保持 skill 可被 `$skill-name` 显式调用，但不自动加入模型上下文」。

改自动触发策略时**必须三处同步**：Claude 端 `SKILL.md`、Pi 端 `SKILL.md`、Codex 端 `agents/openai.yaml`。闸门会校验这三者是否一致，漏一处就拦下。

> 这套开关只影响**送进 LLM 的上下文**。CLI 本地为了 `/`、`$` 的自动补全仍会扫磁盘上的 skill 元数据——本地扫描不消耗 token。

### 新增 / 修改 skill 的红线

1. 目录名 = `name` = 调用名，三者一致，只用小写字母、数字、连字符。
2. frontmatter 不许超出上表，宁可少写不许瞎写。**Codex 端只允许 `name`、`description`、`disable-model-invocation`；Pi 端在此之上多一个 `argument-hint`。** 闸门按这个白名单卡死。
3. **带位置参数**的 skill（xz-plan、xz-exec 等，参数是版本号 N），`description` 末尾必须写本端调用式（`/xz-plan N 需求` / `$xz-plan N 需求` / `/skill:xz-plan N 需求`）。纯语义触发、无位置参数的（xz-debug、xz-debug-mode、xz-cdp-cli）不强制。xz-mmdc 按方言表用 `$mmdc` / `mmdc`，不是 `$xz-mmdc`。
4. 附属文件（`scripts/`、`examples/`、`agents/`）同样要按方言表转写。`agents/openai.yaml` 是 Codex 专属规范（承载自动触发开关），**只许出现在 `skills/codex/` 下**；Pi 端不认这个格式，`pi_skills/` 下不许有 `agents/`。
5. 三端 skill 目录名单必须完全一致。
6. skill 里调用 `xz-tools.py` 的子命令，如果依赖 `_get_plugin_root()` 下的资源文件（`resources/`、`skills/`），必须确认 `install.sh` 的 `install_global_files()` 把那些资源也装进了 `~/.xz_planning/`——Claude 端跑得通不代表另两端跑得通，它们的 root 是 `~/.xz_planning/` 而非 `plugins/planning/`。

上面这 6 条**闸门已全部自动检查**（第 3 条除外，它是判断题、只能人工守）。`./tag.sh --check` 会一次报出所有违规、不会遇到第一个就中断。

## 同步的是什么

**只同步自然语言规则**——流程、判断标准、话术、禁令、模板。每端的调用语法、工具名、脚本路径按下面的方言表转写，**不许串味**。frontmatter 字段照上面的白名单，不在方言表里重复。

### 方言表

| 维度 | Claude | Codex | Pi |
|---|---|---|---|
| 调用前缀 | `/xz-plan 1 需求` | `$xz-plan 1 需求` | `/skill:xz-plan 1 需求` |
| 参数占位 | `$ARGUMENTS` | `$ARGUMENTS` | `<调用参数>` |
| 首个参数 | `$0` | `$0` | `<第一个参数>` |
| 参数约定说明 | 无 | 无 | H1 下方必须有 `> Pi 参数约定：…` 引用块 |
| 参数注入机制 | harness 替换占位符 | 同 Claude | **不替换**，把 `User: <args>` 追加到正文末尾，故必须有参数约定块 |
| 脚本调用 | `xz-tools.py parse 1`（`bin/` 已在 PATH） | `python3 ~/.xz_planning/script/xz-tools.py parse 1` | 同 Codex |
| 提问方式 | 纯文本提问，并写明「禁用 AskUserQuestion——其弹窗会吞掉同回复中前面的文本」 | 纯文本提问（无该工具，不提它） | 同 Codex |
| 浏览器自动化 | `/claude-in-chrome` skill + `mcp__claude-in-chrome__*` 工具 | `$chrome` 插件（`chrome@openai-bundled`） | 泛指「浏览器自动化能力」，不绑定具体工具名 |
| 代码审查子代理 | `agents/xz-code-reviewer.md`（frontmatter 带 `tools:`） | `agents/xz-code-reviewer.toml`（`developer_instructions`） | 无子代理，规则内联 |
| mmdc 渲染脚本 | 裸命令 `xz-mmdc-render.sh`、`xz-mmdc-path.sh`（`bin/` 在 PATH） | 全路径 `~/.codex/skills/xz-mmdc/scripts/render-flowchart.sh`、`make-output-path.sh` | 全路径 `~/.pi/agent/skills/xz-mmdc/scripts/...` |
| mmdc 触发词 | `/xz-mmdc` | `$mmdc`、`mmdc` | `/skill:xz-mmdc`、`mmdc` |

### 改完必做

1. 改 `plugins/planning/skills/<skill>/SKILL.md`
2. 按方言表转写 `skills/codex/<skill>/SKILL.md` 和 `pi_skills/<skill>/SKILL.md`
3. 三端 skill 目录名单必须完全一致（新增/删除 skill 要三端一起动）
4. 跑 `./tag.sh --check` 体检——字段白名单、`name`/目录名一致、串味、附属文件、全局资源都在里面，一次报全
5. 跑 `./tag.sh vX.Y.Z` 发版 —— 同一套闸门，不过就不让推

## 发布与安装

```bash
./tag.sh v1.5.3        # 闸门 → 改版本号 → commit/push → 装 codex → 装 pi
./tag.sh --check       # 只跑闸门体检，不改任何东西
```

闸门检查项（发现问题会一次报全，不会遇到第一个就中断）：

1. 三端 skill 名单一致
2. 各端不含别家语法——扫 skill 目录下 `*.md` / `*.yaml` / `*.yml` / `*.js` / `*.sh` / `*.toml`，不只是 `SKILL.md`
3. frontmatter 字段在该端白名单内，`name` 与目录名逐字一致，`name` / `description` 满足 Agent Skills spec 的字符集与长度约束
4. 自动触发策略三端一致——`disable-model-invocation` 三端同值，且 Codex 的 `agents/openai.yaml` 的 `policy.allow_implicit_invocation` 与之等效
5. `pi_skills/` 下没有 `agents/` 目录
6. skill 用到的 `xz-tools.py` 子命令，其依赖的全局资源已在 `install.sh` 里安装
7. Pi 端有「Pi 参数约定」说明块
8. `xz-tools.py` 两份一致（发版模式下会自动同步）

单独装某一端（`--yes` 跳过逐个覆盖确认）：

```bash
../skills/install.sh --codex --yes    # → ~/.codex/skills + ~/.codex/agents
../skills/install.sh --pi --yes       # → ~/.pi/agent/skills（无子代理）
../skills/install.sh --claude --yes   # → ~/.claude/skills，源是本仓库 plugins/planning
```

`reinstall.sh` / `uninstall.sh` 同样支持这三个平台参数。
