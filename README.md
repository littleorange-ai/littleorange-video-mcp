# 


<p align="center">
  <img src="https://internal-api-drive-stream.larkoffice.com/space/api/box/stream/download/authcode/?code=NjNkZmFlMzcyZmI1OTVmMjU3NzM4MWE1NGUxMzM2ZTZfYWQzZWE3NTEyM2I3YjU0OWNmNDQyZGM5NjM2Mzk1NzhfSUQ6NzY0NzAxMTAxNzI5MTI1NTAyNF8xNzgwNDU4NTM3OjE3ODA1NDQ5MzdfVjM" alt="Image" width="200"  />
  <h1 align="center"> LittleOrange Video MCP 官方文档</h1>
</p>



**LittleOrange Video MCP** 是一款基于 **Model Context Protocol \(MCP\)** 开源标准的服务端工具，专为 AI 应用打造，提供统一、标准化的视频生成 API 调用能力。服务基于官方视频生成 API 文档封装，支持主流 AI 视频模型，内置智能轮询、分层工具能力，完美适配各类 AI 客户端与 Agent 场景。

**协议标准**：[Model Context Protocol \(MCP\)](https://modelcontextprotocol.io)

**接口来源**：[视频生成大模型 API 官方文档](https://video-ai.apifox.cn)

---


## ✨ 功能特性

- **多模型全覆盖**：集成 Sora2、Veo3\.1、Vidu Q3、Dreamina Seedance 2\.0 等主流视频生成大模型

- **智能异步轮询**：自动轮询异步任务，无需手动查询，直接返回最终视频链接与完整任务状态

- **三层工具架构**：底层API映射、自动轮询工具、高层Agent工具，适配开发、自动化、AI代理全场景

- **完整素材管理**：支持AIGC素材/素材组、真人认证素材的增删改查，适配商用素材流程

- **通用透传能力**：内置原始请求透传工具，支持任意接口调试与新接口快速适配

- **结构化错误返回**：标准化JSON错误信息，包含错误类型、描述、详情，便于排查问题

- **隔离式调试日志**：日志写入本地文件，不污染MCP标准stdio通信协议

---

## 📌 覆盖范围

当前 **v0\.0\.3** 版本内置全套工具能力，覆盖视频生成、任务查询、素材管理全流程：

- ✅ 36 个基础文档接口工具

- ✅ 11 个「创建并自动等待」轮询工具

- ✅ 6 个高层 Agent 智能工具

- ✅ 1 个通用 API 透传调试工具

### 支持模型与功能明细

| 模型/类别              | 核心支持功能                                                 |
| ---------------------- | ------------------------------------------------------------ |
| 基础示例接口           | 创建视频任务、查询任务状态                                   |
| Sora2                  | 文生视频、图生视频、任务状态查询                             |
| Veo3\.1                | 文生视频、图生视频、视频时长扩展、任务查询                   |
| Vidu Q3                | 文生视频、图生视频、首尾帧生成视频、主体/非主体参考生视频、生成物查询 |
| Dreamina Seedance 2\.0 | AI视频生成、任务状态查询                                     |
| Dreamina 素材库        | 素材/素材组CRUD、真人认证素材管理、认证H5、认证结果查询、资产删除 |

---

## 🚀 快速开始

### 1\. 获取 API Key

使用前需前往 [LittleOrange 平台](https://portal.aig-ai.com) 注册账号，获取专属 `API Key`（密钥需妥善保管，禁止前端暴露）。

### 2\. 安装 uv 包管理器

项目基于 uv 快速部署，未安装则执行以下命令安装：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

更多安装方式参考：[uv 官方仓库](https://github.com/astral-sh/uv)

### 3\. 配置 MCP 客户端

#### 方式一：uvx 直接启动（推荐，无需源码）

PyPI 发布版本，一键拉起服务，适配所有 MCP 客户端：

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
        "LITTLEORANGE_POLL_INTERVAL_SECONDS": "10",
        "LITTLEORANGE_MAX_POLL_ATTEMPTS": "60",
        "LITTLEORANGE_FIRST_POLL_DELAY_SECONDS": "5",
        "LITTLEORANGE_DEBUG": "0"
      }
    }
  }
}
```

#### 方式二：GitHub 源码部署

指定版本源码安装，适合需要最新迭代功能的场景：

```json
{
  "mcpServers": {
    "littleorange-video": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/littleorange-ai/littleorange-video-mcp.git@v0.0.3",
        "littleorange-video-mcp"
      ],
      "env": {
        "LITTLEORANGE_API_KEY": "sk-你的key",
        "LITTLEORANGE_TIMEOUT": "120",
        "LITTLEORANGE_BASE_URL": "https://vg-api.aig-ai.com",
        "LITTLEORANGE_POLL_INTERVAL_SECONDS": "10",
        "LITTLEORANGE_MAX_POLL_ATTEMPTS": "60",
        "LITTLEORANGE_FIRST_POLL_DELAY_SECONDS": "5",
        "LITTLEORANGE_DEBUG": "0"
      }
    }
  }
}
```

#### 客户端专属配置说明

- **TRAE（Windows）**：直接复制上述推荐配置粘贴即可生效

- **Cursor**：`Preferences → Cursor Settings → MCP → Add new global MCP Server`，粘贴配置保存

- **Claude Desktop**：替换官方 MCP 配置文件对应内容

---

## ⚙️ 配置说明

### 环境变量配置（核心）

| 环境变量名                              | 参数描述                       | 默认值                      | 必填 |
| --------------------------------------- | ------------------------------ | --------------------------- | ---- |
| `LITTLEORANGE_API_KEY`                  | 平台接口密钥，身份认证核心参数 | 无                          | ✅ 是 |
| `LITTLEORANGE_BASE_URL`                 | API 接口基础请求地址           | `https://vg-api.aig-ai.com` | ❌ 否 |
| `LITTLEORANGE_TIMEOUT`                  | HTTP 请求超时时间（单位：秒）  | 120                         | ❌ 否 |
| `LITTLEORANGE_POLL_INTERVAL_SECONDS`    | 任务轮询间隔（单位：秒）       | 5                           | ❌ 否 |
| `LITTLEORANGE_MAX_POLL_ATTEMPTS`        | 最大轮询重试次数               | 60                          | ❌ 否 |
| `LITTLEORANGE_FIRST_POLL_DELAY_SECONDS` | 首次轮询延迟时间（单位：秒）   | 5                           | ❌ 否 |
| `LITTLEORANGE_DEBUG`                    | 调试日志开关（1开启 / 0关闭）  | 0                           | ❌ 否 |
| `LITTLEORANGE_LOG_FILE`                 | 调试日志本地存储路径           | 无                          | ❌ 否 |
| `LITTLEORANGE_CATALOG_AUTO_UPDATE`      | 启动时自动刷新 Apifox 接口目录与工具映射（0关闭/1开启） | 1 | ❌ 否 |
| `LITTLEORANGE_CATALOG_REFRESH_SECONDS`  | 接口目录缓存刷新间隔（秒）；设为0表示每次启动都检查官方文档 | 21600 | ❌ 否 |
| `LITTLEORANGE_CATALOG_CACHE_FILE`       | 自动刷新后的接口目录缓存文件路径 | 系统缓存目录 | ❌ 否 |

