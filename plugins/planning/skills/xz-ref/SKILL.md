---
name: xz-ref
description: 引用已有版本计划作为参考上下文（只读，phases/ 与 archive/ 两个目录都查）。可在版本号后跟一句问题。/xz-ref N 或 /xz-ref N 你的问题
disable-model-invocation: true
argument-hint: "[N] 或 [N-M] / [N1,N2] [可选问题]"
---

# XZ Ref - 引用版本计划当参考

参数 `$ARGUMENTS`：**第一个空格前**是版本表达式，其后全部是**可选问题**。

- `/xz-ref 1.2` → 引用版本 1.2，输出摘要
- `/xz-ref 1.2 软删除当时为什么没用布尔列` → 引用后直接回答这个问题
- `/xz-ref 1,1.2` / `/xz-ref 1-1.2` → 一次引用多个

为空 → 停止，提示 `用法: /xz-ref N [问题]`。**版本表达式内不许有空格**：写成 `1, 1.2` 会把 `1.2` 当成问题，遇到第一个 token 以 `,` 或 `-` 结尾就停下，提示改写成 `1,1.2`。

**脚本**：`xz-tools.py`（`bin/` 已在 PATH，直接调用，在当前目录操作 `.xz_planning/`）。

---

## 去哪儿找这个计划（本 skill 的核心）

**同一个版本的计划目录有两个可能的落点，两处都要查、找到即用：**

| 目录 | 什么时候在这儿 | 摘要里标 |
|---|---|---|
| `.xz_planning/phases/N.中文名/` | 还没归档（待执行 / 进行中 / 待闭环测试 / 待手动执行） | `活跃` |
| `.xz_planning/archive/N.中文名/` | 已经跑过 `/xz-done N` 归档 | `归档` |

实现只有一条命令：

```bash
xz-tools.py parse N --include-archive
```

**`--include-archive` 是「连 archive 一起查」的开关，一次都不许省** —— 省了归档版本一律查不到，而参考旧版本时想引的往往正是已归档的那些。返回的 `phase.archived` 字段直接决定摘要里标「活跃」还是「归档」，`phase.dir` 是它的真实位置。

## 执行流程

**1. 解析版本表达式** — 按逗号拆 token：`A-B` 区间纳入所有 A ≤ v ≤ B 的现存版本（`1-1.2` 命中 `1`/`1.1`/`1.2`）；`A` 单个只精确命中（`1,1.2` 不带上 `1.1`）。取并集去重、按**数值**升序（`1 < 1.1 < 1.2 < 1.5 < 2 < 10`）。

**2. 定位版本** — 单个版本直接跑 `xz-tools.py parse N --include-archive`；含区间的先跑 `xz-tools.py status` 拿 `active` + `archived` 版本号套表达式过滤，再逐个 `parse`。

**3. 读计划** — 只读 `phase.plan_file` 指向的 `N-PLAN.md` **全文**。多个版本按版本号升序读。

> **只读这一个文件**：同目录的 `N-DISCUSS.md` / `N-TEST-REPORT.md` / `N-REVIEW.md` / `N-UAT.md` 和 `tests/` / `worktree/` 一律不读，`tests/.env.local` 更不许碰（里面是明文凭据），`worktree/*.patch` 是二进制 diff 原文、读了只会烧上下文。要看那些，用户会另外点名。

**4. 输出** — 按下面两个分支之一。

## 铁律：全程只读

**本 skill 内禁止任何写操作，一次都不行。** 它只是把旧计划搬进上下文，不改任何东西。

禁止：Edit / Write / NotebookEdit；任何改动状态的 Bash（`rm`、`mv`、`cp`、`mkdir`、`>` / `>>` 重定向、`git commit`、包管理器安装）；动 `.xz_planning/` 下的任何东西（**包括不许把「已引用 X」写进任何 PLAN**）。

允许：`Read`、`Grep`、`Glob`，以及只读的 `xz-tools.py parse` / `status`。

**用户在本次调用中改口说「那按 1.2 的做法改一下」→ 停下**，告诉他：参考已经载入，写计划请用 `/xz-plan`、改计划用 `/xz-update-plan`、直接改码用 `/xz-exec`，本 skill 不动手。

## 输出分支 A：没跟问题 → 摘要待命

每个引用到的版本给一块摘要：

```
已引用 版本 1.2: 订单表加软删除兼容取消流程（归档）

| 项 | 内容 |
|---|---|
| 位置 | .xz_planning/archive/1.2.订单表加软删除兼容取消流程/ |
| 状态 | 已完成（todo 5/5） |

技术方案：软删除走 deleted_at 时间戳，不加 is_deleted 布尔列
涉及文件：model/order.go、dao/order_dao.go、api/order.go

已作为参考上下文载入，接着说你要做什么。
```

摘要取自 PLAN 的 `## 目标` / `## 技术方案` / `## 任务清单`，加上 `parse` 返回的 `progress`。**不复述 todolist 全文** —— 全文已经在上下文里了，摘要只负责给个索引。

## 输出分支 B：跟了问题 → 直接回答

1. **第一句就是结论**，不铺垫、不复述问题。
2. **标明依据在 PLAN 的哪一段**（如 `（依据 1.2-PLAN.md 技术方案）`），方便用户回查。
3. **PLAN 里没写就说没写** —— 不猜，也不拿当前代码现状顶替 PLAN 原文。真要看代码现状，提醒用户那是 `/xz-ask` 的事。
4. 问题有歧义先追问一句，纯文本问 —— **禁用 AskUserQuestion，它的弹窗会吞掉同一条回复里前面的文本。**

## 异常处理

| 情况 | 怎么办 |
|---|---|
| 无 `.xz_planning/` | 停止，提示 `请先执行 /xz-init` |
| `parse` 返回 `ok:false`（版本不存在） | 提示跑 `/xz-status` 看有哪些版本 |
| 离散多个里某个不存在 | 记一句「跳过 N（不存在）」继续，**全都不存在**才停止 |
| 目录在但无 `N-PLAN.md` | 跳过并说明「版本 N 只有讨论稿、还没生成计划」（`parse` 会返回 `plan_exists:false`） |

## 下一步建议

摘要或回答之后以纯文本收尾：

> 下一步: 照着这份参考写新计划 `/xz-plan N 需求` / 改现有计划 `/xz-update-plan N 操作` / 继续问我关于版本 1.2 的事
