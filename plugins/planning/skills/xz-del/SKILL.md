---
name: xz-del
description: 删除单个版本 N 的计划目录并更新 STATE.md。/xz-del N
disable-model-invocation: true
argument-hint: "[N]"
---

# XZ Del - 删除版本计划

删除版本号: `$ARGUMENTS`

### 参数校验

如果 `$ARGUMENTS` 为空或不是合法版本号（正整数，或小数如 1.5），**立即停止**，提示：

> 缺少版本号。用法: `/xz-del N`
> 示例: `/xz-del 1`

## 辅助脚本

**脚本**：`xz-tools.py`

插件启用时 `bin/` 目录自动加入 PATH，直接作为命令调用即可（不需要 `python3` 前缀，也不需要绝对路径）。脚本在**当前工作目录**下操作 `.xz_planning/`。

---

## 执行流程

### 第一步：检查目标

```bash
xz-tools.py parse $ARGUMENTS
```

如果版本不存在，提示错误并退出。

### 第二步：展示将要删除的内容

读取 N-PLAN.md 内容，展示摘要：
- 版本号和需求名
- todolist 完成进度
- 涉及的文件列表

### 第三步：确认删除

以纯文本提问确认删除（禁用 AskUserQuestion，其弹窗会吞掉同回复中前面的版本信息文本）：

> 即将永久删除版本 N: {需求名}（{完成进度}）。此操作不可恢复。回复：
>   1) 确认删除 — 永久删除该版本的全部计划文件
>   2) 取消 — 保留当前计划

回复「取消」则停止操作；「确认删除」进入第四步；其他输入按内容响应。

### 第四步：执行删除

```bash
xz-tools.py delete $ARGUMENTS
```

该脚本会：
- 删除 `.xz_planning/phases/N.xxx/` 整个目录
- 自动重建 STATE.md

### 第五步：输出结果

以纯文本显示删除完成信息和下一步选项：

> 版本 N 已删除。下一步: /xz-status（查看所有版本状态）/ /xz-plan N（创建新版本计划）

用户回复后执行对应的 skill 命令。
