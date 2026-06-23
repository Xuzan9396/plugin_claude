---
name: xz-cases
description: 为指定版本（区间或离散多个）生成结构化测试用例，单 Python 源同时输出 md + xlsx 到 .xz_planning/cases/。/xz-cases 1-1.2 或 /xz-cases 1,1.2
disable-model-invocation: false
argument-hint: "[N-M] 或 [N1,N2,...]"
---

# XZ Cases - 生成测试用例（md + xlsx）

参数: `$ARGUMENTS`

### 参数校验

如果 `$ARGUMENTS` 为空，**立即停止**，提示：

> 缺少版本号。用法: `/xz-cases N-M`（区间）或 `/xz-cases N1,N2,...`（离散）
> 示例: `/xz-cases 1-1.2`、`/xz-cases 1,1.2`、`/xz-cases 1`

---

## 辅助脚本

**脚本**：`xz-tools.py`

插件启用时 `bin/` 目录自动加入 PATH，直接作为命令调用即可（不需要 `python3` 前缀，也不需要绝对路径）。脚本在**当前工作目录**下操作 `.xz_planning/`。

---

## 执行流程

### 第一步：解析版本选择表达式

把 `$ARGUMENTS` 先按逗号 `,` 拆成若干 token，每个 token 是「单个版本」或「区间」：

- **区间** `A-B`（token 中含 `-`）：纳入**所有现存版本号 v 满足 A ≤ v ≤ B**。例如 `1-1.2` 命中现存的 `1`、`1.1`、`1.2` 三个版本（含中间版本）
- **单个** `A`（无 `-`）：只精确命中版本 `A`，**不**纳入相邻的中间版本。例如 `1,1.2` 只命中 `1` 和 `1.2`，即使存在 `1.1` 也跳过

把所有 token 的命中结果**取并集、去重、按版本号升序排序**，得到目标版本列表。

**版本号按数值比较**，不是字符串比较：`1 < 1.1 < 1.2 < 1.5 < 2 < 10`

### 第二步：列出现存版本并过滤

```bash
xz-tools.py status
```

从返回 JSON 的 `active` 和 `archived` 里拿到所有现存版本号，套用第一步的表达式过滤，得到最终目标版本列表。

- 区间表达式命中 0 个版本 → 停止，提示该区间内没有任何版本
- 离散表达式里某个版本不存在 → 记录「跳过」，继续处理其余版本
- 全部都不存在 → 停止，提示先用 `/xz-plan` 创建计划

### 第三步：逐个加载 PLAN 与代码

对每个目标版本 N（活跃 + 归档都要查）：

```bash
xz-tools.py parse N --include-archive
```

1. 用返回 JSON 的 `phase.plan_file` 读取 `N-PLAN.md` 完整内容，理解需求、技术方案、todolist
2. 如果同目录存在 `N-DISCUSS.md`、`N-UAT.md`，一并读取作为上下文
3. 读取 todolist 中**已完成 `[x]` 条目**涉及的**实际代码文件**，了解真实实现，作为用例的依据（不要凭空编造）

### 第四步：生成 md + xlsx 双产物

**用单个 Python 源文件**同时输出 md 和 xlsx，**分目录落盘**（脚本自动创建）：md 进 `.xz_planning/cases/md/`，xlsx 进 `.xz_planning/cases/xlsx/`。

1. 把整理好的用例填进脚本里的 `CASES` 列表（结构见下方「脚本骨架」）
2. 脚本写到 `/tmp/xz_cases_gen.py`
3. 运行（本机大概率没装 openpyxl，用 uv 一键带依赖跑）：

```bash
uv run --with openpyxl python3 /tmp/xz_cases_gen.py
```

**文件命名**（两个产物 basename 相同，功能名由你根据这些版本的整体功能用一句话概括）：

