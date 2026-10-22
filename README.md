# 项目说明

**概述**：自动化报表合成，利用即时通讯平台，约定的群消息的格式，来批量化生成报表。


有一套完整异常处理机制，异常数据缓存本地，人工在UI界面处理后再重新流入自动生成报表。面对峰值吞吐量，可进入缓冲池，排队缓存本地。细颗粒度的IO
消费锁，保障数据的安全性的同时性能并没有下降很多。


## 项目结构

```text
main.py                 程序入口
common/                 配置、错误码、数据模型
dataCollection/         WebSocket 监听、聊天记录缓存
repair/                 维修通知与待维修任务
report/                 报表生成、合并、异常重生成
utils/                  docx/JSON/图片索引/设施编号等工具
ui/                     主窗口与页面（主页、待维修、异常、配置）
```

## 运行

1. 安装依赖：`pip install -r requirements.txt`
2. 复制 `.env.example` 为 `.env` 并填写配置。程序优先读取根目录 `.env`，其次读取旧版的 `common/.env`。
3. 启动：`python main.py`

## 打包

双击 `build.bat`，或从命令行运行：

```bat
build.bat            :: 生成单文件 dist\main.exe（默认）
build.bat onedir     :: 生成文件夹版 dist\main\main.exe（启动更快）
```

首次运行会自动创建 `.venv`、安装 `requirements-build.txt`（运行时依赖 + PyInstaller），
然后生成图标并调用 `pyinstaller main.spec --clean`。构建完成后会把以下文件复制到输出目录：

- `.env.example`：配置模板
- `编号集合.xlsx`：设施编号表（存在时）
- `.env`：本机配置（存在时；注意其中包含 token，分发前请删除）

打包体积控制：

- Excel 读取使用 `openpyxl`，已移除 pandas/numpy（少约 100MB）。
- `main.spec` 的 `excludes` 排除了 matplotlib、scipy、PyQt、PIL 的 AVIF/FPX/MIC 解码器、
  lxml 的 HTML/objectify 等运行时不用的模块。
- 默认单文件 exe 约 19MB（Python 3.11，实际大小随依赖版本略有浮动）。

> 单文件模式启动时会把内容解压到临时目录，首次启动约 1–3 秒；对启动速度敏感时使用 `onedir`。
> `.env` 与 `编号集合.xlsx` 需要放在 `main.exe` 同目录，程序按 exe 所在目录定位它们。

## 图标

`assets/icon.ico` 由 `tools/make_icon.py` 用 Pillow 绘制：靛蓝→青色的圆角底板、
白色报表纸张和三道数据流波纹。修改脚本顶部的调色板后重新运行即可生成新图标：

```bat
python tools/make_icon.py
```

图标同时用于 exe（`main.spec` 的 `icon`）和窗口标题栏（`ui/app.py` 通过
`utils/resources.py` 读取，打包后从 `sys._MEIPASS` 定位）。

配置说明：

- `LOCAL_IMAGES_DIR` 使用英文逗号分隔多个图片目录；路径建议使用 `/`，避免 Windows 反斜杠被 dotenv 转义。
- `AUTO_MONTH_PATHS=True` 时，路径中的 `YYYY-MM` 会自动替换为当前月份；每月 1 号使用上个月，解决月初照片仍在上月目录的问题。
- `WS_BASE_URL` 与 `TOKEN_WEBSOCKET` 会拼成 WebSocket 地址；旧配置中的 `URL_WEBSOCKET` 不再读取。
- 设施编号表默认读取程序目录下的 `编号集合.xlsx`，也可通过 `FACILITY_FILE` 指定。

图片归档：

- 生成报表时，报表用到的图片会从 QQ 缓存**移动**到 `chat_logs/<群号>/image/`。
- 重复生成或修复异常数据时会优先读取该目录，不再依赖 QQ 缓存中的原文件。
- 同一次生成中，同一张图片被多个群引用时，会为后续群复制一份到各自的 `image/` 目录。

报表分类：

- 维修群的消息，或正文包含“维修”的消息：生成维修报表，**不再生成运维报表**。
- 正文包含“维修”时维修优先级最高：即使同时包含“异常”，也**不生成异常报表**。
- 其余消息：生成运维报表；正文包含“异常”时额外生成异常报表。

合并规则：

- 合并 `运维/<地点>/` 目录下当天的多份报表。
- 合并成功后删除参与合并的原报表，合并结果写回同一目录。
- 合并文件名格式：`YYYY-MM-DD_姓名1 姓名2.docx`，不包含具体时间。


## 1.2.1


版本说明：数据流不稳定，用户自定义的可扩展性差。


- bug修复
  - 本地图片，路径定位不准确
  - 峰值吞吐量，缓冲池被写满




# 7.2号

## 已知的bug

1. 每年，每月路径需要自动更新，月初的照片需要到的上个月找
2. 并发量的解决（问题源暂时不知道）
3. 对于数据控制，经常报Nonetype错误（问题源不知道）

路径问题解决，解决方案：每月由人手动更改配置文件
NoneType报错原因：异步时，多协程对象读写一个文件，导致的I/O异常，解决方案：加入颗粒度为文件单位的互斥锁


## 2.0.2

整个项目重构，将函数式编程重构成面向对象；将数据类封装，提高了代码的可读性，可复用性；工具类封装后，代码结构变得清晰；

待重构模块： 合并功能，待维修界面
