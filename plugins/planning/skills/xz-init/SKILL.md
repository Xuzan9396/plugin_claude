---
name: xz-init
description: 初始化或更新当前项目的 .xz_planning 目录结构和项目快照。/xz-init
disable-model-invocation: true
argument-hint: ""
---

# XZ Init - 初始化/更新项目计划目录

在当前项目根目录下创建或更新 `.xz_planning/` 目录结构，为版本计划开发做好准备,如果第一次使用的时候，如果项目为空创建空目录README.md 和 PROJECT.md， 如果没有git管理, 帮我初始化 git, 如果有文件 .gitignore 排除里面的内容扫描

**可重复执行：** 已初始化的项目再次执行时，只更新 README.md 和 PROJECT.md，不影响已有计划数据。

---

## 辅助脚本

**脚本**：`xz-tools.py`

插件启用时 `bin/` 目录自动加入 PATH，直接作为命令调用即可（不需要 `python3` 前缀，也不需要绝对路径）。脚本在**当前工作目录**下操作 `.xz_planning/`。

---

## 执行流程

### 第一步：检查是否已初始化

检查当前目录下 `.xz_planning/` 是否已存在。

- **不存在** → 执行完整初始化（第二步 ~ 第五步全部执行）
- **已存在** → 跳到第四步（只更新 README.md 和 PROJECT.md）

### 第二步：创建目录结构（仅首次）

```bash
xz-tools.py init
```

该脚本会创建：
- `.xz_planning/phases/` — 存放活跃版本计划
- `.xz_planning/archive/` — 存放已归档版本
- `.xz_planning/STATE.md` — 全局状态表

### 第三步：创建 README.md（每次覆盖）

运行 `xz-tools.py get-readme` 获取 README 模板内容，覆盖写入项目的 `.xz_planning/README.md`。

如果命令返回错误（模板文件不存在），跳过此步骤。

**README.md 每次执行都覆盖写入，确保使用最新版本的文档。**

### 第四步：生成/更新 PROJECT.md（核心）

`.xz_planning/PROJECT.md` 是项目的快照索引，相当于书籍的目录页码，让模型快速理解项目全貌。

#### 4a. 扫描当前项目

用 Glob 和 Read 扫描项目，收集以下信息：

1. **目录树** — 用 `tree` 风格展示项目结构（排除 `node_modules/`、`.git/`、`__pycache__/`、`.xz_planning/`、`venv/`、`.venv/` 等），只展示到 2-3 层深度
2. **技术栈识别** — 从配置文件自动识别：
   - `package.json` → Node.js + 具体框架（express/nest/next...）
   - `pyproject.toml` / `requirements.txt` → Python + 具体框架（django/fastapi/flask...）
   - `go.mod` → Go + 具体模块
   - `Cargo.toml` → Rust
   - `Dockerfile` / `docker-compose.yml` → 容器化方案
   - 数据库配置 → 使用的数据库
3. **关键入口文件** — 识别 `main.py`、`app.py`、`index.ts`、`main.go` 等入口，记录路径
4. **核心模块概览** — 每个主要目录的用途（一句话说明）

#### 4b. 对比已有 PROJECT.md

- **PROJECT.md 不存在** → 直接生成新文件
- **PROJECT.md 已存在** → 读取已有内容，对比当前扫描结果：
  - **目录结构有变化**（新增/删除了文件或目录） → 更新目录树和模块概览
  - **技术栈有变化**（新增/删除了依赖） → 更新技术栈部分
  - **无变化** → 跳过，输出提示 "PROJECT.md 无需更新"

#### 4c. PROJECT.md 格式

**获取当前时间：**

```bash
date "+%Y-%m-%d %H:%M:%S"
```

文件要简洁，让模型能一眼抓住重点：

```markdown
# 项目快照

> 更新时间: YYYY-MM-DD HH:mm:ss

## 技术栈

- 语言: Python 3.12
- 框架: FastAPI
- 数据库: PostgreSQL (asyncpg)
- 缓存: Redis
- 部署: Docker Compose

## 目录结构

```
项目名/
├── src/
│   ├── api/          # 路由和接口
│   ├── models/       # 数据模型
│   ├── services/     # 业务逻辑
│   └── utils/        # 工具函数
├── tests/            # 测试
├── main.py           # 入口
├── pyproject.toml
└── docker-compose.yml
```

## 关键入口

| 文件 | 用途 |
|------|------|
| `main.py` | 应用入口，启动 FastAPI |
| `src/api/router.py` | 路由注册 |
| `src/models/base.py` | ORM 基类 |

## 核心模块

| 目录 | 职责 |
|------|------|
| `src/api/` | HTTP 接口层，处理请求和响应 |
| `src/models/` | SQLAlchemy ORM 模型定义 |
| `src/services/` | 业务逻辑，被 api 层调用 |
```

### 第五步：输出结果

根据执行情况输出不同的提示：

**首次初始化：**

```
初始化完成！已创建:

  .xz_planning/
  ├── STATE.md        # 全局状态表
  ├── README.md       # 使用说明
  ├── PROJECT.md      # 项目快照索引
  ├── phases/         # 活跃版本目录
  └── archive/        # 归档目录

现在可以使用 /xz-plan N 需求描述 创建第一个版本计划。
```

**重复执行：**

```
项目已初始化，已更新:
  ✅ README.md — 已覆盖为最新版本
  ✅ PROJECT.md — 目录结构已更新（新增 src/middleware/）
  ⏭️ STATE.md — 无需更新
  ⏭️ phases/ — 已有 3 个版本，保持不变
```

或者：

```
项目已初始化，检查完毕:
  ✅ README.md — 已覆盖为最新版本
  ⏭️ PROJECT.md — 无变化，跳过
```

---

## 关键规则

1. **可重复执行** — 不会覆盖已有计划数据（phases/archive/STATE.md），只更新 README.md 和 PROJECT.md
2. **README.md 每次覆盖** — 确保文档始终是最新版本
3. **PROJECT.md 按需更新** — 有变化才更新，无变化跳过，避免无意义写入
4. **PROJECT.md 要简洁** — 是索引不是文档，让模型快速定位，不要长篇大论
5. **不涉及 git** — 纯文件操作
