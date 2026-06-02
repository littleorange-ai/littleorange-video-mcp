# littleorange-video-mcp 运行说明

本文说明当前 LittleOrange 视频模型 MCP 服务是如何运行、如何被 TRAE / Cursor / Claude Desktop 等 MCP Client 调起，以及调用视频 API 的完整链路。

## 1. 当前项目名称

统一后的名称如下：

- 项目 / Python distribution 名称：`littleorange-video-mcp`
- Python import 包名：`littleorange_video_mcp`
- MCP server 名称：`littleorange-video-mcp`
- MCP client 配置里的 server key 建议：`littleorange-video`
- 命令行入口：`littleorange-video-mcp`
- 原始透传工具：`littleorange_raw_request`

旧名称已弃用：

- `video_ai_mcp`
- `video_ai_raw_request`
- `video-ai-mcp`
- `VIDEO_AI_API_KEY`
- `VIDEO_AI_TIMEOUT`

## 2. 运行模式概览

当前 MCP 是一个 Python stdio MCP Server。

也就是说，它不是一个常驻 HTTP 服务，也不需要你手动启动 Web 端口。

运行方式是：

1. TRAE / Cursor / Claude Desktop 等 MCP Client 根据配置启动一个本地子进程。
2. 子进程运行 `littleorange-video-mcp` 或 `python run_server.py`。
3. MCP Client 和该子进程通过 stdin / stdout 通信。
4. MCP Client 启动后先调用 MCP 协议的 `list_tools`。
5. 本服务返回所有可用工具。
6. 用户在客户端里要求生成视频时，模型选择对应 MCP tool。
7. MCP Client 调用该 tool。
8. 本 MCP 服务把 tool 参数转换成 LittleOrange 视频 API 的 HTTP 请求。
9. 本 MCP 服务请求 `https://vg-api.aig-ai.com`。
10. API 返回结果后，MCP 服务把 JSON 结果返回给 MCP Client。
11. 对于 `_wait` 工具，MCP 服务会自动创建任务并轮询，直到返回最终视频 URL 或超时。

链路示意：

```text
用户
  ↓
TRAE / Cursor / Claude Desktop
  ↓ MCP stdio
littleorange-video-mcp 本地子进程
  ↓ HTTPS
LittleOrange 视频 API: https://vg-api.aig-ai.com
  ↓
返回任务结果 / 视频 URL
```

## 3. 服务入口

项目里有两个主要入口。

### 3.1 安装后命令入口

安装项目后可以直接运行：

```bash
littleorange-video-mcp
```

该入口定义在 `pyproject.toml`：

```toml
[project.scripts]
littleorange-video-mcp = "littleorange_video_mcp.server:main"
```

也就是说，执行 `littleorange-video-mcp` 实际会调用：

```python
littleorange_video_mcp.server:main
```

### 3.2 直接脚本入口

也可以直接运行项目根目录下的：

```bash
python run_server.py
```

`run_server.py` 会导入：

```python
from littleorange_video_mcp.server import main
```

然后启动 MCP stdio server。

## 4. 推荐 TRAE 配置

如果你把 zip 解压到：

```text
<你的解压目录>\littleorange-video-mcp
```

推荐使用 `uvx` 启动。

```json
{
  "mcpServers": {
    "littleorange-video": {
      "command": "uvx",
      "args": [
        "--from",
        "C:\\Users\\Admin\\Desktop\\littleorange-video-mcp",
        "littleorange-video-mcp"
      ],
      "env": {
        "LITTLEORANGE_API_KEY": "sk-你的key",
        "LITTLEORANGE_TIMEOUT": "120"
      }
    }
  }
}
```

这种方式的含义是：

- `uvx`：用 uv 临时安装 / 运行 Python 包。
- `--from <你的解压目录>\littleorange-video-mcp`：从本地目录加载这个包。
- `littleorange-video-mcp`：运行这个包暴露出来的命令行入口。
- `LITTLEORANGE_API_KEY`：传给 MCP 子进程的 API Key。
- `LITTLEORANGE_TIMEOUT`：调用 LittleOrange HTTP API 的超时时间，单位秒。

## 5. 备用 TRAE 配置：直接运行 Python 脚本

如果你的 Windows 环境不方便使用 `uvx`，也可以直接运行 `run_server.py`。

