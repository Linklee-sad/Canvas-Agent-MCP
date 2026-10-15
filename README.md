# Canvas Agent Bridge

A local, read-only Canvas LMS MCP server for Codex, DeepSeek Harness, and other MCP clients.

让 Codex 读取 Canvas 课程、作业、公告和课件，汇总跨课程待办，并准备单个作业的参考材料。支持 PDF、PPTX、DOCX 和文本的分段读取。Python 3.11+；macOS、Linux、Windows。

## 把链接交给 Codex

复制下面这段话给 Codex：

> 请帮我安装并配置 https://github.com/Linklee-sad/Canvas-Agent-MCP 。先阅读 AGENTS.md 和 DEPLOY.md，完成本地安装、MCP 注册与离线自检。保留我已有的配置；账号授权缺失时再告诉我需要提供哪些本地配置信息，不要让我把令牌贴在聊天里。

仓库提供可执行的安装脚本和逐步部署说明，Codex 可以按说明操作。克隆后执行：

```bash
git clone https://github.com/Linklee-sad/Canvas-Agent-MCP.git
cd Canvas-Agent-MCP
python3 install.py --register-codex
```

Windows 使用 `py -3 install.py --register-codex`。安装脚本也支持从其他工作目录通过绝对路径调用。它不会覆盖冲突的 MCP 服务或不同的私有配置；可用 `--name canvas-lms` 指定其他服务名。

**安装与 Canvas 授权分开。** 本项目目前是个人开发预览，读取已有的机构批准凭据，尚未实现 OAuth 登录和自动刷新。其他使用者必须配置自己的授权，仓库不附带任何账号。多人正式应用需要机构批准的 OAuth 接入，详见 [AUTHENTICATION.md](AUTHENTICATION.md) 和 [Canvas 官方说明](https://developerdocs.instructure.com/services/canvas/oauth2/file.oauth)。

## DeepSeek Harness 版本

同一仓库提供 DeepSeek Harness 专用入口，支持相同的 14 个工具。把下面这段话交给安装 agent：

> 请把 https://github.com/Linklee-sad/Canvas-Agent-MCP 安装到 DeepSeek Harness。先读 AGENTS.md 和 DEEPSEEK.md，运行 install_deepseek.py，生成独立 Cordis overlay 并验证工具发现。保留已有 Harness 配置；凭据只通过本地私有文件配置，不要贴进聊天。

```bash
python3 install_deepseek.py
```

脚本返回 overlay 路径和 `launch_argv`；用 `dsh --profile web --patch <overlay绝对路径>` 启动。导出不会启动 Harness，也不会修改已有 profile；详细步骤、headless 用法和验证边界见 [DEEPSEEK.md](DEEPSEEK.md)。

## 连接自己的 Canvas

完整操作见 [DEPLOY.md](DEPLOY.md)。凭据应由批准的授权流程预先保存在私有文件中；配置命令只接收文件路径：

```bash
# 在虚拟环境中运行
canvas-bridge configure --base-url https://canvas.example.edu --token-file /absolute/private/path/credentials.token --timezone Asia/Hong_Kong
canvas-bridge register-codex
canvas-bridge doctor
```

支持 UTF-8 令牌文件和只包含一个凭据的 DOCX；也支持本地配置的环境变量。不要将真实凭据提交到 GitHub 或贴进聊天。

安装完成后可用：

```bash
canvas-bridge self-test
canvas-bridge call list_courses
canvas-bridge call get_upcoming_work --args '{"days":14}'
canvas-bridge config
```

`self-test` 验证 MCP 启动和 14 个工具，不访问 Canvas。只有 `doctor` 成功才证明账号连接可用。重新连接客户端以刷新工具列表。

## 可以让 agent 做什么

- “汇总未来两周的待办，列出仍未完成、已提交和状态未知的项目。”
- “把这份作业的正文、rubric、附件和相关公告整理出来，标明缺了什么。”
- “查看课程模块，找到相关讲义，读取前五页并附页码和原文链接。”
- “继续读取刚才被截断的那一页。”

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
