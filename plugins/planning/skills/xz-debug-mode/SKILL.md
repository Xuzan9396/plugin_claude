---
name: xz-debug-mode
description: 运行时探针调试模式——插入日志探针、收集运行时数据、基于证据定位并修复 bug。适用于可复现但原因不明的 bug、竞态条件、时序问题、性能/内存泄漏、回归问题等静态分析无法解决的场景。必须由用户手动调用。
argument-hint: [问题描述]
disable-model-invocation: true
---

# 运行时探针调试模式 (Debug Mode)

通过向代码插入日志探针、收集运行时数据、分析执行轨迹来定位并修复 bug。支持多语言。

## ⛔ 强制规则 —— 由检查点强制执行

**本 skill 使用检查点系统。必须在进入下一步前，逐字打印每个检查点标记。跳过任何一个检查点即视为整个调试会话无效。**

每个步骤结束时必须打印以下检查点（逐字，不可改写）：

- `✅ CHECKPOINT 0: 问题上下文已收集`
- `✅ CHECKPOINT 1: 探针计划已创建 — 共 N 个探针`
- `✅ CHECKPOINT 2: 日志收集器已启动`
- `✅ CHECKPOINT 3: 已在源码中插入 N 个探针`（必须调用 Edit 工具 N 次）
- `✅ CHECKPOINT 4: 已收集 N 条日志`
- `✅ CHECKPOINT 5: 已基于日志证据定位根因`
- `✅ CHECKPOINT 6: 已应用修复并通过探针验证`
- `✅ CHECKPOINT 7: 所有探针已清除，清理完成`

**硬性规则：**

1. 不得在未打印 CHECKPOINT 1-4 的情况下直接打印 CHECKPOINT 5
2. 不得在未引用具体日志条目作为证据的情况下提出修复方案
3. 第 3 步必须使用 Edit 工具真实修改源文件——脑内"规划"探针不算数
4. 第 5 步必须收集并读取真实日志输出——不得分析尚未收集的日志
5. 若静态分析已能明确看出问题，可以先尝试修复；但如果修复无效，必须先插入探针收集运行时证据，再做下一次修复。核心目的是运行时验证，不是猜测。

## 核心原则

1. **先理解，再插桩** —— 先读代码和错误信息，找到可疑区域，只在关键路径放探针
2. **最小侵入** —— 探针不得改变原有逻辑，只观察和记录
3. **闭环处理** —— 插桩 → 运行 → 收集 → 分析 → 修复 → 验证 → 清理

## 工作流

### Step 0: 问题分诊（Triage）—— 向用户收集上下文

在读任何代码之前，先通过有针对性的提问收集线索。**只问用户尚未说明的信息**——已在初始消息里提供的跳过。

可选问题（按需挑选）：

- **预期行为 vs 实际行为？**
- **如何复现？**（具体步骤、命令、操作）
- **稳定复现还是偶发？**
- **从什么时候开始出现？**（某次改动、部署、依赖升级之后？）
- **有错误信息或堆栈吗？**
- **已经尝试过什么？**

如果用户初始描述已经足够详细（含复现步骤、错误信息、预期 vs 实际），跳过本步，直接进入 Step 1。

打印：`✅ CHECKPOINT 0: 问题上下文已收集`

### Step 1: 理解问题并规划探针

1. 读相关代码，识别可疑区域
2. 形成 2-3 个假设
3. 为每个假设规划探针：哪个文件、哪一行、观察哪些变量
4. **根据运行环境确定日志策略**：
   - **CLI / 服务端 / 脚本** → 文件日志（`.debug_log/debug.log`）
   - **浏览器 / 前端（Vue、React 等）** → `console.log` 探针（由用户粘贴控制台输出）
   - **混合环境（SSR、Electron）** → 服务端用文件日志，渲染进程用 console
5. 输出探针计划表，然后**立即进入 Step 2**：

```
📋 探针计划：
| # | 文件:行号 | 标签 | 观察变量 | 假设 |
|---|-----------|------|---------|------|
| 1 | app.js:22 | checkout-cache-check | available, sku | 缓存返回过期值 |
| 2 | app.js:45 | reserve-entry | stock, reserved | 预留时的实际库存状态 |
...

日志策略：file-based / console / hybrid
⏳ 开始插入探针...
```

打印：`✅ CHECKPOINT 1: 探针计划已创建 — 共 N 个探针`

### Step 2: 启动日志收集器

**文件日志模式（CLI / 服务端）：**

```bash
mkdir -p .debug_log
: > .debug_log/debug.log
echo "run_count=0" > .debug_log/state

# 自动忽略：若 .gitignore 中尚未包含 .debug_log/，追加一条
if [ -f .gitignore ]; then
  grep -qxF '.debug_log/' .gitignore || echo '.debug_log/' >> .gitignore
else
  echo '.debug_log/' > .gitignore
fi
```

**写入 run 分隔符** —— 每次执行前写入一条运行头：

