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

然后按提示填写：

- **学校的 Canvas 网址**：平时浏览器里打开学校 Canvas 的网址。
- **已有授权文件的路径**：只填文件在电脑哪里，不要输入里面的密钥。授权文件应通过学校批准的方式获得。

没有授权文件就直接回车，先完成安装。这个工具目前没有“点击登录”功能。首次安装可能需要几分钟；截止时间默认按香港/北京时间显示，其他地区可让助手调整。

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
| 工具已装好，还没连接学校账号 | 拿到授权文件后，再运行一次安装向导。 |
| 暂时连不上学校 | 让助手检查学校网址、网络和授权是否过期。 |

安装向导会保留你已有的 Harness 设置。修改账号、使用其他启动方式或排查问题时，让安装助手参考 [AGENTS.md](AGENTS.md) 和 [技术参考](ADVANCED.md)。