> **⚠️ 重要说明**：轮询参数支持双层优先级，单次调用传入参数可覆盖全局环境变量配置，灵活适配不同任务场景。
>
> 

### 轮询参数场景推荐

| 使用场景       | 轮询间隔\(秒\) | 最大轮询次数 | 首次延迟\(秒\) |
| -------------- | -------------- | ------------ | -------------- |
| 快速调试       | 3              | 20           | 1              |
| 常规视频生成   | 5              | 60           | 2              |
| 长时长视频任务 | 10             | 120          | 3              |

### 本地开发安装

适合二次开发、本地调试场景：

```bash
# 进入项目目录
cd /path/to/littleorange-video-mcp

# 本地可编辑模式安装
python -m pip install -e .
```

无 pip 环境先安装依赖：

```bash
apt update && apt install -y python3-pip
```

本地开发 MCP 客户端配置：

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
        "LITTLEORANGE_POLL_INTERVAL_SECONDS": "10",
        "LITTLEORANGE_MAX_POLL_ATTEMPTS": "60",
        "LITTLEORANGE_FIRST_POLL_DELAY_SECONDS": "5"
      }
    }
  }
}
```

---

## 🛠️ 工具分类

所有工具分为四大类，从底层原生调用到高层智能封装，适配不同开发与自动化需求。

### 1\. 底层 API 映射工具

完全对齐官方原生接口，适合精细化自定义开发，支持参数灵活覆写。

**通用入参**：`base_url`、`api_key`、`headers`、`query_params`、`request_body`

### 2\. 自动轮询工具（`_wait`）

**推荐优先使用**，自动完成「创建任务 \+ 轮询等待 \+ 结果返回」全流程，直接输出视频链接与任务信息。

**统一返回字段**：`video_urls`、`elapsed_seconds`、`last_state`、`last_status`、`last_error`、完整查询结果

| 模型     | 可用轮询工具                                                 |
| -------- | ------------------------------------------------------------ |
| Sora2    | `sora2_t2v_wait`、`sora2_i2v_wait`                           |
| Veo3\.1  | `veo31_t2v_wait`、`veo31_i2v_wait`、`veo31_extend_wait`      |
| Vidu Q3  | `vidu_t2v_wait`、`vidu_i2v_wait`、`vidu_start_end_wait`、`vidu_ref_subj_wait`、`vidu_ref_wait` |
| Dreamina | `dreamina_create_video_wait`                                 |

### 3\. 高层 Agent 友好工具

极简封装、语义化命名，适配 IDE Agent、MCP 智能代理自动调用，无需手动区分模型。

| 工具名称              | 功能描述                         |
| --------------------- | -------------------------------- |
| `video_generate_wait` | 通用文生视频（智能适配最优模型） |
| `image_to_video_wait` | 通用图生视频                     |
| `video_extend_wait`   | 视频时长扩展                     |
| `video_query`         | 批量查询视频任务状态             |
| `asset_upload`        | 上传自定义素材                   |
| `asset_list`          | 获取个人素材列表                 |

### 4\. 透传工具

通用调试工具 `littleorange_raw_request`，适配所有未封装接口、临时调试场景。

**适用场景**：新接口快速适配、请求头/参数调试、自定义原生请求、官方接口更新兼容

**支持入参**：`base_url`、`query_params`、`headers`、任意格式 `request_body`

---

## 🐛 错误处理与调试

### 标准化错误返回格式

所有异常统一返回结构化 JSON 数据，便于精准排查问题：

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

### 常见错误类型

- `validation_error`：参数校验失败

- `request_error`：请求参数异常

- `http_error`：接口HTTP状态码异常

- `network_error`：网络连接失败

- `polling_timeout`：轮询超时，任务未完成

- `unknown_error`：未知异常

### 调试日志配置

日志独立写入文件，不干扰 MCP 标准通信，开启方式：

```bash
LITTLEORANGE_DEBUG=1
LITTLEORANGE_LOG_FILE=/path/to/littleorange-debug.log
```

**日志包含内容**：请求方式、脱敏URL、查询参数、轮询次数、任务状态、耗时信息

---

## ❓ 常见问题 FAQ

#### Q1：任务完成后没有返回 video\_urls？

可能原因：任务未真正完成、接口返回结构无视频地址、仅返回中间状态数据

解决方案：增大最大轮询次数、调整轮询间隔、查看 `last_status` 与任务最终返回数据

#### Q2：频繁出现轮询超时 timeout？

原因：视频生成任务耗时超出预设轮询上限

解决方案：调大 `LITTLEORANGE_MAX_POLL_ATTEMPTS`、适当增加轮询间隔，长任务建议设置为120次

#### Q3：提示缺少 API Key？

解决方案：配置全局环境变量 `LITTLEORANGE_API_KEY`，或单次调用单独传入密钥参数

#### Q4：TRAE 客户端看不到部分工具？

解决方案：重启 MCP 服务、更新至最新版本、检查配置文件是否生效、确认工具名长度合规

#### Q5：如何切换自定义 API 接口地址？

支持两种方式：全局修改 `LITTLEORANGE_BASE_URL`环境变量、单次调用传入 `base_url` 覆写

#### Q6：什么场景使用 raw\_request 透传工具？

适用于：官方新增未封装接口、接口参数调试、自定义请求头、排查底层接口异常

---

## 💻 开发与测试

### 安装开发依赖

```bash
python -m pip install -e '.[dev]'
```

### 运行单元测试

```bash
# pytest 测试
pytest

