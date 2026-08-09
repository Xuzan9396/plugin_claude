# XZ Planning - 轻量级版本计划驱动开发

init → discuss? → plan → exec(含闭环测试) ⇄ update-plan? → review? → done

辅助: status / ref / test / del / remove-all

基于 todolist 的开发流程管理工具，通过 Claude Code 插件驱动。

## 命令一览

**核心流程：**

| 命令 | 用途 | 必须 | 示例 |
|------|------|:----:|------|
| `/xz-planning:xz-init` | 初始化当前项目的计划目录 | ✅ | `/xz-planning:xz-init` |
| `/xz-planning:xz-discuss N 讨论内容` | PM × Dev 头脑风暴，收敛想法 | 可选 | `/xz-planning:xz-discuss 1 做个客户管理工具` |
| `/xz-planning:xz-plan N 需求描述` | 创建新版本计划 | ✅ | `/xz-planning:xz-plan 1 实现用户注册登录` |
| `/xz-planning:xz-update-plan N 操作` | 修改/新增/删除 todolist 条目 | 可选 | `/xz-planning:xz-update-plan 1 修改 #3 增加缓存` |
| `/xz-planning:xz-exec N` | 执行未完成的 todolist + 完成后自动闭环测试 | ✅ | `/xz-planning:xz-exec 1` |
| `/xz-planning:xz-review N` | 审查版本 N 的代码质量和安全 | 可选 | `/xz-planning:xz-review 1` |
| `/xz-planning:xz-done N` | 归档已完成的版本 | ✅ | `/xz-planning:xz-done 1` |

**辅助工具：**

| 命令 | 用途 | 示例 |
|------|------|------|
| `/xz-planning:xz-status` | 查看所有版本状态总览 | `/xz-planning:xz-status` |
| `/xz-planning:xz-status N` | 查看版本 N 的详细进度 | `/xz-planning:xz-status 1` |
| `/xz-planning:xz-ref N` 或 `/xz-planning:xz-ref N1,N2` | 加载计划到上下文供参考 | `/xz-planning:xz-ref 1,2` |
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
│   ├── xz-discuss/
│   │   ├── SKILL.md
│   │   ├── visual-companion.md
│   │   ├── agents/             # skill 内部角色定义
│   │   └── scripts/            # 可视化服务脚本
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
│   │   └── tests/              # 无测试框架时的临时测试脚本
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

PM × Dev 头脑风暴工具，把粗糙想法收敛为结构化讨论文档。**不是必须步骤**，可以跳过直接 `/xz-planning:xz-plan`。

输出 `N-DISCUSS.md`，包含：目标用户、核心问题、功能方向（价值/复杂度/MVP 标记）、产品方案、技术边界（Dev 视角）、MVP 收敛（Must/Should/Later）、风险与待确认。

确认后写入文件。后续 `/xz-planning:xz-plan` 会自动引用同目录下的 `N-DISCUSS.md`。

### /xz-planning:xz-plan N 需求描述

创建新版本计划。要求项目已初始化。如果同目录存在 `N-DISCUSS.md`，自动引用。

每条 todolist 包含 `改动详情`，明确写出新建/修改哪些文件。

生成后先展示草案，你确认后才写入文件。如果版本已存在会拒绝，提示用 `/xz-planning:xz-update-plan`。

确认时可选**手动执行**路径：额外生成 `N-MANUAL.md`（改动地图 + 逐块 `改动 i/n` 进度 + 复制即用的代码块），你自己贴码、掌握代码写到哪儿了；贴完跑 `/xz-planning:xz-exec N` 校验差异并自动闭环验证。

### /xz-planning:xz-update-plan N 操作描述

修改已有版本的 todolist。支持修改、新增、删除、插入条目。已完成的 `[x]` 条目受锁定保护，不可修改或删除。

### /xz-planning:xz-exec N

从第一个未完成的 `[ ]` 条目开始，按 改动详情 逐条执行代码编写/修改。

**todolist 全部完成后自动进入闭环测试**：按 `N-PLAN.md` 的 `## 测试方案` 逐条跑自动化用例（单测/接口/CLI/浏览器），失败就分诊——计划内实现 bug 直接修，用例或环境问题修用例，越界项停下报告；每轮修完**全量回归**，最多 3 轮。每修一处会在终端打印 `文件:行号 + 原因 + 改前/改后`，改了哪儿一目了然。只有真实凭证、线上环境、真机硬件、多端多人、破坏性操作、主观视觉确认这类 AI 客观做不到的事，才会停下来向你索取。结果写入 `N-TEST-REPORT.md`。

**手动执行的版本（`N-MANUAL.md`）走闸门制**：先只读校验你贴的代码 → 把差异汇总成一份清单让你确认一次（默认全部按计划对齐，你可以挑出想保留的写法）→ 确认后就和常规模式一样全自动闭环验证。你选「保持现状」的写法会记进 `## 约束` 受保护，后续修 bug 不会被改回去；你选「跳过、我自己改」的条目 AI 绝不代劳。

### /xz-planning:xz-done N

归档版本（纯文件操作，不涉及 git）。

### /xz-planning:xz-status

展示所有版本进度的可视化总览和 STATE.md 表格。

### /xz-planning:xz-review N

审查版本 N 的 todolist 改动。检查符合性、安全、性能、质量。

### /xz-planning:xz-ref N 或 /xz-planning:xz-ref N1,N2,N3

加载一个或多个版本的 PLAN.md 到当前对话上下文。

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