```json
{
  "mcpServers": {
    "littleorange-video": {
      "command": "python",
      "args": [
        "C:\\Users\\Admin\\Desktop\\littleorange-video-mcp\\run_server.py"
      ],
      "env": {
        "LITTLEORANGE_API_KEY": "sk-你的key",
        "LITTLEORANGE_TIMEOUT": "120"
      }
    }
  }
}
```

注意：这种方式要求当前 Python 环境已安装依赖：

```bash
pip install -e <你的解压目录>\littleorange-video-mcp
```

或者至少安装：

```bash
pip install mcp httpx jsonschema
```

## 6. 环境变量

当前服务只使用新的 LittleOrange 命名环境变量。

### 6.1 API Key

```text
LITTLEORANGE_API_KEY
```

作用：LittleOrange 视频 API Key。

如果 tool 调用参数里传了 `api_key`，则优先使用参数里的 `api_key`。
如果没传 `api_key`，服务会读取 `LITTLEORANGE_API_KEY`。

### 6.2 HTTP 超时

```text
LITTLEORANGE_TIMEOUT
```

默认值：`120`

作用：每次调用 LittleOrange HTTP API 的超时时间，单位秒。

## 7. MCP 服务内部结构

核心文件如下：

```text
littleorange-video-mcp/
  pyproject.toml
  run_server.py
  README.md
  MCP运行说明.md
  littleorange_video_mcp/
    __init__.py
    server.py
    catalog.py
    client.py
    autopoll.py
    api_catalog.json
  tests/
    test_catalog_and_client.py
```

### 7.1 server.py

职责：MCP 协议层。

主要做：

- 创建 MCP Server：`Server("littleorange-video-mcp")`
- 注册 `list_tools`
- 注册 `call_tool`
- 暴露 36 个 API 文档工具
- 暴露 11 个自动轮询 `_wait` 工具
- 暴露 `littleorange_raw_request` 原始透传工具
- 通过 stdio 和 MCP Client 通信

### 7.2 catalog.py

职责：工具目录和 JSON Schema 生成。

主要做：

- 从 `littleorange_video_mcp/api_catalog.json` 读取 Apifox 提取出来的接口目录
- 每个 API operation 映射成一个 MCP tool
- 生成 MCP tool 的 input schema
- 保留 Apifox 文档里的 request_body 参数、必填项、枚举、嵌套结构
- 保留特殊字段名，例如带尾随空格的 `Name `

### 7.3 client.py

职责：把 MCP tool 参数转换成 HTTP 请求。

主要做：

- 校验 tool 参数是否符合 schema
- 替换 path 参数，例如 `{model_id}`、`{id}`
- 拼接 query 参数，例如 `Action`
- 读取 `LITTLEORANGE_API_KEY`
- 发送 JSON 或 multipart/form-data 请求
- 请求 LittleOrange API：`https://vg-api.aig-ai.com`
- 返回 JSON 文本

### 7.4 autopoll.py

职责：自动轮询。

主要做：

- 创建任务后提取 task id
- 根据创建工具找到对应查询工具
- 定时轮询查询接口
- 判断成功 / 失败 / 仍在进行中
- 从不同模型返回结构里提取视频 URL

## 8. 工具类型

当前 MCP 服务有三类工具。

### 8.1 文档接口工具

这些工具一一对应 Apifox API 文档里的接口。

例如：

- `sora2_t2v`
- `sora2_i2v`
- `sora2_query`
- `veo31_t2v`
- `veo31_i2v`
- `veo31_extend`
- `veo31_query`
- `vidu_t2v`
- `vidu_i2v`
- `vidu_start_end`
- `vidu_ref`
- `vidu_ref_subj`
- `vidu_query`
- `dreamina_create_video`
- `dreamina_query_video`
- Dreamina 素材库相关工具

这些工具只负责单次 HTTP 调用。

比如创建任务工具通常只返回任务 id，不会一直等到视频完成。

### 8.2 自动轮询工具

这些工具以 `_wait` 结尾。

例如：

- `sora2_t2v_wait`
- `sora2_i2v_wait`
- `veo31_t2v_wait`
- `veo31_i2v_wait`
- `veo31_extend_wait`
- `vidu_t2v_wait`
- `vidu_i2v_wait`
- `vidu_start_end_wait`
- `vidu_ref_subj_wait`
- `vidu_ref_wait`
- `dreamina_create_video_wait`

这些工具会：

1. 调用创建接口。
2. 从返回结果里提取任务 id。
3. 调用对应查询接口轮询。
4. 等待任务完成。
5. 返回最终结果和 `video_urls`。

