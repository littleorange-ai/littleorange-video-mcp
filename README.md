# littleorange-video-mcp

LittleOrange 视频模型 API 的 MCP Server，基于 https://video-ai.apifox.cn 文档生成。

## 覆盖范围

当前内置 36 个文档接口工具、11 个“创建并等待”自动轮询工具，并提供 `video_ai_raw_request` 透传工具：

- 示例：创建视频任务、查询任务
- Sora2：文生视频、图生视频、查询任务
- Veo3.1：文生视频、图生视频、视频扩展、查询任务
- Vidu Q3：文生视频、图生视频、首尾帧生视频、参考生视频（主体/非主体）、查询生成物
- Dreamina Seedance 2.0：视频生成、查询任务
- Dreamina 素材库：AIGC 素材/素材组 CRUD、真人认证素材/素材组 CRUD、真人认证 H5、认证结果查询、删除资产/资产组

所有工具的 `request_body` schema 来自 Apifox OpenAPI 文档，保留文档内全部参数、必填项、枚举、嵌套对象和数组结构。

## 安装

```bash
cd /root/video-ai-mcp
python -m pip install -e .
```

如果系统没有 pip，先安装 Python 打包工具，例如 Debian/Ubuntu：

```bash
apt update && apt install -y python3-pip
```

## 配置 MCP Client

推荐把 API Key 放到 MCP Client 的环境变量里，不要写进提示词。

Claude Desktop / Cursor / TRAE 等 stdio MCP 配置示例：

```json
{
  "mcpServers": {
    "littleorange-video": {
      "command": "python",
      "args": ["-m", "video_ai_mcp.server"],
      "env": {
        "VIDEO_AI_API_KEY": "sk-你的key",
        "VIDEO_AI_TIMEOUT": "120"
      }
    }
  }
}
```

如果不是 editable install，也可以直接指定工作目录里的 Python 路径或使用：

```json
{
  "mcpServers": {
    "littleorange-video": {
      "command": "python",
      "args": ["/root/littleorange-video-mcp/run_server.py"],
      "env": {
        "VIDEO_AI_API_KEY": "sk-你的key"
      }
    }
  }
}
```

## 工具调用说明

每个封装工具通常包含：

- `api_key`：可选；不传时读取 `VIDEO_AI_API_KEY`
- `model_id` / `id`：路径参数，按接口需要出现
- `Action`：素材库接口查询参数，已从文档 example 设置默认值，也允许覆盖
- `request_body`：完整请求体；字段和约束来自文档

示例：Vidu Q3 文生视频

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
  }
}
```

示例：查询任务

```json
{
  "model_id": "viduq3-turbo",
  "id": "your-task-id"
}
```

示例：素材库创建素材

```json
{
  "request_body": {
    "GroupId": "group-xxx",
    "Name ": "素材名",
    "URL": "https://example.com/image.png",
    "AssetType": "image"
  }
}
```

注意：Apifox 文档中 `Name ` 字段带一个尾随空格，MCP schema 保留了这个字段名以保证与文档完全一致。

## 开发与测试

```bash
python -m pip install -e '.[dev]'
pytest
```

## 文档更新

文档抓取产物保存在 `/root/video-ai-mcp-docs`。如果 Apifox 文档后续新增接口，可重新抓取 `.md` 文档并更新 `video_ai_mcp/api_catalog.json`；在更新封装命名前，`video_ai_raw_request` 可立即覆盖新增/变更接口。
