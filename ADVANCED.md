# 技术参考（给安装 agent 和开发者）

日常使用请先看 [首页](README.md)。下面保留详细参数与验证说明。

## 项目内的账号 JSON

`canvas-account.local.json` 支持 `base_url`、`api_key`、`timezone`，可直接用作 `CANVAS_CONFIG` 或向导的 `--config-path`。例如 `python setup_canvas.py --client deepseek --config-path ./canvas-account.local.json`。填写后无需再传 `--base-url` 或 `--token-file`；key 不会进入命令参数。`read_token` 也支持从 JSON 的 `api_key` 读取，保留原有凭据文件工作流。

新安装在没有现有设置时由向导创建此文件，并将绝对路径固定到客户端。已有 `CANVAS_CONFIG`、源码 `canvas.toml`、已存在的用户配置文件优先保留；之后才选择源码目录里的本地 JSON。已有同名客户端配置指向别处时应换一个 `--name`，不要覆盖。公开示例始终留空，填写后的本地文件排除在 Git 和分发包之外。

## Codex 详细部署

# Codex deployment guide

This repository installs a local, read-only Canvas LMS MCP server. Installation, MCP registration, and Canvas account authorization are separate steps. Never report a live Canvas connection based only on a successful installation or tool listing.

## 1. Install the repository

Use Python 3.11 or newer. Clone the repository into a directory chosen by the user, inspect `AGENTS.md`, then run:

```bash
python3 install.py --register-codex
```

On Windows, use `py -3 install.py --register-codex`. The script finds the checkout using its own location, creates `.venv`, installs the pinned runtime dependencies and this package, runs an offline MCP self-test, and registers a server named `canvas` if the Codex CLI is available. It works when invoked from a different working directory.

Do not overwrite an existing MCP entry. If `canvas` is already used for another server, select a new name with `--name canvas-lms`. Repeating registration with the same command and configuration is safe.

If the Codex CLI is unavailable, the script returns `registered: false` and a portable manual MCP configuration. Apply that configuration in the user's MCP settings using the available client interface; do not claim registration succeeded until it has been read back.

## 2. Configure account access locally

Read [AUTHENTICATION.md](AUTHENTICATION.md). This developer preview consumes an existing institution-approved access credential; it does not include an OAuth login or refresh service. Do not solicit raw access tokens in a chat or commit them to the repository. Ask only for the Canvas HTTPS domain, preferred IANA timezone, and the path to a credential file already provisioned through the approved process. If this information is missing, finish installation and the offline self-test first, then clearly report that account configuration is pending.

With the virtual environment activated, configure an existing UTF-8 credential file or a DOCX containing one credential:

```bash
canvas-bridge configure \
  --base-url https://canvas.example.edu \
  --token-file /absolute/private/path/credentials.token \
  --timezone Asia/Hong_Kong
canvas-bridge register-codex
canvas-bridge doctor
```

These are examples: use the user's real domain, local file path, and timezone. Never put the token value in arguments. The credential is referenced locally and is not copied into the MCP settings.

The default private configuration is `%APPDATA%/canvas-agent-bridge/config.toml` on Windows and `$XDG_CONFIG_HOME/canvas-agent-bridge/config.toml` (normally `~/.config/canvas-agent-bridge/config.toml`) elsewhere. Configuration creation uses restrictive file permissions where supported and refuses to overwrite a different existing file without `--force`.

Use `--config-path` on `configure` and `register-codex` to isolate multiple accounts. The generated MCP entry pins this file with `CANVAS_CONFIG` so it works from any chat or working directory.

## 3. Verify the result

```bash
canvas-bridge self-test
canvas-bridge doctor
canvas-bridge call list_courses
canvas-bridge call get_upcoming_work --args '{"days":14}'
```

`self-test` must return `ok: true` and `tool_count: 14`. It does not connect to Canvas. `doctor` must independently return `ok: true` after a successful authenticated request. Handle 401/403/404, unknown submission state, `partial`, and `truncated` explicitly.

