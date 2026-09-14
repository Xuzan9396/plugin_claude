---
name: xz-worktree
description: 管理并行开发用的 Git worktree——创建（含复刻忽略文件）、查看、合并回主分支、删除。/xz-planning:xz-worktree <名称> | list | status <名称> | merge <名称> | rm <名称>
disable-model-invocation: true
argument-hint: "<名称> | list | status <名称> | merge <名称> | rm <名称>"
---

# XZ Worktree - 并行工作区

在仓库同级开独立工作区，各自一个分支、互不打扰，完事再合并回来。

参数 `$ARGUMENTS`：`$0` 是动作或名称。

| 输入 | 动作 |
|------|------|
| `<名称>` | 创建工作区（`$0` 不是下面的保留词时一律当名称） |
| `list` | 列出全部工作区 |
| `status <名称>` | 看单个工作区的详情与合并预检 |
| `merge <名称>` | 合并回基础分支 |
| `rm <名称>` | 删除工作区和它的分支 |

`$ARGUMENTS` 为空 → 停止，提示 `用法: /xz-planning:xz-worktree <名称> | list | status <名称> | merge <名称> | rm <名称>`。

---

## 辅助脚本

**脚本**：`xz-tools.py`

插件启用时 `bin/` 目录自动加入 PATH，直接作为命令调用即可（不需要 `python3` 前缀，也不需要绝对路径）。脚本在**当前工作目录**下操作 `.xz_planning/`。

---

## 前置检查

任何动作之前，配置必须存在。脚本返回 `未找到 .xz_planning/worktree/setting.json` → 停止，提示 `请先执行 /xz-planning:xz-worktree-init`。

---

## 创建

### 第一步：看当前分支的提交情况

```bash
xz-tools.py wt-scan
```

`dirty` 非空 → **先把改动列给用户，再问怎么办**。新工作区从基础分支拉，这些未提交的改动不会跟过去。

**禁用 AskUserQuestion——它的弹窗会吞掉同一条回复里前面的文本，用户就看不到你列出的改动清单了。** 用纯文本问：

```
当前分支 feature-x 有 3 处未提交改动：

  M  src/api.go
  M  README.md
  ?? .env.local

新工作区从 main 拉，这些改动会留在当前仓库、不跟过去。

  1) 照建，改动留在这儿
  2) 我先去提交，本次取消
  3) 取消
```

`dirty` 为空 → 跳过提问，直接建。

### 第二步：创建

```bash
xz-tools.py wt-create <名称>
```

要从别的分支或提交拉，加 `--base <ref>`（省略则用配置里的基础分支）。

名称规则：字母或数字开头，1~40 位，只许字母数字和 `.` `_` `-`。

### 第三步：报告

```
工作区已就绪

  路径    ../.xz_worktrees/myrepo-feat-api
  分支    xz/feat-api（从 main @ a1b2c3d4）
  复刻    .env (copy)、.xz_planning (copy)、node_modules (link)
  跳过    venv（源不存在）
  初始化  npm install ✅

  cd ../.xz_worktrees/myrepo-feat-api
```

- `replicate_errors` 非空 → 逐条列出来，别吞掉；工作区本身可用，但缺的东西要让用户知道
- `post_create` 里有非零退出码 → 明确说哪条命令失败了并贴出输出末尾，后续命令已中止

---

## 列表

```bash
xz-tools.py wt-list
```

渲染成表格，主仓库标出来，受管工作区（`managed: true`）排在前面：

```
XZ Worktree（基础分支 main）

  名称        分支            改动  未跟踪  领先  落后  路径
  feat-api    xz/feat-api      0     2      3     0    ../.xz_worktrees/myrepo-feat-api
  fix-login   xz/fix-login     1     0      1     5    ../.xz_worktrees/myrepo-fix-login
  （主仓库）   main             0     1      -     -    .

  领先 = 有几个提交还没合回 main；落后 = main 比它多几个提交
```

`exists: false` 的条目标成「目录已丢失」，提示用 `rm` 清理登记。

---

## 查看

```bash
xz-tools.py wt-status <名称>
```

展示路径、分支、领先/落后、改动清单，以及 `can_merge` 和 `blockers`。不可合并时把 `blockers` 逐条列出。

---

## 合并

**这是唯一会改动主仓库的动作，先预检、让用户确认，再执行。**

### 第一步：预检

```bash
xz-tools.py wt-status <名称>
```

`can_merge: false` → 停止，列出 `blockers`（工作区有未提交改动、主仓库有未提交改动、基础分支不存在等），说明各自怎么解决。

### 第二步：确认

纯文本展示将要发生什么，等用户确认：

```
准备合并 xz/feat-api → main

  合并 3 个提交
  策略  rebase-ff（先在工作区 rebase main，再快进合并）
  合并后自动删掉工作区和分支
  主仓库当前在 feature-x 分支，合并完会切回来

确认执行？
```

`untracked` 非空时补一句：「工作区里有 N 个未跟踪文件，它们进不了提交，所以合并后不会自动删工作区。」

### 第三步：执行

```bash
xz-tools.py wt-merge <名称>
```

- `--keep` — 合并后保留工作区（用户说要接着用时加）
- `--no-ff` — 本次改用 merge-commit 策略，保留合并节点

脚本内部按「预检 → 加锁 → rebase → 切分支 → 合并 → 清理 → 切回原分支」执行。合并锁保证多个工作区不会同时往主仓库合。

### 第四步：报告结果

**成功：**

```
已合并 xz/feat-api → main（3 个提交，rebase-ff）

  ✅ 工作区和分支已清理
  ✅ 主仓库已切回 feature-x
```

`cleaned: false` 时把 `kept_reason` 说明白；`cleanup_errors` 非空则逐条列出。

**rebase 冲突：** 主仓库一点没动，冲突现场留在工作区里等人处理。原样转述 `conflicts` 和 `hint`：

```
rebase 遇到冲突，主仓库未受影响。

  冲突文件：src/api.go、config.yaml

  cd ../.xz_worktrees/myrepo-feat-api
  # 解决冲突后 git rebase --continue（放弃则 git rebase --abort）

处理完重跑 /xz-planning:xz-worktree merge feat-api
```

**合并失败：** 主仓库已自动回到合并前的状态，转述 `detail` 和 `hint`。

---

## 删除

```bash
xz-tools.py wt-remove <名称>
```

被拒时（有未提交改动、有未跟踪文件、有提交没合回基础分支）**原样转述 `blockers`**，并给出选择：

```
不能删 feat-api：

  有 2 个提交尚未合并到 main
  有 1 个未跟踪文件会被删掉：?? notes.md

  1) 先合并：/xz-planning:xz-worktree merge feat-api
  2) 确实不要了，强制删除（这些内容会永久丢失）
```

**只有用户明确说要强制**，才加 `--force` 重跑。不要自作主张强制删除。

---

## 关键规则

1. **不替用户做 git 写操作** — 本命令不 commit、不 stash、不切分支（合并时的切换除外，且会自动切回）。发现未提交改动一律先问。
2. **强制删除必须用户点头** — `--force` 会永久丢数据，任何情况下都不能自己加。
3. **合并失败时原样转述** — 冲突文件清单、脚本给的 `hint`，一个字都不要改写或省略，那是用户接着操作的依据。
4. **别吞错误** — `replicate_errors`、`cleanup_errors`、非零的 `post_create` 都要报出来，哪怕主流程成功了。
5. **软链是共用的** — 配置里 `mode: link` 的目录两边指向同一份，在工作区里改它等于改主仓库的。用户问起时要讲清楚。
