import json
import os
import tempfile
import unittest
from unittest import IsolatedAsyncioTestCase, mock

os.environ.setdefault("LITTLEORANGE_CATALOG_AUTO_UPDATE", "0")

from littleorange_video_mcp.autopoll import (
    AUTO_POLL_TOOL_NAMES,
    configured_first_poll_delay_seconds,
    configured_max_poll_attempts,
    configured_poll_interval_seconds,
    extract_task_id,
    extract_video_urls,
    is_terminal_failure,
    is_terminal_success,
    normalize_task_status,
    poll_until_complete,
    query_tool_for_create_tool,
)
from littleorange_video_mcp.catalog import build_tool_schema, load_catalog, operation_by_tool_name
from littleorange_video_mcp.client import build_request
from littleorange_video_mcp.config import (
    LittleOrangeConfigError,
    get_base_url,
    get_first_poll_delay_seconds,
    get_max_poll_attempts,
    get_poll_interval_seconds,
    get_timeout_seconds,
)

try:
    from littleorange_video_mcp.server import list_tools, _create_and_wait
    SERVER_IMPORT_ERROR = None
except ModuleNotFoundError as exc:
    list_tools = None
    _create_and_wait = None
    SERVER_IMPORT_ERROR = exc


class CatalogAndClientTests(unittest.TestCase):
    def test_catalog_has_one_tool_per_documented_operation_and_raw_passthrough(self):
        catalog = load_catalog()
        self.assertEqual(len(catalog.operations), 36)
        names = {op.tool_name for op in catalog.operations}
        self.assertIn("sora2_t2v", names)
        self.assertIn("vidu_ref_subj", names)
        self.assertIn("dreamina_create_video", names)
        self.assertIn("dreamina_aigc_create_asset", names)

    def test_all_tool_names_fit_trae_sixty_char_limit(self):
        catalog = load_catalog()
        extra_names = [
            "littleorange_raw_request",
            *AUTO_POLL_TOOL_NAMES,
            "video_generate_wait",
            "image_to_video_wait",
            "video_extend_wait",
            "video_query",
            "asset_upload",
            "asset_list",
        ]
        names = [op.tool_name for op in catalog.operations] + extra_names
        too_long = [name for name in names if len(name) > 60]
        self.assertEqual(too_long, [])

    def test_tool_schema_exposes_path_query_and_exact_request_body_schema(self):
        catalog = load_catalog()
        op = operation_by_tool_name(catalog, "vidu_t2v")
        schema = build_tool_schema(op)
        self.assertEqual(schema["properties"]["base_url"]["type"], "string")
        self.assertEqual(schema["properties"]["headers"]["type"], "object")
        self.assertEqual(schema["properties"]["query_params"]["type"], "object")
        self.assertEqual(schema["properties"]["model_id"]["type"], "string")
        self.assertEqual(schema["properties"]["request_body"]["required"], ["model", "prompt"])
        body_props = schema["properties"]["request_body"]["properties"]
        for key in ["model", "prompt", "duration", "seed", "aspect_ratio", "resolution", "audio", "payload", "watermark", "wm_position", "wm_url", "meta_data", "callback_url"]:
            self.assertIn(key, body_props)

    def test_material_tool_sets_action_query_parameter_but_allows_override(self):
        catalog = load_catalog()
        op = operation_by_tool_name(catalog, "dreamina_aigc_create_asset")
        schema = build_tool_schema(op)
        self.assertEqual(schema["properties"]["Action"]["default"], "CreateAsset")
        req = build_request(op, {"api_key": "sk-test", "Action": "CreateAsset", "request_body": {"GroupId": "g", "Name ": "n", "URL": "https://x", "AssetType": "image"}})
        self.assertEqual(req.method, "POST")
        self.assertEqual(req.url, "https://vg-api.aig-ai.com/materials")
        self.assertEqual(req.params, {"Action": "CreateAsset"})
        self.assertEqual(req.headers["Authorization"], "Bearer sk-test")

    def test_build_request_substitutes_path_and_preserves_multipart_body(self):
        catalog = load_catalog()
        op = operation_by_tool_name(catalog, "sora2_i2v")
        req = build_request(op, {"api_key": "sk-test", "model_id": "sora2", "request_body": {"model": "sora2", "prompt": "p", "input_reference": "file-or-url"}})
        self.assertEqual(req.url, "https://vg-api.aig-ai.com/v1/sora2")
        self.assertEqual(req.content_type, "multipart/form-data")
        self.assertIsNone(req.json_body)
        self.assertEqual(req.form_data["input_reference"], "file-or-url")

    def test_build_request_allows_base_url_override_argument(self):
        catalog = load_catalog()
        op = operation_by_tool_name(catalog, "vidu_query")
        req = build_request(op, {"api_key": "sk-test", "base_url": "https://example.com/api", "model_id": "viduq3-turbo", "id": "task-1"})
        self.assertEqual(req.url, "https://example.com/api/v1/query/viduq3-turbo/task-1")

    def test_build_request_supports_headers_query_params_and_any_json_body(self):
        catalog = load_catalog()
        op = operation_by_tool_name(catalog, "dreamina_query_video")
        req = build_request(
            op,
            {
                "api_key": "sk-test",
                "base_url": "https://example.com",
                "model_id": "dreamina-seedance-2-0",
                "id": "cgt-1",
                "headers": {"X-Test": "1", "Authorization": "ignore-me"},
                "query_params": {"foo": "bar"},
            },
        )
        self.assertEqual(req.headers["Authorization"], "Bearer sk-test")
        self.assertEqual(req.headers["X-Test"], "1")
        self.assertEqual(req.params["foo"], "bar")

    def test_query_tools_ignore_spurious_null_request_body(self):
        catalog = load_catalog()
        op = operation_by_tool_name(catalog, "dreamina_query_video")
        req = build_request(
            op,
            {
                "api_key": "sk-test",
                "model_id": "dreamina-seedance-2-0",
                "id": "cgt-20260602175224-5vnnd",
                "request_body": None,
            },
        )
        self.assertEqual(req.url, "https://vg-api.aig-ai.com/v1/query/dreamina-seedance-2-0/cgt-20260602175224-5vnnd")
        self.assertIsNone(req.json_body)

    def test_dreamina_schema_accepts_official_examples_without_role_on_text(self):
        catalog = load_catalog()
        op = operation_by_tool_name(catalog, "dreamina_create_video")
        schema = build_tool_schema(op)
        body_schema = schema["properties"]["request_body"]
        self.assertEqual(body_schema["required"], ["model", "content"])
        content_item_schema = body_schema["properties"]["content"]["items"]
        self.assertEqual(content_item_schema["oneOf"][0]["required"], ["type", "text"])
        self.assertNotIn("role", content_item_schema["oneOf"][0]["properties"])

        official_example = {
            "model": "dreamina-seedance-2-0",
            "content": [
                {"type": "text", "text": "写实风格，晴朗的蓝天之下，一大片白色的雏菊花田。"},
                {
                    "type": "image_url",
                    "image_url": {"url": "https://example.com/ref.png"},
                    "role": "reference_image",
                },
            ],
            "ratio": "16:9",
            "duration": 5,
            "watermark": False,
        }
        req = build_request(
            op,
            {"api_key": "sk-test", "model_id": "dreamina-seedance-2-0", "request_body": official_example},
        )
        self.assertEqual(req.json_body, official_example)
        self.assertNotIn("role", req.json_body["content"][0])

    def test_dreamina_request_normalizes_erroneous_text_role(self):
        catalog = load_catalog()
        op = operation_by_tool_name(catalog, "dreamina_create_video")
        payload = {
            "model": "dreamina-seedance-2-0",
            "content": [
                {"type": "text", "text": "提示词", "role": "reference_image"},
                {
                    "type": "image_url",
                    "image_url": {"url": "https://example.com/ref.png"},
                    "role": "first_frame",
                },
            ],
        }
        req = build_request(
            op,
            {"api_key": "sk-test", "model_id": "dreamina-seedance-2-0", "request_body": payload},
        )
        self.assertNotIn("role", req.json_body["content"][0])
        self.assertEqual(req.json_body["content"][1]["role"], "first_frame")

    def test_create_response_task_id_and_query_mapping_for_auto_poll(self):
        self.assertEqual(extract_task_id({"task_id": "vidu-task"}), "vidu-task")
        self.assertEqual(extract_task_id({"id": "dreamina-task"}), "dreamina-task")
        self.assertEqual(extract_task_id({"name": "veo-task"}), "veo-task")
        self.assertEqual(query_tool_for_create_tool("vidu_t2v"), "vidu_query")
        self.assertEqual(query_tool_for_create_tool("veo31_t2v"), "veo31_query")
        self.assertEqual(query_tool_for_create_tool("dreamina_create_video"), "dreamina_query_video")

    def test_query_result_status_and_video_url_extraction(self):
        self.assertTrue(is_terminal_success({"state": "success", "creations": [{"url": "https://x/video.mp4"}]}))
        self.assertTrue(is_terminal_success({"done": True, "response": {"videos": [{"gcsUri": "https://x/veo.mp4"}]}}))
        self.assertTrue(is_terminal_success({"status": "succeeded", "content": {"video_url": "https://x/dreamina.mp4"}}))
        self.assertTrue(is_terminal_failure({"state": "failed"}))
        urls = extract_video_urls({"creations": [{"url": "https://x/video.mp4", "cover_url": "https://x/cover.jpg"}]})
        self.assertEqual(urls, ["https://x/video.mp4"])

    def test_normalize_task_status(self):
        self.assertEqual(normalize_task_status({"state": "success"})["normalized_status"], "success")
        self.assertEqual(normalize_task_status({"status": "failed"})["normalized_status"], "failed")
        self.assertEqual(normalize_task_status({"status": "processing"})["normalized_status"], "pending")
        self.assertEqual(normalize_task_status({})["normalized_status"], "unknown")

    def test_configured_poll_settings_can_come_from_env(self):
        old_interval = os.environ.get("LITTLEORANGE_POLL_INTERVAL_SECONDS")
        old_attempts = os.environ.get("LITTLEORANGE_MAX_POLL_ATTEMPTS")
        old_first_delay = os.environ.get("LITTLEORANGE_FIRST_POLL_DELAY_SECONDS")
        try:
            os.environ["LITTLEORANGE_POLL_INTERVAL_SECONDS"] = "9"
            os.environ["LITTLEORANGE_MAX_POLL_ATTEMPTS"] = "88"
            os.environ["LITTLEORANGE_FIRST_POLL_DELAY_SECONDS"] = "3"
            self.assertEqual(configured_poll_interval_seconds(), 9.0)
            self.assertEqual(configured_max_poll_attempts(), 88)
            self.assertEqual(configured_first_poll_delay_seconds(), 3.0)
        finally:
            if old_interval is None:
                os.environ.pop("LITTLEORANGE_POLL_INTERVAL_SECONDS", None)
            else:
                os.environ["LITTLEORANGE_POLL_INTERVAL_SECONDS"] = old_interval
            if old_attempts is None:
                os.environ.pop("LITTLEORANGE_MAX_POLL_ATTEMPTS", None)
            else:
                os.environ["LITTLEORANGE_MAX_POLL_ATTEMPTS"] = old_attempts
            if old_first_delay is None:
                os.environ.pop("LITTLEORANGE_FIRST_POLL_DELAY_SECONDS", None)
            else:
                os.environ["LITTLEORANGE_FIRST_POLL_DELAY_SECONDS"] = old_first_delay

    def test_auto_refresh_catalog_from_apifox_docs(self):
        import littleorange_video_mcp.catalog as catalog_module

        llms_text = "## API Docs\n- 示例 [新接口](https://video-ai.apifox.cn/999999999e0.md):"
        markdown = """
# 新接口
```yaml
openapi: 3.0.1
paths:
  /v1/new-endpoint/{id}:
    post:
      summary: 新接口
      tags:
        - 自动更新
      parameters:
        - name: id
          in: path
          required: true
          schema:
            type: string
        - name: Authorization
          in: header
          required: true
          schema:
            type: string
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                prompt:
                  type: string
              required:
                - prompt
            example:
              prompt: hello
servers:
  - url: https://vg-api.aig-ai.com
```
"""

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, "api_catalog.json")

            def fake_get(url):
                if url.endswith("llms.txt"):
                    return llms_text
                if url.endswith("999999999e0.md"):
                    return markdown
                raise AssertionError(url)

            with mock.patch.dict(
                os.environ,
                {
                    "LITTLEORANGE_CATALOG_AUTO_UPDATE": "1",
                    "LITTLEORANGE_CATALOG_REFRESH_SECONDS": "0",
                    "LITTLEORANGE_CATALOG_CACHE_FILE": cache_file,
                },
                clear=False,
            ), mock.patch.object(catalog_module, "_http_get_text", side_effect=fake_get):
                refreshed = load_catalog(refresh=True)

            names = {op.tool_name for op in refreshed.operations}
            self.assertIn("api_999999999e0", names)
            new_op = operation_by_tool_name(refreshed, "api_999999999e0")
            self.assertEqual(new_op.path, "/v1/new-endpoint/{id}")
            self.assertEqual(new_op.parameters[0]["name"], "id")
            self.assertTrue(os.path.exists(cache_file))

    def test_config_validation_errors_are_friendly(self):
        with mock.patch.dict(os.environ, {"LITTLEORANGE_MAX_POLL_ATTEMPTS": "abc"}, clear=False):
            with self.assertRaises(LittleOrangeConfigError):
                get_max_poll_attempts()
        with mock.patch.dict(os.environ, {"LITTLEORANGE_MAX_POLL_ATTEMPTS": "0"}, clear=False):
            with self.assertRaises(LittleOrangeConfigError):
                get_max_poll_attempts()
        with mock.patch.dict(os.environ, {"LITTLEORANGE_POLL_INTERVAL_SECONDS": "-1"}, clear=False):
            with self.assertRaises(LittleOrangeConfigError):
                get_poll_interval_seconds()
        with mock.patch.dict(os.environ, {"LITTLEORANGE_TIMEOUT": "abc"}, clear=False):
            with self.assertRaises(LittleOrangeConfigError):
                get_timeout_seconds()
        with self.assertRaises(LittleOrangeConfigError):
            get_base_url("notaurl")
        with self.assertRaises(LittleOrangeConfigError):
            get_first_poll_delay_seconds(-1)


