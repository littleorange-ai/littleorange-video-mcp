# littleorange-video-mcp

LittleOrange 视频模型 API 的 MCP Server，基于 https://video-ai.apifox.cn 文档生成。

## 覆盖范围

当前内置 36 个文档接口工具、11 个“创建并等待”自动轮询工具，并提供 `littleorange_raw_request` 透传工具：

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
        "LITTLEORANGE_TIMEOUT": "120"
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
        "git+https://github.com/littleorange-ai/littleorange-video-mcp.git@0.0.1.post2",
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
        "LITTLEORANGE_TIMEOUT": "120"
      }
    }
  }
}
```

如果不是 editable install，也可以直接指定工作目录里的 Python 路径：

```json
{
  "mcpServers": {
    "littleorange-video": {
      "command": "python",
      "args": ["/path/to/littleorange-video-mcp/run_server.py"],
      "env": {
        "LITTLEORANGE_API_KEY": "sk-你的key",
        "LITTLEORANGE_TIMEOUT": "120"
      }
    }
  }
}
```

## 工具调用说明

每个封装工具通常包含：

- `api_key`：可选；不传时读取 `LITTLEORANGE_API_KEY`
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

## 自动轮询工具

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

这些工具会先创建任务，再自动轮询查询接口，完成后返回 `video_urls` 和完整查询结果。

额外参数：

- `poll_interval_seconds`：轮询间隔秒数，默认 5
- `max_poll_attempts`：最大轮询次数，默认 60

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
