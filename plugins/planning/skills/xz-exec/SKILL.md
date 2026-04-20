---
name: xz-exec
description: 执行版本 N 中未完成的 todolist。/xz-exec N
disable-model-invocation: false
argument-hint: "[N]"
---

# XZ Exec - 执行版本计划

执行版本号: `$ARGUMENTS`

### 参数校验

如果 `$ARGUMENTS` 为空或不是正整数，**立即停止**，提示：

> 缺少版本号。用法: `/xz-exec N`
> 示例: `/xz-exec 1`

## 辅助脚本

**脚本**：`xz-tools.py`

插件启用时 `bin/` 目录自动加入 PATH，直接作为命令调用即可（不需要 `python3` 前缀，也不需要绝对路径）。脚本在**当前工作目录**下操作 `.xz_planning/`。

---

## 执行流程

### 第一步：读取项目上下文

读取 `.xz_planning/PROJECT.md`（如果存在），了解项目技术栈和目录结构。

### 第二步：解析并读取计划

```bash
xz-tools.py parse $ARGUMENTS
```

- 从返回 JSON 中取 `phase.plan_file` 路径，读取 N-PLAN.md 完整内容
- 版本不存在 → 提示用户先运行 `/xz-plan N`

### 第三步：评估当前状态

检查 todolist 中已完成（`[x]`）和未完成（`[ ]`）的条目，找到第一个未完成条目。

- **没有未完成条目** → 提示全部完成，建议运行 `/xz-done N`
- **有已完成条目 + 有未完成条目（中途接手）** → 进入接续评估（见下方）
- **全部未完成（从头开始）** → 直接进入第四步执行

#### 接续评估（中途接手时必须执行）

上一个 AI 可能已经执行了部分任务，当前代码状态未必和计划完全吻合。必须先评估再继续：

1. **读取最近已完成条目的 change details** — 了解上一步应该做了什么
2. **检查实际代码** — 用 Read 工具查看这些条目涉及的文件，确认改动是否真的落地
3. **判断偏差程度：**

| 情况 | 操作 |
|------|------|
| 已完成条目的改动已正确落地，代码与 change details 一致 | 正常继续，进入第四步 |
| 有小幅偏差但不影响后续任务（如变量名略不同、多了注释） | 记录偏差，适配后续执行，进入第四步 |
| 已完成条目的改动未落地（标了完成但代码没改） | **停下来报告用户**，说明哪些条目标记完成但实际未执行，然后用 AskUserQuestion 让用户决定。question: "以下条目标记完成但实际未执行: {列表}。如何处理？" options: "重新执行这些条目" / "跳过继续后续" |
| 已完成的改动与 change details 偏差较大（用了不同方案、改了不同文件、结构重组） | **停下来报告用户**，列出具体偏差点，然后用 AskUserQuestion 让用户决定。question: "已完成改动与计划偏差较大: {偏差点摘要}。如何处理？" options: "回退重做 — 按原计划执行" / "基于现状调整 — /xz-update-plan N" |

### 第四步：执行任务

根据 change details 中描述的具体改动：

1. 读取需要修改的现有文件
2. 按描述执行代码编写/修改
3. 确保改动符合 change details 的描述
4. **语法检查** — 改动完成后，用项目对应的方式快速验证语法：
   - Python: `python3 -c "import ast; ast.parse(open('文件路径').read())"`
   - JS/TS: 项目有 lint 命令则运行，否则检查文件是否有明显语法错误
   - 其他语言: 用对应编译器/解释器做语法级检查
   - 语法不通过 → **立即修复**，修复后再标记完成

### 第五步：标记完成

**获取当前时间：**

```bash
date "+%Y-%m-%d %H:%M:%S"
```

1. 将该条目的 `[ ]` 改为 `[x]`
2. 更新 N-PLAN.md 文件（使用 `phase.plan_file` 路径）：
   - 更新 `> 最后更新:` 为当前精确时间 `YYYY-MM-DD HH:mm:ss`
   - 在变更记录追加 `- YYYY-MM-DD HH:mm:ss 完成 #N 任务标题`
3. 刷新 STATE.md：

```bash
xz-tools.py update-state
```

### 第六步：循环或结束

检查是否还有下一个 `[ ]` 条目：

- **有** → 回到第四步继续执行
- **无** → 全部完成，输出下一步建议：

**全部完成时：** 使用 AskUserQuestion 工具让用户选择下一步操作：

- question: "版本 N 的 todolist 已全部完成。接下来要做什么？"
- header: "下一步"
- options:
  - label: "/xz-review N", description: "代码审查（可选）"
  - label: "/xz-test N", description: "生成测试指南（可选）"
  - label: "/xz-done N", description: "归档版本"
- multiSelect: false

**中途停止时（用户主动中断或遇阻）：** 使用 AskUserQuestion 工具让用户选择下一步操作：

- question: "已完成 X/Y 条，还剩 Z 条未执行。接下来要做什么？"
- header: "下一步"
- options:
  - label: "/xz-exec N", description: "继续执行剩余条目"
  - label: "/xz-update-plan N", description: "修改/新增/删除 todolist 条目"
- multiSelect: false

用户选择后，执行对应的 skill 命令。如果用户选择 Other，按其输入内容响应。

---

## 关键规则

1. **按顺序执行** — 从第一个 `[ ]` 开始，逐条完成
2. **不操作 git** — 不执行任何 git 命令
3. **严格按 change details** — 改动范围以 details 描述为准
4. **用 parse 返回的路径** — 不要猜测文件位置，用脚本返回的 `phase.plan_file` 绝对路径
5. **更新进度** — 每完成一条都更新 PLAN.md 和 STATE.md
6. **最后整理改动结果** — 全部完成后输出本次改动点汇总
7. **只做计划内的事** — 严禁做 change details 之外的改动，即使觉得"顺手改了更好"也不行；发现计划有遗漏，停下来告知用户，由用户决定是否通过 `/xz-update-plan` 补充
8. **遇阻停下问人** — change details 与实际文件不符、依赖缺失、指令含糊到无法确定改什么时，立即停止报告用户，禁止猜测或自行创造解法
9. **模糊先查 PLAN** — change details 描述不够具体时，先回头读 `## 需求描述`（用户原话 + 我的理解）和 `## 用户资料与引用` 两个章节，大概率能消除歧义；仍不清楚再按规则 8 停下问人
10. **语法必须通过** — 每条任务执行后做语法检查，不通过不标完成
11. **中途接手先评估** — 有已完成条目时，先检查实际代码与 change details 的一致性，偏差大则报告用户等决定
