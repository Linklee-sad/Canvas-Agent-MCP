# DeepSeek Harness 安装：一步一步来

**推荐：直接把 [首页的安装指令](README.md#最简单的安装方法) 发给安装助手，让它操作。** 下面是想自己动手时的步骤。

这里需要的是 **DeepSeek Harness**，不是普通 DeepSeek 网页聊天。如果还没安装，让助手先安装 [DeepSeek 官方 Harness](https://github.com/deepseek-ai/deepseek-harness)。

## 第一步：下载工具

1. 打开 [项目页面](https://github.com/Linklee-sad/Canvas-Agent-MCP)。
2. 点击绿色 **Code** 按钮，再点 **Download ZIP**。
3. 解压文件，在解压后的文件夹里打开终端。

电脑需要 Python 3.11 或更新版本。不会打开终端或不确定 Python 版本，告诉安装助手，让它替你处理。

## 第二步：运行安装向导

复制对应命令，按回车：

**Mac / Linux：**

```bash
python3 setup_canvas.py
```

**Windows：**

```powershell
py -3 setup_canvas.py
```

向导会问你用哪个助手，输入 **2** 选择 DeepSeek Harness。

向导会自动安装工具，并在项目文件夹里创建 **`canvas-account.local.json`**。

用文本编辑器打开它，只填两项：

- **`base_url`**：学校 Canvas 的 `https://` 网址。
- **`api_key`**：你自己的 Canvas key，不是 DeepSeek 的 key。

保留双引号和逗号，保存文件，告诉安装助手“已填好，请检查连接”。`timezone` 默认香港/北京时间，通常不用改。

没有 key 可以先安装，之后再填。授权应通过学校批准的方式获得。不要把 key 发到聊天里，也不要上传这个文件；它已被排除在 Git 提交和发布包之外。

已有旧设置时，向导会继续使用。要改用这个 JSON 文件，让助手帮你切换即可。

## 第三步：启动

以后使用时，在同一个项目文件夹里运行下面这一行即可，无需再填写连接文件路径：

**Mac / Linux：**

```bash
python3 start_deepseek.py
```

**Windows：**

```powershell
py -3 start_deepseek.py
```

启动后新建聊天，发送：

```text
列出我的 Canvas 课程。
```

**看到自己的课程列表，就表示连接成功。** 只看到安装成功、页面打开或功能检查通过，还不代表账号已经连上。

## 遇到这些提示怎么办？

| 看到的提示 | 下一步 |
| --- | --- |
| 找不到 Python / 版本太旧 | 让安装助手安装 Python 3.11 或更新版本。 |
| 没找到 DeepSeek Harness 命令 | 让安装助手安装官方 DeepSeek Harness，再重新启动。 |
| 还没完成安装 / 没找到连接设置 | 重新运行第二步的安装向导，选择 2。 |
| 工具已装好，还没连接学校账号 | 填写本地 JSON 的学校网址和 key，保存后让助手检查。 |
| 暂时连不上学校 | 让助手检查学校网址、网络和授权是否过期。 |

安装向导会保留你已有的 Harness 设置。修改账号、使用其他启动方式或排查问题时，让安装助手参考 [AGENTS.md](AGENTS.md) 和 [技术参考](ADVANCED.md)。
