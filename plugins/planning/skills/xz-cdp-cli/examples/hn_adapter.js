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