推荐普通用户优先使用 `_wait` 工具，因为它可以一步返回最终视频链接。

### 8.3 原始透传工具

工具名：

```text
littleorange_raw_request
```

用途：

- Apifox 文档新增接口但 MCP 还没封装时临时调用。
- 某些特殊请求体不适合走固定 schema 时调用。
- Debug API 时调用。

它支持：

- `method`
- `base_url`
- `path`
- `model_id`
- `id`
- `Action`
- `request_body`
- `api_key`

## 9. 自动轮询参数

所有 `_wait` 工具都额外支持两个参数：

### 9.1 poll_interval_seconds

默认：`5`

含义：每隔多少秒查询一次任务状态。

### 9.2 max_poll_attempts

默认：`60`

含义：最多查询多少次。

默认总等待时间大约是：

```text
5 秒 × 60 次 = 300 秒
```

如果视频生成时间较长，可以调大：

```json
{
  "poll_interval_seconds": 5,
  "max_poll_attempts": 120
}
```

## 10. 一次工具调用的完整流程

以 `vidu_t2v_wait` 为例。

用户在 TRAE 中说：

```text
用 Vidu Q3 生成一个 5 秒的视频，画面是夜晚骑摩托的猫。
```

模型选择工具：

```text
vidu_t2v_wait
```

传入参数类似：

```json
{
  "model_id": "viduq3-turbo",
  "request_body": {
    "model": "viduq3-turbo",
    "prompt": "A cinematic shot of a cat riding a motorcycle at night",
    "duration": 5,
    "aspect_ratio": "16:9",
    "resolution": "720p",
    "audio": true
  },
  "poll_interval_seconds": 5,
  "max_poll_attempts": 60
}
```

MCP 服务内部执行：

1. `server.py` 收到 MCP tool call。
2. 判断这是 `_wait` 工具。
3. `autopoll.py` 找到对应创建工具 `vidu_t2v`。
4. `client.py` 请求创建接口。
5. 从创建响应中提取任务 id。
6. `autopoll.py` 找到对应查询工具 `vidu_query`。
7. 每 5 秒调用一次查询接口。
8. 判断任务是否完成。
9. 如果完成，提取视频 URL。
10. 返回给 TRAE。

返回结果通常类似：

```json
{
  "status": "completed",
  "task_id": "xxx",
  "video_urls": [
    "https://example.com/video.mp4"
  ],
  "result": {
    "完整查询响应": "..."
  }
}
```

## 11. 本地手动验证

在项目目录中可以运行：

```bash
python3 -m unittest discover -s tests -v
```

当前验证结果：

```text
Ran 7 tests
OK
```

也可以检查 schema：

```bash
python3 - <<'PY'
from littleorange_video_mcp.catalog import load_catalog, build_tool_schema
import json
catalog = load_catalog()
for op in catalog.operations:
    json.dumps(build_tool_schema(op), ensure_ascii=False)
print(len(catalog.operations), 'schemas json ok')
PY
```

当前结果：

```text
36 schemas json ok
```

## 12. 常见问题

### 12.1 为什么没有端口？

因为这是 stdio MCP Server，不是 HTTP Server。

MCP Client 会启动它作为子进程，通过 stdin/stdout 通信。

### 12.2 为什么推荐 uvx？

因为这是 Python MCP 服务。

`uvx` 适合运行 Python package 暴露的命令行入口，不需要把它做成 npm 包。

如果要用 `npx`，需要额外做一层 npm 包装或改写成 Node.js MCP Server。

### 12.3 API Key 放在哪里？

放在 MCP Client 配置的 `env` 里：

```json
"env": {
  "LITTLEORANGE_API_KEY": "sk-你的key"
}
```

不要把 API Key 写在对话里。

### 12.4 TRAE 看不到工具怎么办？

检查：

1. zip 是否已解压。
2. MCP 配置路径是否指向解压后的目录。
3. `command` 是否能在 Windows 命令行运行。
4. 是否安装了 uv。
5. 是否使用了新的包名和命令名：`littleorange-video-mcp`。
6. 是否重启 TRAE。
7. TRAE 日志里是否有 MCP 启动错误。

### 12.5 工具名会不会太长？

当前工具名已做过缩短，最长小于 TRAE 的 60 字符限制。

## 13. 当前交付文件

已导出的 zip：

```text
littleorange-video-mcp.zip
```

解压后目录应为：

```text
<你的解压目录>\littleorange-video-mcp
```

然后按第 4 节配置 TRAE 即可。
