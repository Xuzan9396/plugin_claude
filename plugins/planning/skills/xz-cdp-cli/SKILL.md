---
name: xz-cdp-cli
description: 当用户要求“截取网站截图”“导航到某个 URL”“在浏览器中填写表单”“与 Chrome 交互”，或任务需要 Chrome 自动化时使用。
user-invocable: true
disable-model-invocation: true
---

# Chrome DevTools CLI

一个通过 DevTools Protocol 直接与当前运行中的 Chrome 通信的命令行工具。

## 前置条件

Chrome 必须启用远程调试：

1. 打开 Chrome。
2. 进入 `chrome://inspect/#remote-debugging`。
3. 启用远程调试服务器。

## 连接地址优先级

在运行任何页面命令前，先根据用户是否指定连接信息选择 Chrome，不得忽略用户给出的端口：

1. **用户提供完整 WebSocket 地址时，优先级最高。** 直接将它传给 `--ws-endpoint`。
2. **用户提供远程调试端口时，必须连接该端口。** `42223`、`端口 42223`、`--remote-debugging-port=42223` 都表示指定了端口。默认主机为 `127.0.0.1`；只有用户明确提供其他主机时才替换。
3. **用户未指定 WebSocket 地址或端口时，使用 CLI 默认自动连接。** 直接运行 `chrome-devtools list-pages`；首次调用会启动守护进程，后续命令会复用它，空闲 5 分钟后超时退出。

### 指定端口的正确连接方式

`--remote-debugging-port` 是 **Chrome 的启动参数**，不是 `chrome-devtools` 的参数。不得运行 `chrome-devtools --remote-debugging-port=42223 ...`。

例如用户提供 `42223` 端口时：

```bash
# 1. 读取该端口的浏览器级 WebSocket 地址
curl --fail --silent --show-error http://127.0.0.1:42223/json/version

# 2. 从返回 JSON 的 webSocketDebuggerUrl 字段取值，再显式连接
chrome-devtools --ws-endpoint "ws://127.0.0.1:42223/devtools/browser/<browser-id>" list-pages

# 3. 同一任务的后续命令继续携带同一 --ws-endpoint
chrome-devtools --ws-endpoint "ws://127.0.0.1:42223/devtools/browser/<browser-id>" --target warm-squid snapshot
```

必须使用 `/json/version` 实际返回的 `webSocketDebuggerUrl`，不得猜测或复用其他 Chrome 会话的 `<browser-id>`。Chrome 重启后该地址可能变化，应重新读取。

若指定端口无法访问、返回无效 JSON，或没有 `webSocketDebuggerUrl`，立即报告该端口连接失败。**不得静默回退到 CLI 默认连接**，否则可能操作错误的浏览器或标签页。

## ⚠️ 关键：页面目标的定位方式

**目标不是任意字符串。** 不得使用 `--target main`、`--target page1` 或任何自行编造的名称。

目标名是 CLI 根据 Chrome 内部 target ID 派生出的、便于阅读的双单词名称，例如 `warm-squid`、`pink-hen`。**必须从命令输出中获取，绝不能自行构造。**

目标名在标签页的生命周期内保持稳定：同一标签页内导航不会改变名称；关闭后重新打开则会获得新名称。

### 正确工作流

**第 1 步：运行 `list-pages` 查看已打开页面并取得目标名**

```bash
chrome-devtools list-pages
```

输出示例：

```text
[0] (warm-squid) Your Repositories — https://github.com/aeroxy
[1] (pink-hen) Gmail — https://mail.google.com
[2] (hazy-vole) Example — https://example.com
```

**第 2 步：在后续命令中使用输出里的友好名称**

```bash
chrome-devtools --target warm-squid navigate https://example.com
chrome-devtools --target pink-hen screenshot --output screenshot.png
```

**替代方式：使用 `--page <索引>` 按从 0 开始的数字索引定位**

```bash
chrome-devtools --page 0 navigate https://example.com
```

