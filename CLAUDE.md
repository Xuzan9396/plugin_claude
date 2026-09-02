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

## 同步的是什么

**只同步自然语言规则**——流程、判断标准、话术、禁令、模板。每端的调用语法、工具名、脚本路径按下面的方言表转写，**不许串味**。

### 方言表

| 维度 | Claude | Codex | Pi |
|---|---|---|---|
| 调用前缀 | `/xz-plan 1 需求` | `$xz-plan 1 需求` | `/skill:xz-plan 1 需求` |
| 参数占位 | `$ARGUMENTS` | `$ARGUMENTS` | `<调用参数>` |
| 首个参数 | `$0` | `$0` | `<第一个参数>` |
| 参数约定说明 | 无 | 无 | H1 下方必须有 `> Pi 参数约定：…` 引用块 |
| `disable-model-invocation` | 真源值 | 逐字跟随 Claude | 逐字跟随 Claude |
| `user-invocable` | 仅 xz-cdp-cli 有 | 不写 | 不写 |
| `context: fork` / `agent:` | 仅 xz-review 有 | 不写 | 不写 |
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
4. 跑 `./tag.sh vX.Y.Z` —— 它带语法闸门，串味会直接拦下不让推

## 发布与安装

```bash
./tag.sh v1.5.3        # 闸门 → 改版本号 → commit/push → 装 codex → 装 pi
./tag.sh --check       # 只跑闸门体检，不改任何东西
```

闸门检查项：三端 skill 名单一致、各端不含别家语法、`xz-tools.py` 两份一致、Pi 端有参数约定块。

单独装某一端（`--yes` 跳过逐个覆盖确认）：

```bash
../skills/install.sh --codex --yes    # → ~/.codex/skills + ~/.codex/agents
../skills/install.sh --pi --yes       # → ~/.pi/agent/skills（无子代理）
../skills/install.sh --claude --yes   # → ~/.claude/skills，源是本仓库 plugins/planning
```

`reinstall.sh` / `uninstall.sh` 同样支持这三个平台参数。
