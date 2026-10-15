# Canvas Agent Bridge

让你的 AI 助手帮你查看 Canvas 课程、作业、公告和课件。

**支持 Codex 和 DeepSeek Harness。只读取资料，不会替你提交作业。**

## 最简单的安装方法

打开你平时使用的 AI 助手，复制下面对应的一句话发给它，然后按提示操作。你不需要自己改配置文件。

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

## 安装时，你需要提供什么？

只需要准备两样东西：

1. **学校的 Canvas 网址**：就是平时打开 Canvas 时，浏览器地址栏里的学校网址。
2. **你自己的授权文件**：相当于让工具读取你账号资料的“钥匙”，应通过学校批准的方式获得。只告诉助手文件保存在电脑哪里，不要把文件里的密钥发到聊天里。

**没有授权文件也能先安装。** 安装好了不等于账号已经连接；拿到授权文件后，让助手帮你继续设置即可。目前还不支持点击按钮登录 Canvas。

不知道授权文件从哪里来？请询问学校 IT 或 Canvas 管理员，安装工具本身不能代替账号授权。

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
