# Canvas Agent Bridge

让你的 AI 助手帮你查看 Canvas 课程、作业、公告和课件。

**支持 Codex 和 DeepSeek Harness。只读取资料，不会替你提交作业。**

## 最简单的安装方法

打开你平时使用的 AI 助手，复制下面对应的一句话发给它，然后按提示操作。安装由助手处理，你只需在本地文件里填写账号。

**使用 Codex：**

```text
帮我安装这个 Canvas 工具：https://github.com/Linklee-sad/Canvas-Agent-MCP
我用 Codex，不熟悉代码，请按仓库的安装指南帮我完成，每次只告诉我下一步需要做什么。
```

**使用 DeepSeek Harness：**

```text
帮我安装这个 Canvas 工具：https://github.com/Linklee-sad/Canvas-Agent-MCP
我用 DeepSeek Harness，不熟悉代码，请按仓库的安装指南帮我完成，每次只告诉我下一步需要做什么。
```

这里的 DeepSeek Harness 是 DeepSeek 的代理软件。普通 DeepSeek 网页聊天不能直接安装这个本地工具。

## 自己填写 key：只改这一个文件

安装助手或安装向导会在项目文件夹里创建 **`canvas-account.local.json`**。用文本编辑器打开，内容是：

```json
{
  "base_url": "",
  "api_key": "",
  "timezone": "Asia/Hong_Kong"
}
```

只填写前两项的双引号中间：

- **`base_url`**：学校 Canvas 网址，例如 `https://canvas.example.edu`。
- **`api_key`**：你自己的 **Canvas key**，不是 DeepSeek 的 key。
- **`timezone`**：香港/北京时间，通常不用改。

保留双引号、逗号和花括号，保存文件，然后告诉助手“已填好，请检查连接”。不用把 key 发到聊天里，也不用把文件上传。

没有 key 可以先安装。请通过学校批准的方式获取自己的授权；不知道如何获得时，询问学校 IT 或 Canvas 管理员。当前还不支持点击按钮登录 Canvas。

GitHub 上的 `canvas-account.example.json` 只是空白示例。**实际填写的是 `canvas-account.local.json`，这个文件不会随 Git 提交或进入发布包。**

## 怎么知道能用了？

- **Codex**：完成安装后，按提示重新打开或重新连接工具，再新建聊天。
- **DeepSeek Harness**：按安装提示启动，再新建聊天。

发送这句话：

```text
列出我的 Canvas 课程。
```

**看到自己的课程列表，才说明安装和账号连接都成功了。**

接下来可以试试：“未来两周有哪些作业要交？”或“帮我找到这门课的讲义。”

## 想自己安装？

按你使用的助手选择一份逐步操作的说明：

- [Codex：新手安装步骤](DEPLOY.md)
- [DeepSeek Harness：新手安装步骤](DEEPSEEK.md)

遇到问题时，把最后的提示发给你的助手。不要把授权文件内容一起发出去。

详细参数和工具列表放在 [技术参考](ADVANCED.md)；账号授权说明见 [AUTHENTICATION.md](AUTHENTICATION.md)。本项目是个人开发预览，许可证为 [MIT](LICENSE)，与 Instructure、DeepSeek 无隶属关系。
