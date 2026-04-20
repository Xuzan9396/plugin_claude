---
name: xz-review
description: 审查版本 N 的 todolist 改动是否符合预期，检查安全、性能和质量问题。/xz-review N
disable-model-invocation: false
argument-hint: "[N]"
context: fork
agent: xz-code-reviewer
---

# XZ Review - 版本计划代码审查

审查版本号: `$ARGUMENTS`

### 参数校验

如果 `$ARGUMENTS` 为空或不是正整数，**立即停止**，提示：

> 缺少版本号。用法: `/xz-review N`
> 示例: `/xz-review 1`

**只审查版本 N 的 PLAN.md 中 todolist 涉及的改动，其他无关文件不管。**

---

## 辅助脚本

**脚本路径**：`$CLAUDE_PLUGIN_ROOT/bin/xz-tools.py`

Claude Code 插件运行时会自动注入 `CLAUDE_PLUGIN_ROOT` 环境变量，指向本插件根目录。后续所有调用使用 `python3 "$CLAUDE_PLUGIN_ROOT/bin/xz-tools.py" <命令>` 格式（必须带双引号，shell 会展开变量）。脚本在**当前工作目录**下操作 `.xz_planning/`。

---

## 执行流程

### 第一步：解析并读取计划

```bash
python3 "$CLAUDE_PLUGIN_ROOT/bin/xz-tools.py" parse $ARGUMENTS
```

如果版本不存在，提示用户先创建计划。从返回 JSON 中取 `phase.plan_file` 路径，读取 N-PLAN.md 完整内容，提取：
- 所有 todolist 条目（无论 `[x]` 还是 `[ ]`）
- 每条的 change details 中涉及的文件路径
- 需求描述和技术方案

### 第二步：收集实际代码

根据 change details 中列出的所有文件路径：
1. 逐个读取这些文件的**当前实际内容**
2. 「新建」的文件 — 检查是否存在
3. 「修改」的文件 — 读取当前内容

### 第三步：逐条对比审查

**审查顺序：** 先安全（阻断级）→ 再性能 → 最后质量。

**铁律：** 所有问题必须指向具体代码行，禁止列出文件中不存在的假想风险。

对每个 `[x]` 已完成的条目，依次执行以下审查：

#### 3.1 符合性检查

对比 change details 描述和实际代码，确认每个计划点是否已正确落地。

#### 3.2 安全审查

**通用检查项（所有语言）：**
- 硬编码的密钥、密码、token、API key
- 输入未校验就使用（用户输入、外部 API 返回值、URL 参数）
- 敏感信息泄露（日志、错误消息、注释、前端可见的响应字段）
- 权限/鉴权缺失或绕过
- 不安全的加密方式（如 MD5/SHA1 用于密码）

**语言专项检查（根据文件后缀匹配对应项）：**

| 语言 | 高频风险点 |
|------|-----------|
| JS/TS (.js/.ts/.jsx/.tsx) | `innerHTML`/`dangerouslySetInnerHTML`(XSS)、`eval()`/`new Function()`、原型链污染、ReDoS（灾难性回溯正则）、npm 依赖供应链风险 |
| Go (.go) | 未检查的 error return、`unsafe` 指针操作、竞态条件（共享状态缺 mutex/channel 保护）、`net/http` 未设超时 |
| SQL (.sql) | 字符串拼接构造查询（注入）、过宽的 GRANT 权限、动态表名未白名单校验 |

#### 3.3 性能审查

**通用检查项（所有语言）：**
- 冗余重复计算（循环内可外提的逻辑）
- 资源未释放（连接、文件句柄、监听器、定时器）
- 不必要的大对象拷贝

**语言专项检查：**

| 语言 | 高频性能陷阱 |
|------|-------------|
| Python | GIL 下的 CPU 密集阻塞、async 中夹同步阻塞调用、ORM N+1 查询、循环内重复编译正则/重复 import |
| JS/TS | 主线程阻塞（大循环/同步 IO）、React 无效 re-render（缺 memo/useMemo/正确 key）、事件监听器未清理（内存泄漏）、bundle 体积膨胀（整包 import） |
| Go | goroutine 泄漏（无退出条件/无 context cancel）、不必要的堆分配（可用值类型替代指针）、缺连接池 |
| SQL | 缺索引的大表查询、全表扫描（`SELECT *`）、缺分页的列表查询、N+1 查询模式 |

#### 3.4 质量审查

- 边界条件是否完整（空值、空集合、零值、负数）
- 错误处理是否丢失上下文（吞异常、空 catch）
- 资源释放、回滚和清理逻辑是否完整
- 命名是否清晰一致
- 重复代码是否可以提取
- 类型安全 — TS 中 `any` 滥用、Python 类型标注与实际不符
- 并发安全 — 共享状态无锁/无 channel 保护（Go/Java/多线程场景）

#### 附：未完成条目前瞻

对 `[ ]` 未完成条目，仅做简要前瞻：change details 中涉及的文件是否已被前序任务改动导致潜在冲突、是否存在依赖未实现的问题。

### 第四步：输出审查报告

#### 1. 审查范围

```
版本: N
需求: xxx
审查范围: PLAN.md 中涉及的 X 个文件
已完成条目: M 条（深度审查）
未完成条目: K 条（前瞻检查）
```

#### 2. 符合性检查结果

| 条目 | 计划内容 | 实际状态 | 结论 |
|------|----------|----------|------|
| #1 | 创建 User model 含 5 个字段 | 5 个字段齐全 | ✅ 符合 |
| #2 | 注册接口含输入校验 | 缺少 email 格式校验 | ⚠️ 部分缺失 |

#### 3. 问题发现

按严重程度排序，每条问题直接附带修复建议：

- **严重** — 必须修复，存在安全漏洞或数据丢失风险
- **高** — 强烈建议修复，影响可靠性或性能
- **中** — 建议修复，影响代码质量或可维护性
- **低** — 可选优化，改善代码风格

每条格式：

```
[严重] 文件:行号 — 问题描述
  影响: xxx
  建议: xxx（具体到代码怎么改）
```

如果没有问题，明确写 `未发现阻断问题`。

#### 4. 总结

用 2-4 句话概括：整体完成质量、最需要关注的风险点。

#### 5. 下一步建议

根据审查结果，使用 AskUserQuestion 工具让用户选择下一步操作：

**无阻断问题时：**

- question: "审查完成，未发现阻断问题。接下来要做什么？"
- header: "下一步"
- options:
  - label: "/xz-test N", description: "生成测试指南（可选）"
  - label: "/xz-done N", description: "归档版本"
- multiSelect: false

**有问题需修复时：**

- question: "审查发现 X 个问题需修复。接下来要做什么？"
- header: "下一步"
- options:
  - label: "/xz-exec N", description: "继续执行修复"
  - label: "/xz-update-plan N", description: "新增修复条目到 todolist"
- multiSelect: false

用户选择后，执行对应的 skill 命令。如果用户选择 Other，按其输入内容响应。

---

## 关键规则

1. **只看 PLAN 涉及的文件** — 不审查 todolist 范围之外的代码
2. **change details 是审查基准** — 以计划描述为准，对比实际实现
3. **不修改任何文件** — 只读取、分析、输出报告
4. **不执行任何 git 操作** — 纯文件读取
5. **问题要具体** — 必须给出文件名、行号、修复建议，不列假想风险
6. **按语言匹配检查项** — 根据文件后缀自动匹配对应语言的安全和性能专项检查
