# littleorange-video-mcp

LittleOrange 视频模型 API 的 MCP Server，基于 https://video-ai.apifox.cn 文档生成。

## 覆盖范围

当前版本内置：
- 36 个文档接口工具
- 11 个“创建并等待”自动轮询工具
- 6 个更高层、面向 Agent/意图的工具
- 1 个 `littleorange_raw_request` 透传工具

覆盖：
- 示例：创建视频任务、查询任务
- Sora2：文生视频、图生视频、查询任务
- Veo3.1：文生视频、图生视频、视频扩展、查询任务
- Vidu Q3：文生视频、图生视频、首尾帧生视频、参考生视频（主体/非主体）、查询生成物
- Dreamina Seedance 2.0：视频生成、查询任务
- Dreamina 素材库：AIGC 素材/素材组 CRUD、真人认证素材/素材组 CRUD、真人认证 H5、认证结果查询、删除资产/资产组

所有工具的 `request_body` schema 主要来自 Apifox OpenAPI 文档，保留文档内全部参数、枚举、嵌套对象和数组结构。少数文档 schema 与官方示例/真实接口行为不一致时，MCP 会做兼容修正；例如 Dreamina-Seedance 2.0 文本 content 不应携带 `role`，媒体 content 才使用 `role`。

## 推荐使用：uvx

发布到 PyPI 后，MCP Client 可直接用 `uvx` 拉起服务，不需要本地源码路径：

```json
{
  "mcpServers": {
    "littleorange-video": {
      "command": "uvx",
      "args": ["littleorange-video-mcp"],
      "env": {
        "LITTLEORANGE_API_KEY": "sk-你的key",
        "LITTLEORANGE_TIMEOUT": "120",
        "LITTLEORANGE_BASE_URL": "https://vg-api.aig-ai.com",
        "LITTLEORANGE_POLL_INTERVAL_SECONDS": "5",
        "LITTLEORANGE_MAX_POLL_ATTEMPTS": "60",
        "LITTLEORANGE_FIRST_POLL_DELAY_SECONDS": "2",
        "LITTLEORANGE_DEBUG": "0"
      }
    }
  }
}
```

如果要使用 GitHub 或本地源码版本，也可以指定 `--from`：

```json
{
  "mcpServers": {
    "littleorange-video": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/littleorange-ai/littleorange-video-mcp.git@0.0.2",
        "littleorange-video-mcp"
      ],
      "env": {
        "LITTLEORANGE_API_KEY": "sk-你的key",
        "LITTLEORANGE_TIMEOUT": "120",
        "LITTLEORANGE_BASE_URL": "https://vg-api.aig-ai.com",
        "LITTLEORANGE_POLL_INTERVAL_SECONDS": "5",
        "LITTLEORANGE_MAX_POLL_ATTEMPTS": "60",
        "LITTLEORANGE_FIRST_POLL_DELAY_SECONDS": "2",
        "LITTLEORANGE_DEBUG": "0"
      }
    }
  }
}
```

## TRAE 配置示例（Windows 可直接复制）

推荐用 `uvx` 启动：

```json
{
  "mcpServers": {
    "littleorange-video": {
      "command": "uvx",
      "args": ["littleorange-video-mcp"],
      "env": {
        "LITTLEORANGE_API_KEY": "sk-你的key",
        "LITTLEORANGE_BASE_URL": "https://vg-api.aig-ai.com",
        "LITTLEORANGE_TIMEOUT": "120",
        "LITTLEORANGE_POLL_INTERVAL_SECONDS": "5",
        "LITTLEORANGE_MAX_POLL_ATTEMPTS": "60",
        "LITTLEORANGE_FIRST_POLL_DELAY_SECONDS": "2"
      }
    }
  }
}
```

推荐轮询值：
- 快速调试：`interval=3`，`attempts=20`，`first_delay=1`
- 常规视频生成：`interval=5`，`attempts=60`，`first_delay=2`
- 长任务：`interval=10`，`attempts=120`，`first_delay=3`

## 本地开发安装

```bash
cd /path/to/littleorange-video-mcp
python -m pip install -e .
```

如果系统没有 pip，先安装 Python 打包工具，例如 Debian/Ubuntu：

```bash
apt update && apt install -y python3-pip
```

本地 editable install 后也可以这样配置 MCP Client：

```json
{
  "mcpServers": {
    "littleorange-video": {
      "command": "python",
      "args": ["-m", "littleorange_video_mcp.server"],
      "env": {
        "LITTLEORANGE_API_KEY": "sk-你的key",
        "LITTLEORANGE_TIMEOUT": "120",
        "LITTLEORANGE_BASE_URL": "https://vg-api.aig-ai.com",
        "LITTLEORANGE_POLL_INTERVAL_SECONDS": "5",
        "LITTLEORANGE_MAX_POLL_ATTEMPTS": "60",
        "LITTLEORANGE_FIRST_POLL_DELAY_SECONDS": "2"
      }
    }
  }
}
```

## 工具分类

### 1) 底层 API 映射工具
适合熟悉具体模型接口的开发者直接调用。

### 2) `_wait` 自动轮询工具
推荐视频生成优先使用 `_wait` 工具，例如：
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

