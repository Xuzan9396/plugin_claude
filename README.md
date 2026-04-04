# XZ Planning 插件 - 安装指南

## 方式一：本地市场安装（推荐）

### 1. 添加市场

在 Claude Code 中执行：

```
本地
/plugin marketplace add /Users/admin/go/src/myai/plugin_claude
云端
/plugin marketplace add Xuzan9396/plugin_claude
```

### 2. 安装插件

```
/plugin install xz-planning@xz-tools
```

### 3. 重载插件

```
/reload-plugins
```

### 4. 验证

运行 `/help` 查看是否出现 `xz-planning:` 前缀的命令，或直接试：

```
/xz-planning:xz-status
```

---

## 方式二：--plugin-dir 直接加载（开发调试用）

跳过市场，直接加载插件目录：

```bash
claude --plugin-dir /Users/admin/go/src/myai/planning_plugin_claude/plugins/xz
```

每次修改插件后在会话内执行 `/reload-plugins` 即可热更新。

---

## 目录结构

```
/Users/admin/go/src/myai/planning_plugin_claude/
├── .claude-plugin/
│   └── marketplace.json        ← 市场定义（名称: xz-tools）
└── plugins/
    └── xz/                     ← xz-planning 插件
        ├── .claude-plugin/
        │   └── plugin.json     ← 插件清单（名称: xz-planning）
        ├── skills/             ← 13 个 skill（xz-plan, xz-exec 等）
        ├── agents/             ← 子代理（xz-code-reviewer）
        ├── bin/                ← 辅助脚本（xz-tools.py）
        └── resources/          ← README 模板
```

## 命令速查

安装后所有命令带 `xz-planning:` 前缀：

| 命令 | 用途 |
|------|------|
| `/xz-planning:xz-init` | 初始化项目计划目录 |
| `/xz-planning:xz-plan 1 需求描述` | 创建版本计划 |
| `/xz-planning:xz-exec 1` | 执行 todolist |
| `/xz-planning:xz-status` | 查看状态 |
| `/xz-planning:xz-done 1` | 归档版本 |

完整命令列表见 `/help`。

---

## 卸载插件

卸载单个插件（市场保留）：

```
/plugin uninstall xz-planning@xz-tools
```

## 删除市场

删除市场会同时卸载该市场下所有已安装的插件：

```
/plugin marketplace remove xz-tools
```

如果只想刷新市场内容而不删除：

```
/plugin marketplace update xz-tools
```

## 查看已安装

```
/plugin marketplace list
```

---

## 新增插件到市场

### 1. 创建插件目录

在 `plugins/` 下新建目录，包含 `.claude-plugin/plugin.json` 和功能文件：

```
plugins/
├── xz/                      ← 现有插件
└── my-new-plugin/            ← 新插件
    ├── .claude-plugin/
    │   └── plugin.json       ← {"name": "my-new-plugin", "version": "1.0.0", ...}
    ├── skills/
    │   └── hello/
    │       └── SKILL.md
    └── bin/                  ← 可选
```

### 2. 在 marketplace.json 追加条目

编辑 `/Users/admin/go/src/myai/planning_plugin_claude/.claude-plugin/marketplace.json`，在 `plugins` 数组中追加：

```json
{
  "name": "my-new-plugin",
  "source": "./plugins/my-new-plugin",
  "description": "插件描述",
  "version": "1.0.0"
}
```

### 3. 用户侧安装

已添加过市场的用户先更新市场，再安装新插件：

```
/plugin marketplace update xz-tools
/plugin install my-new-plugin@xz-tools
```

新用户直接添加市场后安装即可。
