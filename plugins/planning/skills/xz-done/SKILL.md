---
name: xz-done
description: 归档版本 N 的计划（纯文件操作，不执行 git）。/xz-done N
disable-model-invocation: true
argument-hint: "[N]"
---

# XZ Done - 归档版本计划

归档版本号: `$ARGUMENTS`

### 参数校验

如果 `$ARGUMENTS` 为空或不是正整数，**立即停止**，提示：

> 缺少版本号。用法: `/xz-done N`
> 示例: `/xz-done 1`

## 辅助脚本

**脚本**：`xz-tools.py`

插件启用时 `bin/` 目录自动加入 PATH，直接作为命令调用即可（不需要 `python3` 前缀，也不需要绝对路径）。脚本在**当前工作目录**下操作 `.xz_planning/`。

---

## 执行流程

### 第一步：检查状态

```bash
xz-tools.py parse $ARGUMENTS
```

检查版本 N 是否存在，以及 todolist 完成情况。

### 第二步：判断是否可归档

- **全部 `[x]`** → 直接进入归档流程
- **存在 `[ ]`** → 使用 AskUserQuestion 工具警告并让用户选择：

  - question: "版本 N 还有 X 条未完成任务。如何处理？"
  - header: "未完成警告"
  - options:
    - label: "强制归档", description: "忽略未完成条目，直接归档"
    - label: "返回继续执行", description: "执行 /xz-exec N 完成剩余任务"
  - multiSelect: false

  用户选择「返回继续执行」则停止归档。选择「强制归档」则继续。如果用户选择 Other，按其输入内容响应。

### 第三步：执行归档

运行辅助脚本（纯文件移动，不涉及任何 git 操作）：

```bash
xz-tools.py complete $ARGUMENTS
```

该脚本会：
- 将 `.xz_planning/phases/N.xxx/` 移动到 `.xz_planning/archive/N.xxx/`
- 自动重建 STATE.md

### 第四步：记录归档时间

**获取当前时间：**

```bash
date "+%Y-%m-%d %H:%M:%S"
```

归档前在 N-PLAN.md 的变更记录中追加精确时间：

```
- YYYY-MM-DD HH:mm:ss 归档完成
```

同时更新 `> 最后更新:` 为当前精确时间。

### 第五步：输出归档结果

显示归档摘要：版本号、需求名称、完成条数、归档时间。

然后使用 AskUserQuestion 工具让用户选择下一步操作：

- question: "版本 N 已归档。接下来要做什么？"
- header: "下一步"
- options:
  - label: "/xz-status", description: "查看所有版本状态"
  - label: "/xz-plan N", description: "创建新版本计划"
- multiSelect: false

用户选择后，执行对应的 skill 命令。如果用户选择 Other，按其输入内容响应。

## 关键规则

1. **不执行任何 git 操作** — 只做文件移动和 STATE 更新
2. **未完成需确认** — 有 `[ ]` 条目时必须警告并等待确认
3. **归档时间精确** — 变更记录和 STATE.md 中的完成时间精确到时分秒