这些工具会先创建任务，再自动轮询查询接口，完成后返回：
- `video_urls`
- `elapsed_seconds`
- `last_state`
- `last_status`
- `last_error`
- 完整查询结果

### 3) 高层 Agent 友好工具
更适合 TRAE / IDE Agent / 通用 MCP Agent：
- `video_generate_wait`
- `image_to_video_wait`
- `video_extend_wait`
- `video_query`
- `asset_upload`
- `asset_list`

如果你希望 Agent 更容易选对工具，优先让它调用这些高层工具。

## 工具调用说明

每个封装工具通常包含：
- `base_url`：可选；不传时读取 `LITTLEORANGE_BASE_URL`，默认 `https://vg-api.aig-ai.com`
- `api_key`：可选；不传时读取 `LITTLEORANGE_API_KEY`
- `headers`：可选；附加请求头，`Authorization` 会被忽略并由 `api_key` 统一生成
- `query_params`：可选；附加查询参数
- `model_id` / `id`：路径参数，按接口需要出现
- `Action`：素材库接口查询参数，已从文档 example 设置默认值，也允许覆盖
- `request_body`：完整请求体；字段和约束来自文档

### `_wait` 工具额外参数
- `poll_interval_seconds`：轮询间隔秒数；未传时读取 `LITTLEORANGE_POLL_INTERVAL_SECONDS`，默认 5
- `max_poll_attempts`：最大轮询次数；未传时读取 `LITTLEORANGE_MAX_POLL_ATTEMPTS`，默认 60
- `first_poll_delay_seconds`：首次轮询前等待秒数；未传时读取 `LITTLEORANGE_FIRST_POLL_DELAY_SECONDS`，默认 2

也就是说，这几个值都支持两层配置：
- 全局默认：通过环境变量统一配置
- 单次调用覆盖：通过工具参数直接传入

## raw_request 增强能力

`littleorange_raw_request` 现在支持：
- `base_url`
- `query_params`
- `headers`
- 任意 JSON `request_body`（object / array / string / number / boolean / null）

适合：
- 文档新增但 MCP 尚未封装的接口
- 临时调试接口
- 验证 Header / Query 行为

## 错误返回

错误现在尽量以结构化 JSON 返回，例如：

```json
{
  "status": "error",
  "error_type": "http_error",
  "message": "HTTP 400",
  "details": {
    "method": "POST",
    "url": "https://vg-api.aig-ai.com/v1/viduq3-turbo",
    "params": {},
    "status_code": 400,
    "response_excerpt": "..."
  }
}
```

常见 `error_type`：
- `validation_error`
- `request_error`
- `http_error`
- `network_error`
- `polling_timeout`
- `unknown_error`

## Debug / 日志

可选环境变量：
- `LITTLEORANGE_DEBUG=1`
- `LITTLEORANGE_LOG_FILE=/path/to/littleorange-debug.log`

说明：
- 为避免污染 MCP stdio 协议，调试日志默认不直接打印到 stdout
- 开启 `LITTLEORANGE_DEBUG=1` 且设置 `LITTLEORANGE_LOG_FILE` 后，会把调试信息写入文件

调试日志可能包含：
- request method
- 脱敏后的 request url
- query params
- poll attempt
- normalized status
- elapsed seconds

## FAQ

### 1. 为什么生成后没有 video_urls？
可能原因：
- 任务还没完成
- 当前接口返回结构里没有视频地址字段
- 已完成但只有中间状态数据

建议：
- 提高 `max_poll_attempts`
- 增加 `poll_interval_seconds`
- 查看返回里的 `last_status`、`last_state`、`final_query_response`

### 2. 为什么会 timeout？
说明在最大轮询次数内任务还没完成。

建议：
- 调大 `LITTLEORANGE_MAX_POLL_ATTEMPTS`
- 或增大 `LITTLEORANGE_POLL_INTERVAL_SECONDS`
- 长任务场景建议 `attempts=120`

### 3. 为什么提示缺少 API key？
需要：
- 配置 `LITTLEORANGE_API_KEY`
- 或单次调用时传 `api_key`

### 4. 为什么 TRAE 看不到某些工具？
本项目已尽量控制工具名长度不超过 60 字符。若仍异常：
- 重启 MCP Client
- 确认使用的是最新版本
- 检查配置 JSON 是否生效

### 5. 如何切换 API base_url？
可以：
- 全局设置 `LITTLEORANGE_BASE_URL`
- 单次调用传 `base_url`

### 6. raw_request 什么时候用？
适合：
- MCP 尚未封装的新接口
- 临时调试 Header / Query / Body
- 想直接验证底层 API 行为

## 开发与测试

```bash
python -m pip install -e '.[dev]'
pytest
```

也可使用 stdlib unittest：

```bash
python3 -m unittest discover -s tests -v
```

## 文档更新

接口目录由 Apifox OpenAPI 文档生成，生成结果保存在 `littleorange_video_mcp/api_catalog.json`。如 API 文档发生变化，请重新生成 catalog 并更新工具映射；在封装更新前，可临时使用 `littleorange_raw_request` 覆盖新增/变更接口。