**若同时省略 `--target` 和 `--page`，命令会作用于第 0 个页面（最左侧标签页）。** 单标签页流程中可以这样做，但通常应避免；应始终固定到一个已知页面。

## 核心能力

- **导航**：`navigate`、`navigate --back`、`navigate --forward`、`navigate --reload`
- **页面管理**：`list-pages`、`new-page`、`close-page`、`select-page`
- **内容提取**：`screenshot`、`snapshot`（无障碍树）、`evaluate`（JavaScript）、`read-page`（Markdown 页面内容）、`run-script`（运行本地 JS 文件）、`adapter`（运行站点适配器）
- **交互**：`click`、`fill`、`type-text`、`press-key`、`hover`、`click-at`
- **模拟**：`emulate`（视口、移动端、地理位置、URL 阻止）
- **检查**：`console`、`network`、`sw-logs`（扩展 Service Worker 日志）
- **第三方工具**：`list-3p-tools`、`execute-3p-tool`（调用 `window.__dtmcp` 暴露的工具）
- **同步**：`wait-for`（等待页面中出现文本）
- **守护进程控制**：`kill-daemon`

## 标准模式

### 模式 1：导航与交互

`navigate` 与 `new-page` 会在输出末尾打印目标名；请捕获它，以便固定后续命令的页面。

```bash
# 1. 列出页面并找到目标
chrome-devtools list-pages

# 2. 导航（输出末尾会显示目标名）
chrome-devtools --target warm-squid navigate https://example.com
# stdout: Navigated to https://example.com
# stderr: [navigated to: https://example.com]
# stderr: [target:warm-squid]

# 3. 将所有后续命令固定到此页面
chrome-devtools --target warm-squid screenshot --output page.png
chrome-devtools --target warm-squid evaluate "document.title"

# 4. 打开新标签页，并从输出中捕获新的目标名
chrome-devtools new-page https://github.com
# stdout: Opened: https://github.com
# stderr: [target:icy-goat]  ← 新标签页、新目标
chrome-devtools --target icy-goat snapshot
```

**注意**：`[navigated to: ...]` 和 `[target:...]` 写入 **stderr**，而非 stdout。stdout 只包含命令的主要输出。

### 模式 2：模拟视口与地理位置

覆盖配置按标签页隔离。每个页面保留自己的视口、地理位置和 URL 阻止设置；它们在同一标签页内跨导航持续生效，直到被清除、标签页关闭或守护进程退出。无参数运行 `emulate` 可查看当前标签页状态。

```bash
# 设置视口与地理位置
chrome-devtools --target warm-squid emulate --viewport 1920x1080 --geolocation 40.71,-74.00

# 模拟移动设备
chrome-devtools --target warm-squid emulate --viewport 375x812 --mobile --device-scale-factor 3

# 带模拟配置导航（在 URL 加载前应用）
chrome-devtools --target warm-squid navigate https://example.com --viewport 375x812 --mobile

# 带模拟配置打开新标签页
chrome-devtools new-page https://example.com --viewport 375x812

# 查看当前覆盖配置
chrome-devtools --target warm-squid emulate

# 清除覆盖配置
chrome-devtools --target warm-squid emulate --clear-all
chrome-devtools --target warm-squid emulate --clear-viewport
chrome-devtools --target warm-squid emulate --clear-geolocation
```

### 模式 3：URL 阻止（网络调试）

用简单的 `*` 通配符阻止 URL：`*.png`、`cdn.example.com/*`、`*analytics*`。规则会一直保留在守护进程中，直到被清除。

> **作用范围：** 阻止只作用于页面加载的子资源（图片、脚本、fetch/XHR、样式表、CDN 和跟踪器），不会阻止顶层导航文档。例如设置 `--block-url "*example.com*"` 后，导航到 `https://example.com` 仍会加载页面，但相应子资源会被阻止。这是 Chrome `Network.setBlockedURLs` 的限制，不是 CLI 缺陷。

