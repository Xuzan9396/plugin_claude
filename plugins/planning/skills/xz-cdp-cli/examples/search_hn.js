// @url https://hn.algolia.com/?query={query}

// search_hn.js
// 运行方式：chrome-devtools run-script skill/chrome-devtools/examples/search_hn.js -a query="Rust"
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
