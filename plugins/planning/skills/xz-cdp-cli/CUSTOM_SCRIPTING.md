# 自定义脚本与适配器指南

本指南介绍如何使用 Chrome DevTools CLI 创建并执行自定义 JavaScript 脚本（`run-script`）和具备域名感知能力的自定义适配器（`adapter`）。

---

## 1. 自定义脚本（`run-script`）

`run-script` 读取本地 JavaScript 文件，将其包装进立即调用函数表达式（IIFE），并直接在目标浏览器的页面上下文中执行。

### 灵活的参数语法

传给脚本的动态参数可采用多种形式。参数会被自动解析，并通过 `ctx.args` 提供给脚本。注意：以下第 2、3 种形式中的原始位置值必须放在字面量 `--` 之后；`--output`、`--track-navigation` 等选项必须放在它之前。

1. **通过 `-a`/`--arg` 传入命名参数（推荐）**

   使用可重复的 `-a`/`--arg` 标志传入一个或多个 `key=value`，无需 `--` 分隔符：

   ```bash
   chrome-devtools run-script search_hn.js -a query="Rust"
   ```

2. **纯位置参数**

   在 `--` 后追加原始位置字符串。若只有一个尾随位置参数，它会自动同时映射到 `ctx.args.query` 和 `ctx.args._0`：

   ```bash
   chrome-devtools run-script search_hn.js -- "Rust"
   ```

3. **混合形式（`--` 后的位置参数与命名参数）**

   ```bash
   chrome-devtools run-script search_hn.js -- "Rust" limit=10 safeSearch=true
   ```

### 基于注释的自动导航

在脚本文件顶部声明标准的 `// @url <target_url>` 或 `// @navigate <target_url>` 注释标记后，CLI 会在执行脚本前检查活动标签页的当前 URL。

若活动标签页当前不在与目标 URL 匹配的域名中，**CLI 会先自动导航到目标 URL**，等待页面加载，然后执行脚本。`@url` 模板内可使用 `{arg_name}` 占位符动态插入 CLI 参数：

```javascript
// @url https://hn.algolia.com/?query={query}
```

---

## 2. 自定义域感知适配器（`adapter`）

`adapter` 读取本地自定义 JavaScript 适配器文件，解析目标 `@domain` JSDoc 标记，确保浏览器位于匹配域名后，再调用脚本内指定的具名函数。

### 域名保护与自动导航

在适配器文件顶部声明标准 `@domain` 标记后，CLI 会在执行函数前检查活动页面 URL。若活动标签页不在目标域名中，**它会自动导航到第一个目标域名**，等待加载完成，然后运行适配器。

```javascript
// ==UserAdapter==
// @name         Hacker News 搜索适配器
// @domain       hn.algolia.com
// ==/UserAdapter==
```

---

## 3. 注入的辅助上下文（`ctx`）

`run-script` 和 `adapter` 函数都会收到注入的 `ctx` 上下文，其中包含以下标准工具：

- `ctx.args`：包含已确定类型的键值参数的对象。
- `ctx.wait(ms)`：休眠/延迟工具，例如 `await ctx.wait(1000)`。
- `ctx.waitForText(text, timeout_ms)`：轮询页面正文，直到出现指定字符串；默认超时 30 秒。
- `ctx.waitForSelector(selector, timeout_ms)`：轮询 DOM，直到存在匹配 CSS 选择器的元素。
- `ctx.click(selector)`：DOM 点击辅助函数。
- `ctx.fill(selector, value)`：DOM 值输入辅助函数。它会覆盖标准 value setter 并触发相应事件，因此与 React、Vue、Angular 等有状态框架高度兼容。

---

## 4. 真实 SPA 示例（Hacker News 搜索）

以下示例可在 `hn.algolia.com` 上运行。

### 脚本文件（`skill/xz-cdp-cli/examples/search_hn.js`）

```javascript
// @url https://hn.algolia.com/?query={query}

// search_hn.js
// 运行方式：chrome-devtools run-script skill/xz-cdp-cli/examples/search_hn.js -a query="Rust"
//
// run-script 会注入 `ctx`，并在异步上下文中执行本文件。
// 上面的 `@url` 会让 CLI 先自动导航到预渲染的查询 URL。

const query = ctx.args.query;
if (!query) {
  throw new Error("缺少 query 参数，请使用 '-a query=...' 传入");
}

// 等待结果更新/加载
await ctx.waitForSelector("article.Story", 10000);

// 提取结果
const results = Array.from(document.querySelectorAll("article.Story")).map(el => {
  const titleEl = el.querySelector(".Story_title a");
  const metaEl = el.querySelector(".Story_meta");
  return {
    title: titleEl?.innerText.trim() || "",
    meta: metaEl?.innerText.trim() || "",
    url: titleEl?.href || ""
  };
});

return results;
```

### 适配器文件（`skill/xz-cdp-cli/examples/hn_adapter.js`）

```javascript
// ==UserAdapter==
// @name         Hacker News 搜索适配器
// @domain       hn.algolia.com
// ==/UserAdapter==

// 运行方式：chrome-devtools adapter skill/chrome-devtools/examples/hn_adapter.js search -a query="Rust"

async function search(ctx) {
  const query = ctx.args.query;
  if (!query) throw new Error("缺少 query 参数");

  // 填写搜索框；该 SPA 会动态请求并渲染结果
  await ctx.fill("input.SearchInput", query);

  // 稍等 React、网络请求和 DOM 更新完成
  await ctx.wait(1500);

  // 等待结果更新/加载
  await ctx.waitForSelector("article.Story", 10000);

  const results = Array.from(document.querySelectorAll("article.Story")).map(el => {
    const titleEl = el.querySelector(".Story_title a");
    const metaEl = el.querySelector(".Story_meta");
    return {
      title: titleEl?.innerText.trim() || "",
      meta: metaEl?.innerText.trim() || "",
      url: titleEl?.href || ""
    };
  });

  return results;
}
```