```bash
chrome-devtools --target warm-squid emulate --block-url "*.png"
chrome-devtools --target warm-squid emulate --block-url "*.ico" --block-url "*.svg"
chrome-devtools --target warm-squid --block-url "*.png" navigate https://example.com
chrome-devtools --target warm-squid emulate
chrome-devtools --target warm-squid emulate --unblock-url "*.png"
chrome-devtools --target warm-squid emulate --clear-blocks
chrome-devtools --target warm-squid emulate --clear-all
```

`--unblock-url` 会从阻止列表中移除该模式；不存在单独的“允许列表”。

### 模式 4：表单交互

填写输入框有两种方式，应按网站预期选择：

- `fill` 通过 `element.value = ...` 直接设置值。速度快，不触发按键事件，适用于文本框、文本域、`<select>`、复选框和单选框。React/Vue 依赖真实输入事件，因此这种方式经常无法正确更新它们的状态。
- `type-text` 逐个派发键盘事件，速度较慢，但会触发框架监听的 `input`、`compositionstart/end` 等事件。若 `fill` 看起来无效，应改用它。

```bash
chrome-devtools --target warm-squid click "button.submit"
chrome-devtools --target warm-squid click-at 100 200
chrome-devtools --target warm-squid fill "input.search" "search query"
chrome-devtools --target warm-squid type-text "search query" --submit-key Enter
chrome-devtools --target warm-squid press-key Enter
chrome-devtools --target warm-squid press-key Control+A
chrome-devtools --target warm-squid hover ".menu-item"
chrome-devtools --target warm-squid wait-for "Results" --timeout 10000
```

`click-at` 的坐标相对于可见视口，左上角为 `(0,0)`。`press-key` 支持 Enter、Tab、Escape、ArrowDown、Control+A、Meta+C、Shift+Tab、Backspace、Space 等。`wait-for` 默认超时为 30000 毫秒。

### 模式 5：控制台与网络检查

守护进程为当前页面维持持久会话，并跨命令持续收集网络与控制台事件。

`console` 和 `network` 会返回累积事件并清空缓冲区；紧接着再次调用通常为空，除非又产生了新事件。`--duration` 可用于实时监控。

```bash
chrome-devtools --target warm-squid navigate https://example.com
chrome-devtools --target warm-squid network
chrome-devtools --target warm-squid console
chrome-devtools --target warm-squid console --type error --type warning
chrome-devtools --target warm-squid network --type Fetch --type XHR
chrome-devtools --target warm-squid console --duration 5000
chrome-devtools --target warm-squid network --duration 3000
chrome-devtools --target warm-squid console --duration 0
```

`network --type` 的有效值为：`Document`、`Script`、`Stylesheet`、`Image`、`Media`、`Font`、`WebSocket`、`Manifest`、`XHR`、`Fetch`、`Other`，且区分大小写。控制台类型包括 `log`、`warning`、`error`、`info`、`debug`、`exception`。

### 模式 6：JavaScript 求值

`evaluate` 执行 JavaScript 表达式并返回结果。它会自动等待 Promise，并序列化返回值；对象转为 JSON，基本类型返回纯文本。

```bash
chrome-devtools --target warm-squid evaluate "document.title"
chrome-devtools --target warm-squid evaluate "fetch('/api/user').then(r => r.json())"
chrome-devtools --target warm-squid --json evaluate "performance.navigation"
chrome-devtools --target warm-squid evaluate "alert('hi')" --dialog-action accept
chrome-devtools --target warm-squid evaluate "confirm('sure?')" --dialog-action dismiss
chrome-devtools --target warm-squid evaluate "prompt('name')" --dialog-action "my-answer"
chrome-devtools --target warm-squid evaluate "JSON.stringify(performance.timing)" -o /tmp/perf.json
```

`--dialog-action` 可为 `accept`、`dismiss` 或任意提示框输入文本。若不提供该选项，触发对话框的求值可能挂起。

