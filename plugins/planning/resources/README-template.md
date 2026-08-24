# XZ Planning - 轻量级版本计划驱动开发

init → discuss? → plan → exec(含闭环测试) ⇄ update-plan? → review? → done

辅助: status / ref / test / del / remove-all

基于 todolist 的开发流程管理工具，通过 Claude Code 插件驱动。

## 命令一览

**核心流程：**

| 命令 | 用途 | 必须 | 示例 |
|------|------|:----:|------|
| `/xz-planning:xz-init` | 初始化当前项目的计划目录 | ✅ | `/xz-planning:xz-init` |
| `/xz-planning:xz-discuss N 讨论内容` | 澄清需求，比 2-3 个方案给推荐 | 可选 | `/xz-planning:xz-discuss 1 做个客户管理工具` |
| `/xz-planning:xz-plan N 需求描述` | 创建新版本计划 | ✅ | `/xz-planning:xz-plan 1 实现用户注册登录` |
| `/xz-planning:xz-update-plan N 操作` | 修改/新增/删除 todolist 条目 | 可选 | `/xz-planning:xz-update-plan 1 修改 #3 增加缓存` |
| `/xz-planning:xz-exec N` | 执行未完成的 todolist + 完成后自动闭环测试 | ✅ | `/xz-planning:xz-exec 1` |
| `/xz-planning:xz-review N` | 审查版本 N 的代码质量和安全 | 可选 | `/xz-planning:xz-review 1` |
| `/xz-planning:xz-done N` 或 `all` | 归档版本，`all` 为全部强制归档 | ✅ | `/xz-planning:xz-done 1`、`/xz-planning:xz-done all` |

**辅助工具：**

| 命令 | 用途 | 示例 |
|------|------|------|
| `/xz-planning:xz-status` | 查看所有版本状态总览 | `/xz-planning:xz-status` |
| `/xz-planning:xz-status N` | 查看版本 N 的详细进度 | `/xz-planning:xz-status 1` |
| `/xz-planning:xz-eli5 内容 [讲给谁]` | 讲人话：按听众水平把东西讲明白 | `/xz-planning:xz-eli5 这个报错 讲给我妈听` |
| `/xz-planning:xz-del N` | 删除单个版本计划 | `/xz-planning:xz-del 2` |
| `/xz-planning:xz-remove-all` | 交互式清理全部计划数据 | `/xz-planning:xz-remove-all` |

## 典型工作流

```
                          ┌─────────────────────────────────┐
                          │  /xz-planning:xz-init            │  必须，首次使用前执行
                          └──────────────┬──────────────────┘
                                         ↓
                     ┌───────────────────────────────────────────┐
                     │  /xz-planning:xz-discuss N 讨论内容        │  可选，头脑风暴
                     └───────────────────┬──────────────────────┘
                                         ↓
                          ┌─────────────────────────────────┐
                          │  /xz-planning:xz-plan N 需求描述  │  必须，生成 todolist
                          └──────────────┬──────────────────┘
                                         ↓
                          ┌─────────────────────────────────┐
                     ┌──→ │  /xz-planning:xz-exec N          │  必须，逐条执行 + 闭环测试
                     │    └──────────────┬──────────────────┘
                     │                   ↓
                     │    ┌─────────────────────────────────┐
                     └────│  /xz-planning:xz-update-plan N   │  可选，中途增删改条目
                          └──────────────┬──────────────────┘
                                         ↓
                     ┌───────────────────────────────────────────┐
                     │  /xz-planning:xz-review N                  │  可选，代码审查
                     └───────────────────┬──────────────────────┘
                                         ↓
                          ┌─────────────────────────────────┐
                          │  /xz-planning:xz-done N          │  必须，归档
                          └─────────────────────────────────┘
```

**最小流程：** `init → plan → exec → done`

**完整流程：** `init → discuss → plan → exec(含闭环测试) ⇄ update-plan → review → done`

典型使用示例：

```
0. /xz-planning:xz-init                                              ← 首次
1. /xz-planning:xz-discuss 1 做一个用户注册登录和JWT鉴权               ← 可选
2. /xz-planning:xz-plan 1 实现用户注册登录和JWT鉴权
3. /xz-planning:xz-exec 1                                            ← 执行完自动跑闭环测试
4. /xz-planning:xz-update-plan 1 新增一条: 添加密码找回功能            ← 可选
5. /xz-planning:xz-exec 1
6. /xz-planning:xz-review 1                                          ← 可选
7. /xz-planning:xz-done 1
```

## 目录结构

### 插件结构

