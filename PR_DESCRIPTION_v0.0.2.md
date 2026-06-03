## Summary
- release LittleOrange Video MCP v0.0.2 as a single external-facing upgrade
- add full configurability for base URL and polling behavior
- improve polling stability, diagnostics, and agent ergonomics
- expand docs for TRAE/uvx onboarding and troubleshooting

## What changed

### Config and runtime
- add centralized `config.py`
- add env-driven and per-call config for:
  - `base_url`
  - `poll_interval_seconds`
  - `max_poll_attempts`
  - `first_poll_delay_seconds`
- add friendly validation for invalid env/config values

### Polling
- add first-poll delay support
- add normalized polling status handling
- return richer polling metadata:
  - `elapsed_seconds`
  - `last_state`
  - `last_status`
  - `last_error`
  - `normalized_status`
- improve query argument propagation from create tools to query tools

### Tooling and agent UX
- improve tool descriptions and schemas
- add high-level tools:
  - `video_generate_wait`
  - `image_to_video_wait`
  - `video_extend_wait`
  - `video_query`
  - `asset_upload`
  - `asset_list`
- preserve TRAE compatibility by keeping tool names within the known limit

### raw_request
- add `headers`
- add `query_params`
- allow arbitrary JSON request bodies

### Errors and diagnostics
- switch to structured JSON error payloads where possible
- include safe HTTP error context without leaking authorization headers
- add optional debug logging via env vars

### Docs and release prep
- update README with:
  - TRAE example config
  - polling presets
  - FAQ
  - debug/logging notes
- bump version to `0.0.2`

## Test plan
- `python3 -m unittest discover -s tests -v`
- Result: passing in current environment, with 3 server-level tests skipped because optional `mcp` runtime dependency is not installed in this container

## Notes
- this PR intentionally bundles the full first public release surface into one version as requested
- release notes draft: `RELEASE_NOTES_v0.0.2.md`