**不要用 `evaluate` 遍历 DOM。** 应使用 `snapshot` 阅读页面结构，使用 `click`/`fill` 进行交互。

### 模式 7：输出格式

所有命令默认输出便于人类阅读的文本。结构化输出可用 `--json` 或更紧凑、适合 LLM 的 `--toon`。

```bash
chrome-devtools list-pages
chrome-devtools list-pages --json
chrome-devtools list-pages --toon
chrome-devtools --target warm-squid snapshot --toon
chrome-devtools --target warm-squid network --toon --type Fetch
```

`--json` 与 `--toon` 互斥。

### 模式 8：快照（无障碍树）

理解页面结构时，应使用快照，而不是 `evaluate document.querySelector(...)`。

```bash
chrome-devtools --target warm-squid snapshot
chrome-devtools --target warm-squid snapshot --output /tmp/ax-tree.txt
chrome-devtools --target warm-squid snapshot --toon
```

### 模式 9：截图

```bash
# 默认：只截取视口，格式为 PNG
chrome-devtools --target warm-squid screenshot --output page.png

# 完整可滚动页面（可能非常高）
chrome-devtools --target warm-squid screenshot --full-page --output full-page.png

# 保存到指定路径
chrome-devtools --target warm-squid screenshot --output /tmp/whatever.jpg
```

### 模式 10：扩展 Service Worker 日志

这是浏览器级命令，不需要 `--target`。

```bash
chrome-devtools sw-logs --duration 2000
chrome-devtools sw-logs --duration 2000 --extension-id abcdef123456
```

### 模式 11：第三方开发者工具

适用于通过 `window.__dtmcp` 暴露工具的页面。

```bash
chrome-devtools --target warm-squid list-3p-tools
chrome-devtools --target warm-squid execute-3p-tool "<tool-name>" '<json-params>'
```

### 模式 12：以 Markdown 读取页面内容

将页面主要文章内容提取为干净的 Markdown。工具使用 Readability 识别正文，再转换为适合 LLM 的 Markdown，并附带标题、作者、摘要和 URL。非文章页面（SPA、仪表盘）会退回到转换完整页面。

```bash
chrome-devtools --target warm-squid read-page
chrome-devtools --target warm-squid read-page --output /tmp/article.md
chrome-devtools --target warm-squid read-page --json
```

JSON 输出包含 `title`、`byline`、`excerpt`、`site_name`、`url`。

- `read-page`：需要可阅读的 Markdown 文本时使用，适合文章、文档、Wiki、摘要和内容提取。
- `snapshot`：需要完整无障碍树、元素 ID、角色和交互元素时使用，适合理解结构和寻找点击/填写目标。

### 模式 13：本地 JavaScript 脚本（`run-script`）

在页面上下文中执行本地 JavaScript 文件。动态参数可在命令末尾作为原始位置值传入，也可使用 `-a/--arg`；工具会自动确定类型并注入为 `ctx.args`。支持通过注释中的 `@url` 自动导航。

完整说明见[自定义脚本指南](./CUSTOM_SCRIPTING.md)。

```bash
chrome-devtools --target warm-squid run-script skill/chrome-devtools/examples/search_hn.js -- "Rust"
```

### 模式 14：自定义域感知适配器（`adapter`）

运行站点专用适配器动作。若浏览器当前不在 JSDoc 头部 `@domain` 注释定义的匹配域名中，CLI 会先自动导航到该域名。

完整说明见[自定义脚本指南](./CUSTOM_SCRIPTING.md)。

```bash
chrome-devtools --target warm-squid adapter skill/chrome-devtools/examples/hn_adapter.js search -- "Rust"
```

### 模式 15：内存泄漏调试（堆快照）

在疑似泄漏操作前后分别拍摄堆快照，按类比较差异，再深入查看具体节点 ID。`compare-heapsnapshots` 与 `inspect-heapsnapshot-node` 完全离线，只解析本地文件，无需连接 Chrome。

