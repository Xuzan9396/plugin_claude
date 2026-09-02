---
name: xz-cases
description: 为指定版本（区间或离散多个）生成核心功能点改动验收清单，Python 脚本输出 xlsx 到 .xz_planning/cases/xlsx/。/xz-cases 1-1.2 或 /xz-cases 1,1.2
disable-model-invocation: false
argument-hint: "[N-M] 或 [N1,N2,...]"
---

# XZ Cases - 生成测试用例（xlsx）

参数 `$ARGUMENTS`。为空则**立即停止**，提示：

> 缺少版本号。用法: `/xz-cases N-M`（区间）或 `/xz-cases N1,N2,...`（离散）
> 示例: `/xz-cases 1-1.2`、`/xz-cases 1,1.2`、`/xz-cases 1`

**脚本**：`xz-tools.py`（`bin/` 已在 PATH，直接调用，在当前目录操作 `.xz_planning/`）。

---

## 执行流程

**1. 解析版本表达式** — 按逗号拆 token：`A-B` 区间纳入所有 A ≤ v ≤ B 的现存版本（`1-1.2` 命中 `1`/`1.1`/`1.2`）；`A` 单个只精确命中（`1,1.2` 不带上 `1.1`）。取并集去重、按**数值**升序（`1 < 1.1 < 1.2 < 1.5 < 2 < 10`）。

**2. 过滤现存版本** — `xz-tools.py status` 拿 `active` + `archived` 版本号套表达式过滤。区间命中 0 个 → 停止；离散里某个不存在 → 记「跳过」继续；全都不存在 → 停止，提示先 `/xz-plan`。

**3. 逐版本加载** — 每个版本跑 `xz-tools.py parse N --include-archive`，**按版本号升序**读：`N-PLAN.md` 全文（需求/技术方案/todolist）、同目录的 `N-DISCUSS.md` 与 `N-UAT.md`、以及已完成 `[x]` 条目涉及的**实际代码文件**。

**4. 消解版本冲突：代码是唯一裁判** — 后版本经常推翻前版本（换实现、改字段、废弃功能），用例只描述**当前代码里的最终形态**：

- 同一功能点被多版本改过 → 只留版本号最大的那份，中间态不算，最终只写**一行**
- 字段名、取值范围、默认值、排序、条数上限、文案、兜底返回拿不准 → Grep/Read 打开代码确认。PLAN 是当时的打算，代码才是现在的事实
- 代码里找不到 PLAN 描述的功能 → 要么不生成这行，要么标注「计划与代码不一致，需与开发确认」
- 「以前是 X，现在改成 Y」的 X 指这批版本**上线前线上的真实形态**，不是同批里从未上线的作废草案

**5. 生成 xlsx** — 用例填进下方骨架的 `CASES`，写到 `/tmp/xz_cases_gen.py` 后跑 `uv run --with openpyxl python3 /tmp/xz_cases_gen.py`（`uv` 不可用回退 `pip3 install openpyxl && python3 /tmp/xz_cases_gen.py`）。文件名的功能名由你一句话概括：多版本 `v{首}-v{尾}-功能名测试用例.xlsx`，单版本 `v{N}-功能名测试用例.xlsx`。**只出这一个 xlsx——不生成 md，不改 STATE.md / PLAN.md，不写测试代码。**

---

## 表结构

这不是通用测试用例表，是**版本改动验收清单**：**一行 = 一个核心功能点**，测试人员看完「详细说明」自己就知道该怎么测。

| # | 列 | 要求 |
|---|---|---|
| 1 | 用例编号 | `TC-001`，三位补零，全文件连续 |
| 2 | 功能模块 | 测试听得懂的业务叫法（「战绩查询」而非 `game_log`），同模块可多行 |
| 3 | 测试新增改动详细说明 | 核心列，不限字数，`1. 2. 3.` 逐条展开，`\n` 换行 |
| 4 | 预期结果 | 能观察到的现象，带具体数值，既写「应该出现什么」也写「不应出现什么」，`\n` 换行 |
| 5-6 | 测试结果 / 备注/Bug | 留空给测试人员填 |

**不要**所属版本、用例标题、改动说明、优先级、类型、前置条件、操作步骤这些列——全并进第 3 列。跨版本汇总到同一份、按功能模块排在一起，不按版本分开。

**样式**：冻结首行 `A2`、自动筛选到最后一格、表头深蓝底白字加粗自动换行、数据行按功能模块分块底色（不加斑马纹）、列宽第 3 列最宽。

---

## 详细说明写作规则（质量核心）

### 粒度：宁少勿滥

- **一行 = 一处新增或一处改动**，不是单个输入值、不是单个分支
- **同类必须收敛** — 同一校验点的多个非法输入、同一兜底的多种触发原因，全写进那一行的子序号里。反例：`记录类型传 -1 / 传 2 / 传 128` 拆三行 → 合并成一行「记录类型开关的取值校验」
- **内部实现不开行** — 函数调用次数、序列化路径、日志埋点测试观察不到；要提醒就写成详细说明里的一条「排查提示」
- **条数上限** — 单版本 5～12 行，多版本汇总不超过 20 行；超了回去合并。但合并不等于漏测，宁可一行写长

### 结构：逐条编号，顺序固定

一条一个要点一句话，一般 3～8 条：