```bash
RUN_NUM=$(($(grep -oE 'run_count=[0-9]+' .debug_log/state | cut -d= -f2) + 1))
echo "run_count=$RUN_NUM" > .debug_log/state
echo "" >> .debug_log/debug.log
echo "========== RUN #$RUN_NUM | $(date -Iseconds) ==========" >> .debug_log/debug.log
```

确保多次运行在日志中有清晰分隔。

**控制台日志模式（浏览器 / 前端）：**

无需初始化——探针直接用 `console.log` 并加 `[DEBUG PROBE N]` 前缀。提示用户打开浏览器控制台（F12 → Console），过滤 `DEBUG PROBE`。

打印：`✅ CHECKPOINT 2: 日志收集器已启动`

### Step 3: 插入探针（必须使用 Edit 工具）

**必须调用 Edit 工具真实修改源文件。** 计划中每个探针都必须调用一次 Edit 真实插入，不得只口头描述。

所有探针必须使用 START/END 块标记包裹，保证清理时能整块删除而不误伤业务代码：

```
// 🔍 DEBUG PROBE [N] label
<探针代码 - 一行或多行>
// 🔍 DEBUG PROBE END [N]
```

其中 `[N]` 为计划中的探针编号。每个探针**必须包含**：
- 文件名和行号
- 标签（语义化描述探针位置）
- 关键变量的值
- 时间戳（文件日志）或结构化前缀（控制台日志）

#### 浏览器 / 前端（Vue、React、Svelte 等）

```typescript
// 🔍 DEBUG PROBE [1] funcName-entry
console.log(`[DEBUG PROBE 1] funcName-entry | var1=${var1} | var2=${JSON.stringify(var2)}`)
// 🔍 DEBUG PROBE END [1]
```

Vue（响应式状态）：

```typescript
// 🔍 DEBUG PROBE [1] reactive-state
console.log(`[DEBUG PROBE 1] reactive-state | refVal=${someRef.value} | computedVal=${someComputed.value} | storeVal=${store.someState}`)
// 🔍 DEBUG PROBE END [1]
```

React（hooks 状态）：

```typescript
// 🔍 DEBUG PROBE [1] component-render
console.log(`[DEBUG PROBE 1] component-render | state=${JSON.stringify(state)} | prop=${prop}`)
// 🔍 DEBUG PROBE END [1]
```

#### JavaScript / TypeScript（Node.js / 服务端）

```javascript
// 🔍 DEBUG PROBE [1] funcName-entry
require('fs').appendFileSync('.debug_log/debug.log', `[${new Date().toISOString()}] [js] file.js:42 | funcName-entry | var1=${JSON.stringify(var1)}, var2=${JSON.stringify(var2)}\n`);
// 🔍 DEBUG PROBE END [1]
```

#### Python

```python
# 🔍 DEBUG PROBE [1] funcName-entry
import datetime; open(".debug_log/debug.log", "a").write(f"[{datetime.datetime.now().isoformat()}] [python] file.py:42 | funcName-entry | var1={var1}, var2={var2}\n")
# 🔍 DEBUG PROBE END [1]
```

#### Go

```go
// 🔍 DEBUG PROBE [1] funcName-entry
if f, err := os.OpenFile(".debug_log/debug.log", os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644); err == nil {
    fmt.Fprintf(f, "[%s] [go] file.go:42 | funcName-entry | var=%v\n", time.Now().Format(time.RFC3339), variable)
    f.Close()
}
// 🔍 DEBUG PROBE END [1]
```

#### Swift

```swift
// 🔍 DEBUG PROBE [1] funcName-entry
if let fh = FileHandle(forWritingAtPath: ".debug_log/debug.log") {
    fh.seekToEndOfFile()
    fh.write("[\(ISO8601DateFormatter().string(from: Date()))] [swift] file.swift:42 | funcName-entry | val=\(variable)\n".data(using: .utf8)!)
    fh.closeFile()
}
// 🔍 DEBUG PROBE END [1]
```

#### Java / Kotlin

```kotlin
// 🔍 DEBUG PROBE [1] funcName-entry
java.io.File(".debug_log/debug.log").appendText("[${java.time.Instant.now()}] [kotlin] file.kt:42 | funcName-entry | var=$variable\n")
// 🔍 DEBUG PROBE END [1]
```

#### Shell / Bash

```bash
# 🔍 DEBUG PROBE [1] funcName-entry
echo "[$(date -Iseconds)] [bash] script.sh:42 | funcName-entry | var=$variable" >> .debug_log/debug.log
# 🔍 DEBUG PROBE END [1]
```

插入所有探针后打印：`✅ CHECKPOINT 3: 已在源码中插入 N 个探针`

### Step 4: 运行并复现

**文件日志模式：** 每次执行前先写入 run 分隔符：

```bash
RUN_NUM=$(($(grep -oE 'run_count=[0-9]+' .debug_log/state | cut -d= -f2) + 1))
echo "run_count=$RUN_NUM" > .debug_log/state
echo -e "\n========== RUN #$RUN_NUM | $(date -Iseconds) ==========" >> .debug_log/debug.log
```

