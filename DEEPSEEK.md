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