- 多个版本：`cases/md/v{首}-v{尾}-功能名测试用例.md` + `cases/xlsx/v{首}-v{尾}-功能名测试用例.xlsx`，如 `v1-v1.2-用户模块测试用例`
- 单个版本：`cases/md/v{N}-功能名测试用例.md` + `cases/xlsx/v{N}-功能名测试用例.xlsx`，如 `v1-用户登录测试用例`

**只生成这两个产物（同名 md + xlsx，分别在 cases/md 与 cases/xlsx）。不更新 STATE.md，不更新 PLAN.md，不生成任何测试代码文件。**

**获取当前时间：**

```bash
date "+%Y-%m-%d %H:%M:%S"
```

---

## 列结构（md 与 xlsx 共用）

**内容列（11 列）：**

1. 用例编号（`TC-001`，三位补零，全文件连续）
2. 所属版本（`v1` / `v1.2`）
3. 测试白话说明（**给测试人员看的通俗解释，不限字数**：改之前是什么样 → 这次改了什么 → 预期变成什么样，用大白话讲清，把裸数值和术语翻成能听懂的话，不堆代码细节）
4. 功能模块（如「注册」「登录」「余额」）
5. 用例标题（一句话点出验证点）
6. 改动说明（这条用例对应版本改了什么，技术描述 OK）
7. 优先级（P0 核心主流程 / P1 重要分支 / P2 次要边界）
8. 类型（正常 / 异常 / 边界）
9. 前置条件（带具体数值；无额外前置写 `-`）
10. 操作步骤（带编号 `1. 2. 3.`，md 用 `<br>` 换行、xlsx 用 `\n` 换行，带具体数值）
11. 预期结果（用户/接口可观察到的现象，带具体数值，含「不应出现什么」）

**xlsx 额外两列**（留空给测试人员填）：

12. 测试结果
13. 备注/Bug

**xlsx 样式要求：**

- 冻结首行（`A2`）
- 自动筛选（覆盖到最后一列最后一行）
- 表头深蓝底白字加粗、自动换行
- 数据行按版本分块底色（不同版本不同淡色）+ 偶数行斑马纹
- 列宽预设（白话说明 / 步骤 / 预期 / 改动说明 较宽，编号 / 版本 / 优先级 / 类型 较窄）

---