```bash
# 1. 基准快照
chrome-devtools --target warm-squid take-heapsnapshot --output /tmp/base.heapsnapshot

# 2. 执行疑似泄漏操作，再拍第二个快照
chrome-devtools --target warm-squid take-heapsnapshot --output /tmp/current.heapsnapshot

# 3. 比较：每类一行，按大小增量排序
chrome-devtools compare-heapsnapshots --base /tmp/base.heapsnapshot --current /tmp/current.heapsnapshot

# 4. 查看某个汇总行的节点级增删详情（使用 idx 列）
chrome-devtools compare-heapsnapshots --base /tmp/base.heapsnapshot --current /tmp/current.heapsnapshot --class-index 0

# 5. 检查详情输出中的具体节点 ID
chrome-devtools inspect-heapsnapshot-node --file-path /tmp/current.heapsnapshot --node-id 12345
```

**⚠️ 两个快照必须来自同一个 Chrome 会话。** 差异比较依赖 V8 堆对象 ID，而该 ID 只在同一浏览器会话中稳定。跨 Chrome 重启、配置文件或机器比较毫无意义，几乎所有对象都会同时显示为新增与移除；CLI 检测到这种情况时会在 stderr 输出警告。

### 模式 16：无头 Chrome（无需登录态，无需人工批准）

当被测流程不需要用户的 Cookie 或登录凭据时，应启动一个一次性的无头 Chrome，而不是附着到用户自己的浏览器。由于该实例启动时就已开启远程调试，**不会出现任何授权确认弹窗**，整个流程可无人值守运行。

```bash
PROFILE=$(mktemp -d)

# 1. 若守护进程已附着到用户的真实 Chrome，先终止它
#    （守护进程按用户维度存在，且会一直粘在它首次连接的那个 Chrome 上）
chrome-devtools kill-daemon --force

# 2. 用隔离的配置目录启动无头 Chrome；端口 0 表示自动选择空闲端口
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless=new --remote-debugging-port=0 \
  --user-data-dir="$PROFILE" \
  --no-first-run --no-default-browser-check \
  about:blank &
CHROME_PID=$!

# 3. 清理逻辑 —— 即使后续步骤失败也必须执行：守护进程已绑定到这个无头实例，
#    否则会劫持后续本应发往用户真实 Chrome 的命令。用 trap 保证任何退出路径都会清理，
#    而不只是成功路径。
cleanup() {
  chrome-devtools kill-daemon --force
  kill "$CHROME_PID" 2>/dev/null
  # Chrome 是异步关闭的，发出 SIGTERM 后立即删除配置目录会与它的退出流程竞争，
  # 可能导致 Chrome 仍在运行却指向一个已不存在的目录。因此要等待进程真正退出，
  # 但需设上限（5 秒），超时后改用 SIGKILL，避免忽略 SIGTERM 的 Chrome 把 trap 卡死。
  for _ in $(seq 1 20); do
    kill -0 "$CHROME_PID" 2>/dev/null || break
    sleep 0.25
  done
  if kill -0 "$CHROME_PID" 2>/dev/null; then
    kill -9 "$CHROME_PID" 2>/dev/null
  fi
  wait "$CHROME_PID" 2>/dev/null
  rm -rf "$PROFILE"
}
trap cleanup EXIT

# 4. DevToolsActivePort 只在 DevTools 服务真正开始监听之后才写入，
#    因此就绪信号是该文件是否存在，而不是进程是否存活；过早连接会与启动过程竞争。
#    同样设上限（30 秒）并监控 PID，让崩溃或根本没起来的 Chrome 直接让脚本失败，
#    而不是永久挂起。
for _ in $(seq 1 60); do
  [ -f "$PROFILE/DevToolsActivePort" ] && break
  kill -0 "$CHROME_PID" 2>/dev/null || { echo "Chrome exited during startup" >&2; exit 1; }
  sleep 0.5
done
[ -f "$PROFILE/DevToolsActivePort" ] || { echo "Chrome not ready after 30s" >&2; exit 1; }

# 5. 每条命令都需要用 --user-data-dir 指向该无头配置目录；
#    CLI 会读取其中的 DevToolsActivePort 自动连接
chrome-devtools --user-data-dir "$PROFILE" navigate https://example.com
chrome-devtools --user-data-dir "$PROFILE" evaluate 'document.title'
chrome-devtools --user-data-dir "$PROFILE" screenshot --output /tmp/shot.png
```