class ServerTests(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        if SERVER_IMPORT_ERROR is not None:
            self.skipTest(f"server tests require optional runtime dependency: {SERVER_IMPORT_ERROR}")

    async def test_list_tools_exposes_wait_highlevel_and_raw_schemas(self):
        tools = await list_tools(None)
        by_name = {tool.name: tool for tool in tools}
        self.assertIn("vidu_t2v", by_name)
        self.assertIn("vidu_t2v_wait", by_name)
        self.assertIn("video_generate_wait", by_name)
        self.assertIn("littleorange_raw_request", by_name)
        self.assertIn("base_url", by_name["vidu_t2v"].inputSchema["properties"])
        self.assertIn("poll_interval_seconds", by_name["vidu_t2v_wait"].inputSchema["properties"])
        self.assertIn("max_poll_attempts", by_name["vidu_t2v_wait"].inputSchema["properties"])
        self.assertIn("first_poll_delay_seconds", by_name["vidu_t2v_wait"].inputSchema["properties"])
        self.assertIn("base_url", by_name["littleorange_raw_request"].inputSchema["properties"])
        self.assertIn("query_params", by_name["littleorange_raw_request"].inputSchema["properties"])
        self.assertIn("headers", by_name["littleorange_raw_request"].inputSchema["properties"])
        self.assertGreaterEqual(len(tools), 36 + len(AUTO_POLL_TOOL_NAMES) + 7)

    async def test_create_and_wait_forwards_base_url_and_uses_query_mapping(self):
        calls = []

        async def fake_call_operation(op, args):
            calls.append((op.tool_name, dict(args)))
            if op.tool_name == "vidu_t2v":
                return {"task_id": "task-1"}
            return {"status": "succeeded", "content": {"video_url": "https://example.com/video.mp4"}}

        with mock.patch("littleorange_video_mcp.server.call_operation", side_effect=fake_call_operation):
            response = await _create_and_wait(
                "vidu_t2v_wait",
                {
                    "base_url": "https://example.com/api",
                    "api_key": "sk-test",
                    "model_id": "vidu-model",
                    "request_body": {"model": "vidu-model", "prompt": "p"},
                    "poll_interval_seconds": 1,
                    "max_poll_attempts": 2,
                    "first_poll_delay_seconds": 0,
                },
            )
        self.assertEqual(calls[0][0], "vidu_t2v")
        self.assertEqual(calls[0][1]["base_url"], "https://example.com/api")
        self.assertEqual(calls[1][0], "vidu_query")
        self.assertEqual(calls[1][1]["base_url"], "https://example.com/api")
        payload = json.loads(response[0].text)
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["video_urls"], ["https://example.com/video.mp4"])

    async def test_create_and_wait_cannot_poll_without_task_id(self):
        async def fake_call_operation(op, args):
            return {"ok": True}

        with mock.patch("littleorange_video_mcp.server.call_operation", side_effect=fake_call_operation):
            response = await _create_and_wait("vidu_t2v_wait", {"request_body": {"model": "m", "prompt": "p"}, "first_poll_delay_seconds": 0})
        payload = json.loads(response[0].text)
        self.assertEqual(payload["status"], "cannot_poll")