Reconnect the MCP client to refresh tools. A running chat may retain its original tool inventory. The same installation can also be used through `python -m canvas_bridge` or the `canvas-bridge` command.

## Configuration precedence

1. Explicit `CANVAS_CONFIG` or a command's `--config-path`.
2. An existing private `canvas.toml` in a source checkout, for compatibility with early personal installations.
3. The per-user configuration path above.

`CANVAS_BASE_URL`, `CANVAS_TOKEN_FILE`, `CANVAS_TOKEN`, and `CANVAS_TIMEZONE` override their corresponding settings. Environment-only configuration is supported without a TOML file when `CANVAS_CONFIG` is not explicitly set. Do not print environment values. `CANVAS_TOKEN` must be provisioned locally through an approved process.

## Updates and troubleshooting

- Pull an approved update and rerun `install.py`. Existing credential files, different private configurations, and conflicting MCP entries are preserved.
- Python cannot create the virtual environment: install the operating system's `venv` support or select a supported Python interpreter.
- Missing configuration: complete step 2; do not change Canvas interface feature switches.
- Fake-IP proxy: by default private download addresses are blocked. If required by the local proxy, explicitly allow only verified Canvas content domains using `proxy_fake_ip_domains`; see `canvas.example.toml` and the [official domain list](https://community.instructure.com/en/kb/articles/485223-canvas-domain-email-and-server-management).
- OAuth token expired: refresh it through the institution's approved authorization system; automatic refresh is not implemented by this preview.

Codex's supported registration command and configuration are described in the [official OpenAI MCP documentation](https://developers.openai.com/codex/mcp).


## DeepSeek 详细部署

# DeepSeek Harness 版本

本版本面向 DeepSeek 官方 [deepseek-ai/deepseek-harness](https://github.com/deepseek-ai/deepseek-harness)，通过 `@deepseek-ai/dsh-mcp-client` 接入本地 Canvas MCP。它复用本项目的 14 个只读工具，包含独立安装入口和 Cordis overlay 导出。无需调用 Codex，也无需在本项目保存 DeepSeek API key。模型和模型授权由 Harness 自己管理。

## 给安装 agent 的指令

> 请把 https://github.com/Linklee-sad/Canvas-Agent-MCP 安装到 DeepSeek Harness。先阅读 AGENTS.md、DEEPSEEK.md 和 AUTHENTICATION.md。运行 install_deepseek.py，完成离线自检，生成独立 Cordis overlay，然后使用已有官方 dsh 验证配置组合与 MCP 工具发现。保留已有 Harness profile、模型设置和凭据；没有 Canvas 授权时先完成安装，不要让我把令牌贴进聊天。

## 安装和配置

需要 Python 3.11+。先按 [DeepSeek 官方安装指南](https://github.com/deepseek-ai/deepseek-harness) 安装可用的 `dsh`；当前 CLI 自带 MCP 客户端。克隆本仓库后执行：

```bash
python3 install_deepseek.py
# Windows: py -3 install_deepseek.py
```

脚本创建虚拟环境、安装依赖、验证 MCP stdio 和 14 个工具，再导出独立配置。它支持从其他工作目录通过脚本绝对路径调用。它不会安装或启动 Harness，也不会改写现有 profile、home patch、模型设置或 Codex 配置。共享安装入口的等价参数是 `python3 install.py --deepseek`。

默认导出位置为用户配置目录下的 `deepseek-canvas.cordis.patch.yml`。输出为 JSON 格式的 YAML 1.2 子集，可由 Cordis patch loader 直接读取，能保留 Windows 路径与特殊字符。它只引用 Python 可执行文件和 Canvas 私有配置路径，不包含令牌。重复导出相同配置安全；已有不同内容会拒绝覆盖。

自定义位置、服务名称和目标 profile：

```bash
python3 install_deepseek.py --name canvas-study --deepseek-profile web --deepseek-output /absolute/private/path/canvas.cordis.patch.yml
```

若 Canvas 授权尚未配置，按照 [AUTHENTICATION.md](AUTHENTICATION.md) 使用已有机构批准的本地凭据文件。在虚拟环境中执行：

```bash
canvas-bridge configure --base-url https://canvas.example.edu --token-file /absolute/private/path/credentials.token --timezone Asia/Hong_Kong
canvas-bridge export-deepseek --profile web --output /absolute/private/path/canvas.cordis.patch.yml
canvas-bridge doctor
```

多个账号可在 `configure`、`export-deepseek` 中指定同一个 `--config-path`，不同服务使用不同 `--name` 和 `--output`。导出前已有私有 `canvas.toml` 的个人源码部署仍兼容。首次配置默认使用用户配置目录；以导出文件内 `CANVAS_CONFIG` 指向的文件为准。若改变了配置路径，应重新导出到新文件并更新启动参数。

Harness 会过滤环境中的凭据变量；本适配通过显式 `CANVAS_CONFIG` 读取本地私有文件，不依赖继承 `CANVAS_TOKEN`。不要将原始令牌加入 overlay。账户授权与 v0.3 一致：当前没有内建 OAuth 登录或自动刷新；其他使用者需配置自己的授权。

## 启动 Harness

使用导出结果的 `launch_argv`，或将实际 overlay 路径代入：

```bash
dsh --profile web --patch /absolute/private/path/canvas.cordis.patch.yml
```

配置按官方 `insert` patch 格式加入一个 MCP 客户端；它与现有 patch 叠加。相同作用域内服务名称必须唯一。冲突时用新名称重新导出，不要替换已有插件。

headless 模式也使用相同 overlay；launcher 参数必须在任务文字前：

```bash
dsh --profile headless --patch /absolute/private/path/canvas.cordis.patch.yml "用 Canvas 工具汇总未来两周待办，附截止时间和原文链接。"
```

`--profile sdk` 与 `--profile acp` 可供已有自动化客户端使用。Desktop 的启动入口由其安装版本管理，本文不声称通过 npm CLI 注册 Desktop。

## 验证

1. `canvas-bridge self-test`：`ok: true`、14 个工具，只证明 Python MCP 能工作。
2. `dsh --profile web --patch <overlay> --dump-config`：仅在本机检查目标客户端的配置组合。它不启动 MCP，不能作为连接成功的证据；完整配置可能包含其他私人设置，不要上传或贴入聊天。
3. 实际启动目标 Harness profile，确认发现 `mcp__canvas__list_courses`、`mcp__canvas__get_upcoming_work` 等共 14 个工具。默认服务名是 `canvas`；自定义名称会改变前缀。仅导出成功时结果明确为 `registered: false`、`harness_connection_verified: false`。
4. 使用自己的授权运行 `canvas-bridge doctor`，并在 Harness 中调用一次 `list_courses`。Canvas 401/403、未知提交状态和部分结果必须原样报告。

可单独查看无凭据的 Cordis patch：`canvas-bridge config --client deepseek`。工具调用超时设为 120 秒；重连使用官方客户端默认值。原有 Codex 接入仍可独立使用。

## 官方依据

- [MCP 客户端字段、作用域与环境过滤](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/mcp/mcp-client/README.md)
- [官方 MCP overlay 示例与启用方式](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/user/guide/mcp-memory.md)
- [CLI profiles、patch 组合及配置检查](https://github.com/deepseek-ai/deepseek-harness/blob/master/apps/cli/reference/README.md)

DeepSeek Harness 仍在开发预览，接口可能变化；本适配以官方 `@deepseek-ai/dsh` 的 Cordis MCP 接口为依据。

## 维护者集成验证

已用官方 `@deepseek-ai/dsh@0.2.1-alpha.3` 验证配置组合、MCP 插件发现全部 14 个工具及错误传播。可复现的本机检查如下（路径替换为实际安装位置）：

```bash
node scripts/verify_deepseek.mjs --harness-package /path/to/node_modules/@deepseek-ai/dsh/package.json --overlay /absolute/private/path/canvas.cordis.patch.yml
```

此检查加载真实 Cordis、工具注册表和官方 MCP 客户端，不请求模型，不创建用户会话；不证明已有 Web/SDK 会话已经加载该 overlay。可加 `--check-canvas` 用自己的现有授权执行一次只读课程查询；输出只给连接状态，不显示课程正文或凭据。CI 使用临时目录和虚构授权，不访问真实课程。


## 14 个工具

| 工具 | 用途 |
| --- | --- |
| `list_courses` | 列出课程，可按名称和课程代码过滤 |
| `get_course` | 读取课程信息和 syllabus |
| `list_assignments` | 作业、截止时间及可用的本人提交状态 |
| `get_assignment` | 作业正文、rubric 和附件链接 |
| `list_modules` | 课程模块 |
| `list_module_items` | 模块中的文件、页面和任务索引 |
| `list_pages` / `get_page` | 查找和读取课程页面 |
| `list_announcements` | 按显式日期范围读取公告 |
| `list_course_materials` | 文件名搜索；必要时尝试模块文件索引 |
| `download_material` | 下载到本地缓存，核验大小和 SHA256 |
| `read_material` | 按页、幻灯片、段落或行读取文字，支持页内续读 |
| `get_upcoming_work` | 合并 Assignments 与 Planner，跨课程去重汇总 |
| `get_assignment_context` | 作业材料及其关联依据、来源覆盖和缺失信息 |

## 结果如何理解

- `source_url`、`html_url` 和 `fetched_at` 保留出处与查询时间。
- `partial`、`truncated`、`coverage` 和 `warnings` 标明未读取、受限或达到上限的内容。
- 未知提交状态不会被推断为未提交；手动标记完成也不会被描述为提交凭证。
- 待办默认覆盖今天起 14 天和过去 7 天，配置时区以私有配置为准；无截止日期项目单列为 `undated_items`。
- 作业上下文分别标注直接链接、标题匹配候选和同模块候选。附件预览默认关闭；`read_attachments=true` 只预览前两页／幻灯片，每份最多 5000 字。
- 公告默认从课程或学期起始日至今查询；起始时间不可用时明确回退过去 180 天，可手动指定更早范围。
- 续读时把 `next_cursor` 的全部字段传回 `read_material`，并保留文件 ID。游标校验文件版本，避免拼接不同版本内容。
- 外部视频和教学工具只返回链接；本项目不登录外部平台、不提交作业、不发送消息。
- 图片、扫描页、公式和手写批注可能无法提取。当前没有 OCR、课件全文搜索或自动变更提醒。

## 配置与缓存

普通安装将私有配置放在用户配置目录，缓存放在该配置目录下。通过 `CANVAS_CONFIG` 可以指定独立配置文件；`CANVAS_BASE_URL`、`CANVAS_TOKEN_FILE`、`CANVAS_TOKEN`、`CANVAS_TIMEZONE` 支持环境覆盖。已有个人源码部署的私有 `canvas.toml` 仍兼容。

MCP 配置按当前 Python 环境生成，不包含作者本机路径或令牌。启动方式是 `python -m canvas_bridge serve`，不依赖调用时的工作目录。见 [配置模板](mcp-config.example.json) 和 [Canvas 配置模板](canvas.example.toml)。

令牌只发送到配置的 Canvas 源站。跨域课件下载不携带 Canvas Authorization；签名 URL 不写入文件元数据。缓存会核对远端更新时间及本地 SHA256。课程内容始终作为不可信资料处理。

## 开发和打包

```bash
python3 -m venv .venv
# 激活后：
python -m pip install -r requirements.lock
python -m pip install .
python -m unittest discover -s tests -v
python scripts/package_release.py
```

测试使用虚构数据，不需要真实 Canvas 账号。发布脚本只收集明确允许的源码、文档和测试，检查可疑凭据与本机私有路径，生成源码 ZIP、哈希清单和可选发布载荷。个人凭据、课程缓存和本地验证记录不会进入公开包。项目还提供跨平台 GitHub Actions 检查。

发布版本和改动见 [CHANGELOG.md](CHANGELOG.md)。许可证：[MIT](LICENSE)。本项目与 Instructure 无隶属关系。
