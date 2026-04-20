# 可视化辅助指南

基于浏览器的可视化辅助工具，用于在讨论过程中展示架构图、流程图、方案对比等可视化内容。

## 何时使用

逐问题判断，不是开启就全程用。判断标准：**用户看到比读到更容易理解吗？**

**用浏览器**展示本质上是视觉的内容：
- **架构图** — 系统组件、数据流、模块关系
- **流程图** — 状态机、业务流程、用户旅程
- **方案对比** — A/B/C 方案的卡片式可视化对比
- **UI 线框图** — 页面布局、导航结构、组件设计
- **实体关系图** — 数据模型、表关系

**用终端**处理文字或表格内容：
- **需求与范围问题** — "X 是什么意思？"、"哪些功能在范围内？"
- **概念性 A/B/C 选择** — 用文字描述的方案取舍
- **权衡清单** — 优缺点、对比表格
- **技术决策** — API 设计、数据建模、架构选型
- **澄清提问** — 任何答案是文字而非视觉偏好的问题

关于 UI 话题的问题不一定是视觉问题。"你想要什么样的向导？"是概念问题 — 用终端。"这两种向导布局哪个更好？"是视觉问题 — 用浏览器。

## 工作原理

服务端监视一个目录中的 HTML 文件，自动向浏览器提供最新的文件。你写 HTML 内容，用户在浏览器中看到，可以点击选择选项。选择记录到 `.events` 文件，你在下一轮读取。

**内容片段 vs 完整文档：** 如果 HTML 文件以 `<!DOCTYPE` 或 `<html` 开头，服务端原样提供（只注入辅助脚本）。否则，服务端自动用框架模板包裹你的内容 — 添加头部、CSS 主题、选择指示器和所有交互基础设施。**默认写内容片段。**

## 启动会话

脚本位于 `$SKILL_DIR/scripts/`（即 SKILL.md 同级的 `scripts/` 目录）。

`$SKILL_DIR` 是 SKILL.md「路径说明」第零步通过 `xz-tools.py skill-path xz-discuss` 查询得到的真实绝对路径，执行时替换为该值。

```bash
bash "<SKILL_DIR 真实绝对路径>/scripts/start-server.sh" --project-dir "$(pwd)"

# 返回: {"type":"server-started","port":52341,"url":"http://localhost:52341",
#        "screen_dir":"<项目根目录>/.xz_planning/visual/<pid>-<timestamp>"}
```

保存返回的 `screen_dir`，告知用户打开 URL。

**查找连接信息：** 服务端将启动 JSON 写入 `$SCREEN_DIR/.server-info`。如果后台启动未捕获 stdout，读取该文件获取 URL 和端口。使用 `--project-dir` 时，会话目录在 `<项目>/.xz_planning/visual/` 下。

**注意：** 不传 `--project-dir` 时文件放在 `/tmp`，会被系统清理。传入后文件持久化到项目的 `.xz_planning/visual/` 下。

## 使用循环

1. **检查服务存活**，然后**写 HTML** 到 `screen_dir` 的新文件：
   - 每次写入前检查 `$SCREEN_DIR/.server-info` 存在。不存在（或 `.server-stopped` 存在）说明服务已关闭 — 重启后继续。服务 30 分钟无活动自动退出。
   - 使用语义化文件名：`architecture.html`、`flow.html`、`comparison.html`
   - **不要复用文件名** — 每个页面用新文件
   - 用 Write 工具 — **不要用 cat/heredoc**
   - 服务端自动提供最新文件

2. **告知用户并结束回合：**
   - 每步都提醒 URL（不仅是首次）
   - 简要文字描述页面内容（如"展示 3 种架构方案对比"）
   - 请用户在终端回复

3. **下一轮** — 用户回复后：
   - 读取 `$SCREEN_DIR/.events`（如果存在）— 包含用户浏览器交互（点击、选择）的 JSON 行
   - 合并终端文字得到完整反馈
   - 终端消息是主要反馈；`.events` 提供结构化交互数据

4. **迭代或推进** — 如果反馈改变当前页面，写新文件（如 `architecture-v2.html`）。当前步骤验证通过才进入下一步。

5. **返回终端时卸载** — 下一步不需要浏览器时，推送等待页面清除过期内容：

   ```html
   <div style="display:flex;align-items:center;justify-content:center;min-height:60vh">
     <p class="subtitle">继续在终端中对话...</p>
   </div>
   ```

6. 重复直到完成。

## 编写内容片段

只写页面内部的内容。服务端自动用框架模板包裹。

**最小示例：**

```html
<h2>哪种架构方案更合适？</h2>
<p class="subtitle">考虑可扩展性和开发成本</p>

<div class="options">
  <div class="option" data-choice="a" onclick="toggleSelect(this)">
    <div class="letter">A</div>
    <div class="content">
      <h3>单体架构</h3>
      <p>快速开发，适合 MVP</p>
    </div>
  </div>
  <div class="option" data-choice="b" onclick="toggleSelect(this)">
    <div class="letter">B</div>
    <div class="content">
      <h3>微服务</h3>
      <p>高扩展性，前期成本高</p>
    </div>
  </div>
</div>
```

不需要 `<html>`、CSS、`<script>` 标签。服务端全部提供。

## 可用 CSS 类

### 选项（A/B/C 选择）

```html
<div class="options">
  <div class="option" data-choice="a" onclick="toggleSelect(this)">
    <div class="letter">A</div>
    <div class="content">
      <h3>标题</h3>
      <p>描述</p>
    </div>
  </div>
</div>
```

**多选：** 给容器加 `data-multiselect`。

### 卡片

```html
<div class="cards">
  <div class="card" data-choice="plan-a" onclick="toggleSelect(this)">
    <div class="card-body">
      <h3>方案 A</h3>
      <p>核心功能 + 部分扩展</p>
    </div>
  </div>
</div>
```

### 模拟容器

```html
<div class="mockup">
  <div class="mockup-header">预览：系统架构</div>
  <div class="mockup-body"><!-- 架构图 HTML --></div>
</div>
```

### 并排对比

```html
<div class="split">
  <div class="mockup"><!-- 方案 A --></div>
  <div class="mockup"><!-- 方案 B --></div>
</div>
```

### 优缺点

```html
<div class="pros-cons">
  <div class="pros"><h4>优点</h4><ul><li>...</li></ul></div>
  <div class="cons"><h4>缺点</h4><ul><li>...</li></ul></div>
</div>
```

### 排版

- `h2` — 页面标题
- `h3` — 小节标题
- `.subtitle` — 标题下副文字
- `.section` — 内容块
- `.label` — 小号标签文字

## 浏览器事件格式

```jsonl
{"type":"click","choice":"a","text":"方案 A - 单体架构","timestamp":1706000101}
{"type":"click","choice":"b","text":"方案 B - 微服务","timestamp":1706000115}
```

最后一个 `choice` 事件通常是最终选择。如果 `.events` 不存在，用户未在浏览器中交互。

## 清理

```bash
bash $SKILL_DIR/scripts/stop-server.sh $SCREEN_DIR
```

项目目录下的 `.xz_planning/visual/` 会保留可视化文件供后续查阅。仅 `/tmp` 临时会话会被自动删除。

## 参考

- 框架模板（CSS 参考）：`$SKILL_DIR/scripts/frame-template.html`
- 辅助脚本（客户端）：`$SKILL_DIR/scripts/helper.js`