1. **第 1 条 = 功能点 + 场景入口** — 以 `新增 xxx` / `改动 xxx` 起头（承担标题作用），接着说这功能在哪、谁会用、从哪进去看得到
2. **中间若干条 = 前后对比 + 情况分支** — 以前什么样 → 现在什么样；正常、传错、没数据、服务出问题各是什么表现
3. **最后 1 条 = 「测试重点：」** — 最容易出问题、要盯着看的地方

未完成 `[ ]` 条目对应的功能点，在第 1 条标注「待实现后测试」。

### 语言：三条禁令

- **禁代码标识符与技术缩写** — `act_type`、`DAO`、`JWT`、`int8`、驼峰函数名、SQL 片段一律翻成业务话：「记录类型开关」「登录身份」「整数上限」
- **禁规约腔** — 不写「必须」「应在……之前被拒绝」「避免……压力」，改成现象：「传错了会直接提示参数错误，不会去查数据库」
- **禁抽象描述** — 数值带单位和含义：「最多取最近 20 轮」「金额 30000 会显示成 3万」；同一行内详细说明与预期结果的数值必须对得上

正反例（右列 `<br>` 是本文档排版换行，写进脚本用 `\n`）：

| ✗ 开发评审腔 + 术语裸露 | ✓ 改成这样 |
|---|---|
| 非法模式必须在访问数据库之前被拒绝，避免无效请求增加数据库压力或意外落入个人分支 | 1. 改动 战绩页的「看谁的记录」开关，只认「看自己」和「看全服」两个值<br>2. 填别的值（负数、没定义过的数字、超大数字）一律直接提示参数错误<br>3. 提示后不会去查数据库，也不会默认给你看自己的记录<br>4. 测试重点：正常玩家碰不到，主要防有人改包乱试 |

另外两条：正文里**不出现版本号和需求编号**（`v36.2`、`#1`，追溯靠文件名）；**行尾不带标点**（`。`、`.`、`;`、`；` 都不要，写到末尾字符就结束）。

---

## 脚本骨架

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""xz-cases 生成脚本：输出 xlsx 到当前工作目录的 .xz_planning/cases/xlsx/。"""

from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

# ↓↓↓ AI 按读到的 PLAN / 代码填充
BASENAME = "v1-v1.2-用户模块测试用例"      # 不带扩展名
CASES = [
    {
        "no": "TC-001",
        "module": "战绩查询",
        "detail": "1. 新增 全服战绩查询入口，玩家在战绩页原来只有「我的战绩」，这次多了「全服战绩」标签\n2. 以前只能看自己的记录，现在切到全服标签能看全服玩家最近的对局\n3. 两个标签共用一个入口，靠一个开关区分看谁的\n4. 全服最多只给最近 20 轮，按轮次从新到旧排\n5. 测试重点：切标签时两边数据不能串，金额格式两边要一样",
        "expect": "切到「全服战绩」能看到 20 条记录，最上面一条是最新一轮\n切回「我的战绩」只有自己的记录，不应混进别人的",
    },
    # ... 更多功能点
]
# ↑↑↑

HEADERS = ["用例编号", "功能模块", "测试新增改动详细说明", "预期结果"]
EXTRA_HEADERS = ["测试结果", "备注/Bug"]
XLSX_WIDTHS = [12, 16, 80, 48, 12, 24]
PALETTE = ["FFF7EC", "EAF6FF", "F5EEFF", "ECFBF0", "FFF0F3"]


def _module_fill_map():
    modules = []
    for c in CASES:
        if c["module"] not in modules:
            modules.append(c["module"])
    return {m: PALETTE[i % len(PALETTE)] for i, m in enumerate(modules)}


def write_xlsx(path):
    wb = Workbook()
    ws = wb.active
    ws.title = "测试用例"
    full_headers = HEADERS + EXTRA_HEADERS
    module_fill = _module_fill_map()

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
        fill_color = module_fill.get(c["module"], "FFFFFF")
        fill = PatternFill(fill_type="solid", start_color=fill_color, end_color=fill_color)
        values = [c["no"], c["module"], c["detail"], c["expect"], "", ""]
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
    xlsx_dir = Path.cwd() / ".xz_planning" / "cases" / "xlsx"
    xlsx_dir.mkdir(parents=True, exist_ok=True)
    xlsx_path = xlsx_dir / f"{BASENAME}.xlsx"
    write_xlsx(xlsx_path)
    print(f"wrote: {xlsx_path}\ntotal cases: {len(CASES)}")


if __name__ == "__main__":
    main()
```

---

## 校验

跑完抽查：

- `.xz_planning/cases/xlsx/` 下有 `.xlsx`、没有 md；6 列齐全
- 行数 5～12（单版本）/ ≤20（多版本）；超了回去合并
- 每格详细说明：`1. 2. 3.` 编号、3～8 条、首条以「新增/改动」起头、末条以「测试重点：」起头
- 全表扫一遍有无残留代码标识符或规约腔（「必须」「应」「避免」）
- 多版本汇总：同一功能点只剩一行，且描述的是最新版本的最终形态

## 下一步建议

生成后以纯文本输出：

> 测试用例已生成:
>   .xz_planning/cases/xlsx/{文件名}.xlsx（给测试人员，含改动详细说明 + 测试结果/备注列）
> 下一步: /xz-done N（归档版本）