class PollTests(IsolatedAsyncioTestCase):
    async def test_poll_until_complete_failed_status_exits_early(self):
        async def query_once():
            return {"status": "failed", "error": "bad"}

        result = await poll_until_complete({"task_id": "t1"}, query_once, max_attempts=5, interval_seconds=1, first_poll_delay_seconds=0)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["last_error"], "bad")

    async def test_poll_until_complete_timeout_returns_last_response(self):
        async def query_once():
            return {"status": "processing"}

        result = await poll_until_complete({"task_id": "t1"}, query_once, max_attempts=2, interval_seconds=0.01, first_poll_delay_seconds=0)
        self.assertEqual(result["status"], "timeout")
        self.assertEqual(result["final_query_response"], {"status": "processing"})

    async def test_poll_until_complete_invalid_runtime_values(self):
        async def query_once():
            return {"status": "processing"}

        result = await poll_until_complete({"task_id": "t1"}, query_once, max_attempts=0, interval_seconds=1, first_poll_delay_seconds=0)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error_type"], "validation_error")

    async def test_debug_log_file_can_be_written(self):
        fd, path = tempfile.mkstemp()
        os.close(fd)
        try:
            with mock.patch.dict(os.environ, {"LITTLEORANGE_DEBUG": "1", "LITTLEORANGE_LOG_FILE": path}, clear=False):
                async def query_once():
                    return {"status": "succeeded", "content": {"video_url": "https://example.com/video.mp4"}}

                await poll_until_complete({"task_id": "t1"}, query_once, max_attempts=1, interval_seconds=1, first_poll_delay_seconds=0)
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.assertIn("poll.attempt", content)
        finally:
            if os.path.exists(path):
                os.remove(path)


if __name__ == "__main__":
    unittest.main()
