---
name: xz-worktree-init
description: 初始化或修改当前项目的 Git worktree 配置——基础分支、存放目录、合并策略、以及要复刻到新工作区的忽略文件。/xz-worktree-init [基础分支]
disable-model-invocation: true
argument-hint: "[基础分支]"
---

# XZ Worktree Init - 配置并行工作区

给当前项目写 `.xz_planning/worktree/setting.json`，供 `/xz-worktree` 建工作区时使用。

**可重复执行：** 已有配置时进入修改模式，展示当前值、只改用户点名的项，其余原样保留。

参数 `$ARGUMENTS`（可选）：指定基础分支，省略则默认当前分支。

---

## 辅助脚本

**脚本**：`xz-tools.py`

插件启用时 `bin/` 目录自动加入 PATH，直接作为命令调用即可（不需要 `python3` 前缀，也不需要绝对路径）。脚本在**当前工作目录**下操作 `.xz_planning/`。

---

## 执行流程

### 第一步：探测现状

```bash
xz-tools.py wt-scan
```

返回 JSON：

| 字段 | 含义 |
|------|------|
| `repo_root` / `branch` / `head` | 仓库根、当前分支、当前提交 |
| `ignored_candidates` | 顶层被 git 忽略且**实际存在**的条目。每条带 `type`、`size_kb`，以及自动判断出的 `suggested_mode` / `recommended` / `reason` |
| `planning_ignored` | `.xz_planning/` 是否已被 git 忽略 |
| `exclude_file` | `.git/info/exclude` 的路径（主 checkout 与所有 worktree 共享） |
| `config_exists` / `config` | 已有配置及其内容 |
| `defaults` | 各字段的默认值 |

`ok:false` → 停止，把 `error` 原样告诉用户（常见是当前目录不在 git 仓库里）。

### 第二步：判断模式

- `config_exists: false` → **首次初始化**，各项默认值取 `defaults`，基础分支默认取 `branch`（或 `$ARGUMENTS` 指定的）
- `config_exists: true` → **修改模式**，先原样展示当前配置，各项默认值取现有值

### 第三步：提问

**禁用 AskUserQuestion——它的弹窗会吞掉同一条回复里前面的文本，用户就看不到你列出的候选清单了。** 用纯文本一次把问题列全，让用户一次答完。

`ignored_candidates` 里每条**已经带了判断结果**：`suggested_mode`（`copy` / `link` / `skip`）、`recommended`（是否默认勾选）、`reason`（一句话理由）、`size_kb`（体积，探测超时为 `null`）。

**直接用这些值，不要自己另行判断。** 规则在脚本里统一维护，三端一致：

| 建议 | 含义 | 典型 |
|------|------|------|
| `link` | 内容由锁文件确定、构建时只读，共用无害 | `node_modules`、`vendor`、`Pods` |
| `copy` | 各自要独立一份，共用会互相干扰 | `.env`、`.xz_planning`、`*.sqlite3` |
| `skip` | 不该复刻 | 构建产物（`dist`/`target`/`.next`）、虚拟环境（`venv`） |

`skip` 项**也要展示**（让用户知道工具看见了它们），但单独列在下方、默认不勾。体积把 `size_kb` 换算成人类可读，`null` 就省略这一列。

```
XZ Worktree 配置（直接回车 = 全用默认；要改就写编号，如 `1 develop` `5 1 2 4`）

  1. 基础分支        [main]              新工作区从它拉，也合并回它
  2. 存放目录        [../.xz_worktrees]  相对项目根；放在仓库同级，免得被项目自身扫描
  3. 合并策略        [rebase-ff]         先 rebase 再快进合并，历史线性
                                         另一选项 merge-commit：保留合并节点
  4. 合并后自动清理   [是]                删掉工作区目录和已合并的分支
  5. 复刻到新工作区的文件（这些被 git 忽略，不会自己跟过去）：

       [1] .env           文件    4K   copy   本地环境变量，各自一份
       [2] .xz_planning   目录   120K  copy   不带上它，新工作区里用不了计划流程
       [3] node_modules   目录   412M  link   依赖树只读，软链省一次安装
       [4] vendor         目录    88M  link   依赖由锁文件确定，只读

     ── 以下不建议复刻 ──
       [5] dist           目录    12M  构建产物，两个工作区共用会互相覆盖
       [6] venv           目录   180M  内含绝对路径，搬过去会指回原目录
       [7] target         目录   1.2G  两边的编译会互相打架

     默认勾选 1 2 3 4。回编号改选择，如 `1 2`；要改方式写 `3:copy`。
  6. 创建后执行的命令 [无]                如 npm install、go mod download
```

用户坚持要复刻某个 `skip` 项 → 照办，但把它的 `reason` 复述一遍，让他知道代价。

修改模式下把 `[默认值]` 换成当前配置的值，并在开头说明「以下是当前配置，回车保留」。

### 第四步：写入配置

把答案合成完整 JSON 从 stdin 喂给脚本（它会校验后覆盖写入，字段缺失自动补默认值）：

```bash
xz-tools.py wt-config-write <<'JSON'
{
  "baseBranch": "main",
  "branchPrefix": "xz/",
  "worktreeParent": "../.xz_worktrees",
  "mergeStrategy": "rebase-ff",
  "cleanupAfterMerge": true,
  "replicate": [
    { "path": ".env", "mode": "copy" },
    { "path": ".xz_planning", "mode": "copy" }
  ],
  "postCreate": []
}
JSON
```

返回 `ok:false` 时 `details` 里是逐条错误，按错误修正后重写，不要跳过。

### 第五步：确认 `.xz_planning/` 已被忽略

`planning_ignored` 为 `false` 时提醒用户——这个目录是本地计划数据，不该进版本库：

```
.xz_planning/ 还没被 git 忽略。建议加到 .git/info/exclude（本地生效，不动仓库里的 .gitignore）：

  echo '.xz_planning/' >> <exclude_file 的值>

要我执行吗？
```

用户同意才执行，**不要擅自改**。追加前先确认文件里没有重复行。

### 第六步：输出摘要

```
XZ Worktree 配置完成 → .xz_planning/worktree/setting.json

  基础分支     main
  存放目录     ../.xz_worktrees
  分支前缀     xz/
  合并策略     rebase-ff（合并后自动清理）
  复刻         .env (copy)、.xz_planning (copy)、node_modules (link)
  创建后执行   npm install

下一步: /xz-worktree <名称> 建一个并行工作区
```

修改模式下额外标出改了哪几项。

---

## 关键规则

1. **一次问完** — 把所有问题列在一条消息里，别一问一答来回磨。
2. **候选和建议都只来自 `wt-scan`** — 不要凭空猜项目里有什么，也不要自己重新判断 copy/link，那些是脚本里统一维护的规则。
3. **`.xz_planning` 强烈建议复刻** — 否则新工作区里整套计划流程失效，默认就勾上它。
4. **link 的代价要说清** — 软链是两边共用同一份。判据是「共用会不会出事」，不是「大不大」：依赖目录只读所以能共用，构建产物共用会互相覆盖。用户在工作区里 `npm install` 装新包，主仓库那份也会跟着变——这点要讲明白。
5. **配置不入库** — `.xz_planning/` 通常被忽略，每个协作者各自跑一次本命令。
6. **只写配置，不碰 git** — 本命令不创建任何工作区、不切分支；除第五步经用户同意的那一行 exclude 外，不改任何文件。