```
xz-planning/
├── .claude-plugin/
│   └── plugin.json             # 插件清单
├── skills/                     # Skill 定义
│   ├── xz-init/SKILL.md
│   ├── xz-plan/SKILL.md
│   ├── xz-exec/SKILL.md
│   ├── xz-review/SKILL.md
│   ├── xz-discuss/SKILL.md
│   └── ...（所有 xz-* skills）
├── agents/                     # 子代理定义
│   └── xz-code-reviewer.md
├── bin/                        # 可执行脚本（自动加入 PATH）
│   └── xz-tools.py
└── resources/
    └── README-template.md      # 项目 README 模板
```

### 项目运行时目录

执行 `/xz-planning:xz-init` 后会在项目根目录生成：

```
.xz_planning/
├── STATE.md                    # 全局状态表
├── README.md                   # 使用说明
├── PROJECT.md                  # 项目快照索引
├── phases/
│   ├── 1.用户注册登录/
│   │   ├── 1-DISCUSS.md        # 讨论文档（可选）
│   │   ├── 1-PLAN.md           # 版本计划和 todolist（含测试方案）
│   │   ├── 1-TEST-REPORT.md    # 闭环测试报告（xz-exec 自动产出）
│   │   └── tests/              # 测试产物，按 T 编号前缀平铺
│   │       ├── .env.local      # 测试用的连接/凭据（自动加进 .gitignore）
│   │       ├── T1-req.json     # T1 的请求体
│   │       ├── T1-resp.json    # T1 的实际响应（已脱敏）
│   │       ├── T1-run.log      # T1 的运行输出
│   │       ├── T3-run.sh       # 无测试框架时的可执行脚本
│   │       └── T3-01-登录成功.png  # 浏览器用例的关键节点截图
│   └── 2.商品管理/
│       └── 2-PLAN.md
└── archive/                    # 已归档的版本
    └── 1.用户注册登录/
        └── 1-PLAN.md
```

## 各命令详细说明

### /xz-planning:xz-init

初始化当前项目的 `.xz_planning/` 目录结构。首次使用前必须执行。已初始化的项目会提示跳过，不会覆盖已有数据。

### /xz-planning:xz-discuss N 讨论内容

把粗糙想法收敛成一份「做什么」的讨论文档。**不是必须步骤**，可以跳过直接 `/xz-planning:xz-plan`。

流程：摸清现状 → 澄清缺口（最多 5 问，一次一个，每问带推荐项）→ 出 2-3 个方案（每个都写清「不做什么」）→ 给推荐 → 确认后写 `N-DISCUSS.md`。

输出包含：需求重述、澄清结果、方案对比（思路/做什么/不做什么/代价/体量）、风险与待确认（已知/假设/待确认）。

**只答「做什么」**——架构、改哪些文件、怎么测这些「怎么做」的事留给 `/xz-planning:xz-plan`。方案没确认前不写代码、不排 todo。

写完后自己把选定的方案带进 `/xz-planning:xz-plan`（它不会自动读 `N-DISCUSS.md`）。

### /xz-planning:xz-plan N 需求描述

创建新版本计划。要求项目已初始化。如果同目录存在 `N-DISCUSS.md`，自动引用。

每条 todolist 包含 `改动详情`，明确写出新建/修改哪些文件。

生成后先展示草案，你确认后才写入文件。如果版本已存在会拒绝，提示用 `/xz-planning:xz-update-plan`。

确认时可选**手动执行**路径：额外生成 `N-MANUAL.md`（改动地图 + 逐块 `改动 i/n` 进度 + 复制即用的代码块），你自己贴码、掌握代码写到哪儿了；贴完跑 `/xz-planning:xz-exec N` 校验差异并自动闭环验证。

### /xz-planning:xz-update-plan N 操作描述

修改已有版本的 todolist。支持修改、新增、删除、插入条目。已完成的 `[x]` 条目受锁定保护，不可修改或删除。

### /xz-planning:xz-exec N

从第一个未完成的 `[ ]` 条目开始，按 改动详情 逐条执行代码编写/修改。

**todolist 全部完成后自动进入闭环测试**：按 `N-PLAN.md` 的 `## 测试方案` 逐条跑自动化用例（单测/接口/CLI/浏览器），失败就分诊——计划内实现 bug 直接修，用例或环境问题修用例，越界项停下报告；每轮修完**全量回归**，最多 3 轮。每修一处会在终端打印 `文件:行号 + 原因 + 改前/改后`，改了哪儿一目了然。结果写入 `N-TEST-REPORT.md`。

**卡住一定会喊你，不会闷头死磕**（防死循环护栏）：同一条用例最多修 3 次、全局最多 3 轮、同一失败最多重跑确认 2 次、单条命令超 2 分钟判挂起、同一问题最多追问 2 轮。触到上限或遇到下列情况就停下来找你——根因说不清、缺信息改法全靠猜、环境起不来、需要真实凭证/线上环境、**需要你手动操作到某一步**（验证码、扫码、后台点按钮）。求助时会把无关用例先跑完，再把卡壳项**攒成一份清单一次性问**，每项写清「现象 / 已尝试 / 卡在哪 / 需要你 / 拿到后我做什么」。你可以：直接给信息、回「N 已就绪」（你手动操作到位了，AI **从那个状态接着跑，不让你重做一遍**）、或回「跳过 N」。提问后到你回复前 AI 真的会停手，不改代码也不再试。