Linux 环境下，把 macOS 的 `.app` 二进制路径替换为 `$PATH` 中的 `google-chrome` 或 `chromium`。

**⚠️ 每个用户只有一个守护进程，且绑定单个 Chrome。** 守护进程会连接到第一条命令解析出的那个 Chrome，后续命令即使参数指向别处也仍会复用它。在用户的 Chrome 与无头实例之间切换时，**两个方向都必须**执行 `kill-daemon --force`（即上面的第 1 步与 EXIT trap）。

## 完整命令参考

### 导航

```bash
chrome-devtools list-pages
chrome-devtools navigate <url> [--viewport WxH] [--mobile] [--device-scale-factor N] [--geolocation lat,lon]
chrome-devtools navigate <url> --extra-headers '{"Authorization":"Bearer ..."}'
chrome-devtools navigate --back
chrome-devtools navigate --forward
chrome-devtools navigate --reload
chrome-devtools new-page <url> [--viewport WxH] [--mobile]
chrome-devtools close-page [index_or_target_name]
chrome-devtools select-page [index_or_target_name]
```

### 检查

```bash
chrome-devtools --target <name> screenshot [--output <path>] [--full-page]
chrome-devtools --target <name> snapshot
chrome-devtools --target <name> read-page [--output <path>]
chrome-devtools --target <name> evaluate "<js-expression>" [--dialog-action accept|dismiss|text]
chrome-devtools --target <name> network [--duration <ms>] [--type <resource>]
chrome-devtools --target <name> console [--duration <ms>] [--type <level>]
chrome-devtools sw-logs [--duration <ms>] [--extension-id <id>]
```

### 内存（堆快照）

```bash
chrome-devtools --target <name> take-heapsnapshot --output <path.heapsnapshot>
chrome-devtools compare-heapsnapshots --base <path> --current <path> [--class-index N]
chrome-devtools inspect-heapsnapshot-node --file-path <path> --node-id <id>
```

### 交互

```bash
chrome-devtools --target <name> click "<css-selector>"
chrome-devtools --target <name> click-at <x> <y>
chrome-devtools --target <name> fill "<css-selector>" "<value>"
chrome-devtools --target <name> type-text "<text>" [--submit-key <key>]
chrome-devtools --target <name> press-key <key>
chrome-devtools --target <name> hover "<css-selector>"
chrome-devtools --target <name> wait-for "<text>" [--timeout <ms>]
```

### 模拟

```bash
chrome-devtools --target <name> emulate [--viewport WxH] [--mobile] [--geolocation lat,lon]
chrome-devtools --target <name> emulate
chrome-devtools --target <name> emulate --block-url "<pattern>" [--block-url ...]
chrome-devtools --target <name> emulate --unblock-url "<pattern>"
chrome-devtools --target <name> emulate --clear-blocks
chrome-devtools --target <name> emulate --clear-viewport
chrome-devtools --target <name> emulate --clear-geolocation
chrome-devtools --target <name> emulate --clear-all
```

### 第三方工具

```bash
chrome-devtools --target <name> list-3p-tools
chrome-devtools --target <name> execute-3p-tool <name> '<json-params>'
```

### 自定义脚本与适配器

```bash
chrome-devtools --target <name> run-script <file-path> [--arg key=value] [--output <path>] [--track-navigation]
chrome-devtools --target <name> adapter <file-path> <function-name> [--arg key=value] [--output <path>] [--track-navigation]
```

### 守护进程

```bash
chrome-devtools kill-daemon
chrome-devtools kill-daemon --force
```

