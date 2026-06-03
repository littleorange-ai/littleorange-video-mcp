# littleorange-video-mcp v0.0.2

## Release Notes

### Highlights

This release packages the first complete external-facing version of the LittleOrange Video MCP usability improvements into one version.

Key themes:
- better configurability
- better polling stability
- better agent/tool usability
- better diagnostics and error reporting
- better TRAE/uvx onboarding

### Added

#### Configuration
- Added `LITTLEORANGE_BASE_URL`
- Added `LITTLEORANGE_POLL_INTERVAL_SECONDS`
- Added `LITTLEORANGE_MAX_POLL_ATTEMPTS`
- Added `LITTLEORANGE_FIRST_POLL_DELAY_SECONDS`
- Added `LITTLEORANGE_DEBUG`
- Added `LITTLEORANGE_LOG_FILE`
- Added per-call overrides for:
  - `base_url`
  - `poll_interval_seconds`
  - `max_poll_attempts`
  - `first_poll_delay_seconds`

#### Polling improvements
- Added first-poll delay support for async task creation flows
- Added normalized polling state handling
- Added richer polling result fields:
  - `elapsed_seconds`
  - `last_state`
  - `last_status`
  - `last_error`
  - `normalized_status`
- Improved query argument propagation from create flow to query flow

#### Agent-friendly tools
Added high-level tools for better IDE/agent ergonomics:
- `video_generate_wait`
- `image_to_video_wait`
- `video_extend_wait`
- `video_query`
- `asset_upload`
- `asset_list`

#### Raw passthrough improvements
- Added `headers`
- Added `query_params`
- Added support for arbitrary JSON `request_body`

#### Diagnostics and errors
- Added structured JSON error payloads
- Improved HTTP error context with safe redaction
- Added config validation with user-friendly messages
- Added optional file-based debug logging

#### Docs
- Expanded README substantially
- Added TRAE-ready configuration example
- Added recommended polling presets
- Added FAQ and debug/logging guidance

### Changed
- Centralized config handling in `littleorange_video_mcp/config.py`
- Improved tool descriptions to steer users/agents toward `_wait` tools when appropriate
- Kept tool names under the TRAE 60-character constraint

### Tests
- Added coverage for config parsing and validation
- Added coverage for schema exposure of new fields
- Added coverage for polling normalization and timeout/failure handling
- Added coverage for raw request enhancements
- Retained tool-name-length guard tests

### Compatibility
- No intended breaking changes for existing basic tool usage
- Existing direct API-style tools remain available
- New features are additive, with improved structured error output

### Version
- Bumped package version from `0.0.1.post2` to `0.0.2`