另外 AI **不许放水**：不许为了让用例变绿去改断言迁就错误结果、删用例、注释被测代码或把逻辑 mock 成永远成功。

**每条用例都留一份可手动复现的现场**：跑出来的脚本、截图、请求响应样本、日志**平铺**在 `.xz_planning/phases/N.xxx/tests/`，文件名带 `T{编号}-` 前缀（如 `T1-resp.json`、`T3-01-登录成功.png`），不建子目录、也不会丢进 `/tmp`。**怎么重跑写在 `N-TEST-REPORT.md` 的「复现步骤」段**——每条用例一个代码块，贴的是真跑过的命令（cwd = 项目根，复制即可执行），末尾带预期和产物文件名，**你可以照着自己重跑任意一条**，不用回翻对话。需要你人工配合的用例会用 `# ⚠️ 你手动做：` 标出哪一步归你、AI 从第几步续跑；跳过的用例也照样写步骤。项目已有测试框架时，测试代码仍写进项目正式测试目录，报告里写明代码位置 + 运行命令。产物重跑覆盖、只留最新一轮，历史失败现场看报告的修复记录；产物与报告一律脱敏，明文凭据只存 `tests/.env.local`。

**手动执行的版本（`N-MANUAL.md`）走闸门制**：先只读校验你贴的代码 → 把差异汇总成一份清单让你确认一次（默认全部按计划对齐，你可以挑出想保留的写法）→ 确认后就和常规模式一样全自动闭环验证。你选「保持现状」的写法会记进 `## 约束` 受保护，后续修 bug 不会被改回去；你选「跳过、我自己改」的条目 AI 绝不代劳。

### /xz-planning:xz-done N 或 /xz-planning:xz-done all

归档版本（纯文件操作，不涉及 git）。

- **`N`** — 归档单个版本。要过三道闸门：`待手动执行` 不许归档、`待闭环测试` 需明确确认、有未完成条目会警告并询问是否强制
- **`all`** — 把 `phases/` 下全部版本强制归档，跳过上面三道闸门。**但会先列出清单让你确认一次**（进度、状态、哪些没做完都摆出来），确认后才移动。`phases/` 下不符合 `N.名称` 格式的目录原样保留不动

### /xz-planning:xz-status

展示所有版本进度的可视化总览和 STATE.md 表格。

### /xz-planning:xz-review N

审查版本 N 的 todolist 改动。检查符合性、安全、性能、质量。

### /xz-planning:xz-eli5 内容 [讲给谁听]

把任何话题、代码、概念、报错按指定听众的理解水平讲明白。听众可以是年龄档（五岁 / 十岁 / 40 岁往上）、学段（小学五年级 / 大学生 / 研究生）、职场角色（经理 / 工程师 / 产品经理 / 老板）或家里人（老婆 / 爸妈 / 小孩）。不指定就默认按五岁小孩讲。

用户说「讲人话」「掰开揉碎讲讲」「解释给我妈听」这类话时也会自动触发。

### /xz-planning:xz-del N

删除单个版本的计划目录，需确认。

### /xz-planning:xz-remove-all

交互式清理全部计划数据。

## 辅助脚本

`xz-tools.py` 位于插件的 `bin/` 目录，插件启用时自动加入 PATH：

```bash
xz-tools.py init          # 初始化目录
xz-tools.py status        # 输出 JSON 状态
xz-tools.py parse N       # 解析版本 N 的 PLAN
xz-tools.py update-state  # 刷新 STATE.md
xz-tools.py complete N    # 归档版本 N
xz-tools.py delete N      # 删除版本 N
xz-tools.py remove-all    # 交互式清理
xz-tools.py plugin-root   # 输出插件根目录路径
xz-tools.py skill-dir N   # 输出 skill N 的目录路径
xz-tools.py get-readme    # 输出 README 模板内容
```

## 设计原则

- **初始化先行** — 使用前必须 `/xz-planning:xz-init`，确保目录结构就绪
- **方案先出** — 禁止需求模糊就动手，先对齐再干活
- **先展示后写文件** — 所有计划/修改必须确认后才落盘
- **已完成锁定** — `[x]` 条目不可修改删除
- **不碰 git** — 所有操作均为纯文件操作，不执行任何 git 命令
- **原子化执行** — 每条 todo 独立完成，逐条推进
- **状态可追溯** — STATE.md 实时反映所有版本进度
