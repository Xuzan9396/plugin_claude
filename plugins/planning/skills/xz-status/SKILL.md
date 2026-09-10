---
name: xz-status
description: 查看当前所有版本的计划状态总览。/xz-status
disable-model-invocation: true
---

# XZ Status - 查看计划状态

## 辅助脚本

**脚本**：`xz-tools.py`

插件启用时 `bin/` 目录自动加入 PATH，直接作为命令调用即可（不需要 `python3` 前缀，也不需要绝对路径）。脚本在**当前工作目录**下操作 `.xz_planning/`。

---

## 执行流程

### 第一步：获取状态

```bash
xz-tools.py status
```

### 第二步：格式化输出

根据返回的 JSON 数据，输出可视化状态：

```
XZ Planning Status

🚧 活跃版本:
  [1] 用户注册登录    ███░░░ 2/4 (50%)
  [2] 商品管理模块    ░░░░░░ 0/3 (0%)

✅ 已归档:
  [0] 项目初始化      4/4 (100%)  2026-03-12

💡 下一步: /xz-exec 1
```

如果 `.xz_planning` 不存在，提示：

```
XZ Planning 未初始化。运行 /xz-plan N 需求描述 开始第一个计划。
```

### 第三步：读取 STATE.md

同时读取并展示 `.xz_planning/STATE.md` 的完整内容，让用户看到表格形式的状态。

### 第四步：worktree 残留检查

`xz-tools.py status` 的 JSON **没有 worktree 字段**，所以这一步必须自己扫：Glob `.xz_planning/phases/*/worktree/*.handoff.json`，逐条读出 `integration` / `worktree_path` / 组名。

凡 `integration` 不是 `applied`、或 `worktree_path` 目录仍存在的，在输出**末尾**加一段警示：

```
⚠️ 版本 1.5 有 2 组 worktree 未收尾：
  api-层     conflict     ../worktree/myrepo/api-层-a1b2c3
  dao-层     preserved    ../worktree/myrepo/dao-层-d4e5f6

跑 xz-tools.py wt list 1.5 看详情、xz-tools.py wt clean 1.5 收掉。
归档或删除版本前务必先清，否则工具再也定位不到现场。
```

没有 handoff、或全部 `applied` 且现场目录已清 → 不输出这段，也不要写「无残留」占版面。

## 输出规则

1. **进度条可视化** — 用 █ 和 ░ 表示完成比例
2. **给出下一步建议** — 如有进行中的版本，建议 `/xz-exec N`
3. **同时展示 STATE.md** — 表格和可视化两种形式都展示
4. **worktree 残留必须报** — 有未收尾的现场就在输出末尾列出组名 / 状态 / 现场路径，并提示 `wt list` / `wt clean`；这是全仓层面唯一能看到残留的地方，漏报会让 worktree 目录和 `xz-worktree/*` 分支静默累积