第一条在非交互环境（如智能体）中会拒绝执行，除非加 `--force`；第二条会无条件终止守护进程。

## 失败处理：“Failed to connect to Chrome”或命令挂起

Chrome 远程调试连接首次需要用户在 Chrome 中批准一次对话框。若命令挂起或出现连接/超时错误，最可能的原因是该对话框正等待人工操作，而不是可通过重试修复的缺陷。

若命令长时间挂起，或报错 `Failed to connect to Chrome`、`Timed out ... connecting to Chrome`：

1. **最多重试一次**，因为用户可能刚刚完成批准。
2. 若仍失败，**立即停止**。不要不断重试；用户很可能不在键盘旁，重试无法替用户批准。
3. 直接告知用户 Chrome 正在等待其批准远程调试连接，并等待用户回复。

**绝不能用 `kill-daemon`“修复”连接问题。** 它不会解决问题，反而会销毁可能已经获批的守护进程连接，保证下一次尝试必须重新人工批准。作为智能体，只有在用户因其他原因明确要求终止守护进程时（例如无关的 JS 执行卡死），才可传 `--force`；不得把它当作连接失败的应对措施。

## 关键陷阱

### ✗ 错误：使用自行编造的目标名

```bash
chrome-devtools --target main navigate https://example.com
chrome-devtools --target page1 screenshot
chrome-devtools --target "my-page" evaluate "..."
```

### ✓ 正确：从命令输出取得目标名

```bash
chrome-devtools list-pages
# [0] (warm-squid) Example — https://example.com
chrome-devtools --target warm-squid navigate https://github.com
```

### ✗ 错误：未先确定目标就运行命令

```bash
chrome-devtools screenshot --output page.png
```

### ✓ 正确：始终先识别页面

```bash
chrome-devtools list-pages
chrome-devtools --target warm-squid screenshot --output page.png
```

### ✗ 错误：用 `evaluate` 遍历 DOM 或进行交互

```bash
chrome-devtools --target warm-squid evaluate "document.querySelector('...').click()"
```

### ✓ 正确：用 `snapshot` 查看结构，用 `click`/`fill` 交互

```bash
chrome-devtools --target warm-squid snapshot
chrome-devtools --target warm-squid click "button.submit"
```

### ✗ 错误：期待 `fill` 更新 React/Vue 表单状态

```bash
chrome-devtools --target warm-squid fill "input" "value"
```

### ✓ 正确：对有状态框架使用 `type-text`

```bash
chrome-devtools --target warm-squid type-text "value"
```

### ✗ 错误：期望 `console`/`network` 在读取清空后继续保留事件

```bash
chrome-devtools --target warm-squid console
chrome-devtools --target warm-squid console
# 第二次通常为空，因为第一次已经清空缓冲区
```

### ✓ 正确：把每次读取视为一个新窗口

在产生事件的操作后立即运行 `console`/`network`，或使用 `--duration` 在指定时间窗口内收集。

### ✗ 错误：连接失败后循环重试或运行 `kill-daemon`

```bash
chrome-devtools list-pages
chrome-devtools kill-daemon --force
chrome-devtools list-pages
```

### ✓ 正确：只重试一次，然后停止并请求人工批准

```bash
chrome-devtools list-pages
chrome-devtools list-pages
# 仍失败：停止重试，告知用户 Chrome 需要人工批准，并等待
```

## 输出格式汇总

| 标志 | 说明 |
|---|---|
| *无* | 便于人类阅读的文本（默认） |
| `--json` | 格式化 JSON |
| `--toon` | TOON：紧凑表格格式，供 LLM 智能体节省 token |

`--json` 与 `--toon` 互斥。

## stdout 与 stderr

- **stdout** 包含主要命令输出：表格、文本、JSON 或 TOON。
- **stderr** 包含提示行（`[target:...]`、`[navigated to: ...]`）和错误。

以程序方式解析命令输出时，只读取 stdout 以取得主要结果。