## 脚本骨架

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""xz-cases 单源生成脚本：同时输出 md 和 xlsx。在当前工作目录的 .xz_planning/cases/ 分目录落盘。"""

from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

# ↓↓↓ AI 按读到的 PLAN / 代码填充
GEN_TIME = "YYYY-MM-DD HH:mm:ss"           # 用 date 命令取到的真实时间
BASENAME = "v1-v1.2-用户模块测试用例"      # 不带扩展名，md/xlsx 共用
VERSION_TITLES = {"v1": "用户注册", "v1.2": "登录"}  # 各版本主题
CASES = [
    {
        "no": "TC-001",
        "ver": "v1",
        "plain": "以前系统没有注册功能；这次新增了用户注册——填邮箱和密码就能开通账号。测试重点：注册成功后系统会给你分配一个用户编号；数据库里存的密码必须是一串看不懂的加密字符，绝不能是刚输入的原始密码（明文存密码是安全事故）",
        "module": "注册",
        "title": "正常注册流程",
        "change": "新增注册接口，密码加密入库",
        "priority": "P0",
        "type": "正常",
        "pre": "服务已启动，邮箱 alice@example.com 未注册",
        "steps": "1. 调用注册接口，提交邮箱 alice@example.com、密码 Test@1234\n2. 查询 SELECT id, email, password FROM users WHERE email='alice@example.com'",
        "expect": "接口返回 200，返回 id=1001\nusers 新增一条记录，password 为加密串 $2b$... 而非明文 Test@1234",
    },
    # ... 更多用例
]
# ↑↑↑

HEADERS = ["用例编号", "所属版本", "测试白话说明", "功能模块", "用例标题", "改动说明",
           "优先级", "类型", "前置条件", "操作步骤", "预期结果"]
EXTRA_HEADERS = ["测试结果", "备注/Bug"]
XLSX_WIDTHS = [14, 8, 48, 14, 26, 30, 8, 8, 24, 40, 40, 12, 24]
# 版本分块底色（按出现顺序循环取色）
PALETTE = ["FFF7EC", "EAF6FF", "F5EEFF", "ECFBF0", "FFF0F3"]
ZEBRA_FILL = "FAFAFA"


def _ver_fill_map():
    vers = []
    for c in CASES:
        if c["ver"] not in vers:
            vers.append(c["ver"])
    return {v: PALETTE[i % len(PALETTE)] for i, v in enumerate(vers)}


def cell_md(text):
    if text is None or text == "":
        return "-"
    return str(text).replace("|", "\\|").replace("\n", "<br>")


def write_md(path):
    counts = {}
    for c in CASES:
        counts[c["ver"]] = counts.get(c["ver"], 0) + 1
    lines = [f"# {BASENAME}", "",
             f"> 生成时间: {GEN_TIME}",
             f"> 覆盖版本: {', '.join(counts.keys())}",
             "> 说明：xlsx 版另含「测试结果 / 备注 Bug」两列供测试人员填写",
             "", "## 总览", "",
             "| 版本 | 用例数 | 主题 |", "|------|-------:|------|"]
    for ver in counts:
        lines.append(f"| {ver} | {counts[ver]} | {VERSION_TITLES.get(ver, '')} |")
    lines.append(f"| **合计** | **{len(CASES)}** | |")
    lines += ["", "## 用例明细", ""]
    for ver in counts:
        lines.append(f"### {ver} · {VERSION_TITLES.get(ver, '')}")
        lines.append("")
        cols = ["编号", "测试白话说明", "模块", "标题", "改动说明", "优先级", "类型", "前置条件", "操作步骤", "预期结果"]
        lines.append("| " + " | ".join(cols) + " |")
        lines.append("|" + "|".join(["------"] * len(cols)) + "|")
        for c in CASES:
            if c["ver"] != ver:
                continue
            row = [c["no"], c["plain"], c["module"], c["title"], c["change"], c["priority"],
                   c["type"], c["pre"], c["steps"], c["expect"]]
            lines.append("| " + " | ".join(cell_md(x) for x in row) + " |")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_xlsx(path):
    wb = Workbook()
    ws = wb.active
    ws.title = "测试用例"
    full_headers = HEADERS + EXTRA_HEADERS
    ver_fill = _ver_fill_map()

    header_fill = PatternFill(fill_type="solid", start_color="305496", end_color="305496")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin = Side(style="thin", color="C0C0C0")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    for col_idx, h in enumerate(full_headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = header_align
        cell.border = border
    ws.row_dimensions[1].height = 32

    cell_align = Alignment(vertical="top", wrap_text=True)
    for row_idx, c in enumerate(CASES, start=2):
        base = ver_fill.get(c["ver"], "FFFFFF")
        fill_color = ZEBRA_FILL if row_idx % 2 == 0 else base
        fill = PatternFill(fill_type="solid", start_color=fill_color, end_color=fill_color)
        values = [c["no"], c["ver"], c["plain"], c["module"], c["title"], c["change"], c["priority"],
                  c["type"], c["pre"], c["steps"], c["expect"], "", ""]
        for col_idx, v in enumerate(values, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=v)
            cell.fill = fill
            cell.alignment = cell_align
            cell.border = border

    for i, w in enumerate(XLSX_WIDTHS, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    ws.freeze_panes = "A2"
    last_col = get_column_letter(len(full_headers))
    ws.auto_filter.ref = f"A1:{last_col}{len(CASES) + 1}"
    wb.save(str(path))


def main():
    base = Path.cwd() / ".xz_planning" / "cases"
    md_dir, xlsx_dir = base / "md", base / "xlsx"
    md_dir.mkdir(parents=True, exist_ok=True)
    xlsx_dir.mkdir(parents=True, exist_ok=True)
    md_path = md_dir / f"{BASENAME}.md"
    xlsx_path = xlsx_dir / f"{BASENAME}.xlsx"
    write_md(md_path)
    write_xlsx(xlsx_path)
    print(f"wrote: {md_path}\nwrote: {xlsx_path}\ntotal cases: {len(CASES)}")


if __name__ == "__main__":
    main()
```

---

## 生成规则

1. **md + xlsx 两个同名产物** — md 落 `.xz_planning/cases/md/`、xlsx 落 `.xz_planning/cases/xlsx/`，不生成测试代码，不改其他文件
2. **跨版本汇总到一份** — 多个版本的用例放进同一文件，每条用「所属版本」标注来自哪个版本
3. **用例编号全局连续** — `TC-001`、`TC-002`… 在整个文件内连续，不按版本重新计数
4. **每条用例关联 todolist 编号** — 改动说明或标题里标注对应版本的 `#N`，让人能追溯到需求
5. **基于已完成 `[x]` 条目生成** — 未完成的 `[ ]` 条目对应用例标注「待实现后测试」
6. **覆盖正常 + 异常 + 边界** — 每个核心功能至少覆盖一条正常路径、一条异常/错误输入、必要时补边界与跨模块/并发/时序场景
7. **预期结果写正反面** — 既写「应该出现什么」，必要时也写「不应出现什么」
8. **前置条件要具体** — 写清系统状态、角色、环境，让执行者知道从什么状态开始；无额外前置写 `-`
9. **优先级分级** — P0（核心主流程）/ P1（重要分支）/ P2（次要边界），按业务影响判断
10. **依据真实代码** — 用例步骤和预期来自读过的 PLAN 与代码，不凭空编造接口或字段
11. **行尾不带标点** — 标题、用例标题、步骤、预期结果等每一行结尾**不要**带句号 `。`/`.`、分号 `;`/`；` 或任何其他收尾符号，写到末尾字符就结束
12. **补具体案例数值** — 前置条件、操作步骤、预期结果里凡涉及数据，都填**具体示例值**让测试者直观感受，不要只写抽象描述。如前置写「用户 `alice@example.com` 未注册，账户余额 `100.00`」、步骤写「提交邮箱 `alice@example.com`、密码 `Test@1234`」而非「提交合法邮箱密码」、预期写「返回 `id=1001`」「余额从 `100.00` 扣到 `90.00`」「password 为加密串 `$2b$...` 而非明文」。数值要符合代码里的真实字段、类型和约束，且同一用例内前置/步骤/预期的数值要前后一致
13. **测试白话说明面向不懂技术的测试** — 「测试白话说明」列**不限字数**，用大白话把「改之前是什么样 → 这次改了什么 → 预期变成什么样」讲清楚，把裸数值和术语翻成能听懂的话（如不要只写「raw_json 为空返回 -1」，要写「某分钟没采集到数据时，页面对应位置显示空缺而不是报错」）。这列是给测试看的通俗导读，技术细节留给「改动说明 / 步骤 / 预期」三列
14. **xlsx 必须可用** — 冻结首行、自动筛选、表头配色、版本分块底色 + 斑马纹、列宽合理；「测试结果」「备注/Bug」两列留空给测试人员填

---

## 校验

运行脚本后抽查：

- `.xz_planning/cases/md/` 与 `.xz_planning/cases/xlsx/` 下各生成了同名 `.md` 与 `.xlsx`
- xlsx 内容列 11 列 + 测试列 2 列 = 13 列；md 明细表 10 列（不含「所属版本」，已按版本分块）
- 用例总数与各版本子数对得上
- 若 `uv` 不可用，回退 `pip3 install openpyxl && python3 /tmp/xz_cases_gen.py`

---

## 下一步建议

生成后以纯文本输出：

> 测试用例已生成:
>   .xz_planning/cases/md/{文件名}.md
>   .xz_planning/cases/xlsx/{文件名}.xlsx（给测试人员，含测试白话说明 + 测试结果/备注列）
> 下一步: /xz-test N（生成手动测试指南）/ /xz-done N（归档版本）
