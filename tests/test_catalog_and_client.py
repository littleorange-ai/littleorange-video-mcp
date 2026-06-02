import unittest

from littleorange_video_mcp.catalog import load_catalog, build_tool_schema, operation_by_tool_name
from littleorange_video_mcp.client import build_request
from littleorange_video_mcp.autopoll import (
    AUTO_POLL_TOOL_NAMES,
    extract_task_id,
    extract_video_urls,
    is_terminal_success,
    is_terminal_failure,
    query_tool_for_create_tool,
)


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
        names = [op.tool_name for op in catalog.operations] + ["littleorange_raw_request", *AUTO_POLL_TOOL_NAMES]
        too_long = [name for name in names if len(name) > 60]
        self.assertEqual(too_long, [])

    def test_tool_schema_exposes_path_query_and_exact_request_body_schema(self):
        catalog = load_catalog()
        op = operation_by_tool_name(catalog, "vidu_t2v")
        schema = build_tool_schema(op)
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


if __name__ == "__main__":
    unittest.main()