# 原生 unittest 测试
python3 -m unittest discover -s tests -v
```

### 文档与接口更新

MCP 服务启动时会自动读取 Apifox 官方 OpenAPI 文档并生成运行时接口目录，缓存文件默认位于系统缓存目录。官方接口更新后，用户重启 MCP 服务即可自动刷新接口目录和工具映射，不需要等待新的 MCP/PyPI 版本发布。

内置兜底目录文件路径：`littleorange_video_mcp/api_catalog.json`。当网络不可用或官方文档临时不可访问时，会自动使用最近一次缓存；如果没有缓存，则使用包内置目录。

可配置项：

- `LITTLEORANGE_CATALOG_AUTO_UPDATE=1`：默认开启自动更新；设为 `0` 可关闭。
- `LITTLEORANGE_CATALOG_REFRESH_SECONDS=21600`：缓存刷新间隔，默认 6 小时；设为 `0` 表示每次启动都检查官方文档。
- `LITTLEORANGE_CATALOG_CACHE_FILE=/path/to/api_catalog.json`：自定义缓存文件路径。

过渡期或新接口尚未形成稳定封装命名时，可使用 `littleorange_raw_request` 临时适配新接口。

---

## 📝 版本历史

| 版本号   | 发布日期     | 核心更新内容                                                 |
| -------- | ------------ | ------------------------------------------------------------ |
| v0\.0\.3 | 2026\-06\-04 | 新增启动时自动刷新 Apifox 官方文档接口目录与工具映射；清理发布包冗余文档 |
| v0\.0\.2 | 2026\-06\-03 | 新增可自定义轮询参数、高层Agent工具、结构化错误返回、文件调试日志；优化TRAE/uvx部署配置 |
| v0\.0\.1 | 2026\-06\-02 | 项目首次正式发布，完成基础视频模型接口封装与MCP服务搭建      |

详细版本迭代记录：[GitHub Releases](https://github.com/littleorange-ai/littleorange-video-mcp/releases)