然后执行项目运行命令。

**控制台日志模式（浏览器 / 前端）：** 告知用户

> "已插入探针：
> - `fileA.xx:line` — 观察 XXX
> - `fileB.xx:line` — 观察 YYY
>
> 请：
> 1. 打开浏览器控制台（F12 → Console）
> 2. 复现问题
> 3. 复制所有以 `[DEBUG PROBE` 开头的行，粘贴到这里"

**GUI / 移动端等需手动交互的项目：** 告知探针位置，请用户复现并贴出输出。

**偶发 bug（竞态、时序）：** 连跑 2-3 次，每次前写入分隔符。跨 `RUN #1`、`RUN #2` 比较差异点。

打印：`✅ CHECKPOINT 4: 已收集 N 条日志`

### Step 5: 分析日志

**文件日志：**

```bash
cat .debug_log/debug.log
```

**控制台日志：** 分析用户粘贴的内容。

分析清单：
- **执行顺序**：是否符合预期？
- **缺失条目**：哪些探针没被触发（路径未走到）？
- **异常取值**：变量值是否符合预期？
- **重复执行**：有无意外的重入/循环？
- **时间间隔**：探针之间的耗时是否异常（性能/超时问题）？

打印：`✅ CHECKPOINT 5: 已基于日志证据定位根因`（必须引用具体日志条目作为证据）

### Step 6: 定位并修复

基于日志分析：

1. 明确陈述根因，引用具体日志条目作为证据
2. 实施修复
3. **保留探针不动**，再次运行以收集"修复后"日志：

文件日志模式：
```bash
echo -e "\n========== VERIFY | $(date -Iseconds) ==========" >> .debug_log/debug.log
<运行命令>
```

控制台模式：请用户再复现一次并贴出新的输出。

4. 对比"修复前"与 `VERIFY` 日志，问题探针条目应该展现正确的值
5. 验证通过后进入清理

打印：`✅ CHECKPOINT 6: 已应用修复并通过探针验证`

#### 修复无效时怎么办

1. **不要删除已有探针**——它们是基线数据
2. **围绕刚修改的代码再加探针**——观察修复代码是否真正执行、看到的值是否符合预期
3. **对比修复前后日志**：
   - 新代码路径有没有被走到？（缺失探针 = 根本没走到）
   - 走到了但输入值不对？
   - 是否被别的路径覆盖或撤销？
4. 重新运行收集。总迭代次数不超过 3 轮，3 轮后向用户汇报并商讨后续。

### Step 7: 清理（强制，不可跳过）

```bash
# 删除调试目录
rm -rf .debug_log/
```

搜索所有探针块：

```bash
grep -rn "🔍 DEBUG PROBE" . --include="*.ts" --include="*.js" --include="*.py" --include="*.swift" --include="*.go" --include="*.kt" --include="*.java" --include="*.sh" --include="*.vue" --include="*.jsx" --include="*.tsx" --include="*.svelte"
```

对每个文件，删除完整探针块——从 `🔍 DEBUG PROBE [N]` 到 `🔍 DEBUG PROBE END [N]` 全部删除（包含首尾标记）。使用 Edit 工具逐块删除。START/END 标记保证不会误删业务代码。

验证清理完成：

```bash
grep -rn "DEBUG PROBE" . --include="*.ts" --include="*.js" --include="*.py" --include="*.swift" --include="*.go" --include="*.kt" --include="*.java" --include="*.sh" --include="*.vue" --include="*.jsx" --include="*.tsx" --include="*.svelte"
```

必须返回零结果。**不得残留任何探针代码。**

打印：`✅ CHECKPOINT 7: 所有探针已清除，清理完成`

## 探针标签约定

| 模式 | 示例 | 用于 |
|------|------|------|
| `funcName-entry` | `processOrder-entry` | 函数入口 |
| `funcName-exit` | `processOrder-exit` | 函数出口 |
| `funcName-error` | `processOrder-error` | 异常捕获 |
| `varName-state` | `cart-state` | 状态快照 |
| `reactive-state` | `reactive-state` | Vue ref/computed、React state |
| `condition-branch` | `earlyReturn-branch` | 控制流分支 |
| `loop-iter` | `retry-iter` | 循环迭代 |
| `async-await` | `fetchData-await` | 异步 await 点 |

## 注意事项

- 探针代码**不得影响原有逻辑**（必要时用 try-catch 包裹或抑制错误）
- 所有探针必须用 `🔍 DEBUG PROBE [N] label` / `🔍 DEBUG PROBE END [N]` 块标记包裹——保证清理时可整块安全删除
- 日志目录 `.debug_log/`，日志文件 `.debug_log/debug.log`，运行计数 `.debug_log/state`
- 每次运行用 `========== RUN #N | timestamp ==========` 分隔，验证运行用 `========== VERIFY | timestamp ==========`
- Step 2 已自动把 `.debug_log/` 加入 `.gitignore`，无需手动处理
- 对生产代码，插入探针前务必先与用户确认
