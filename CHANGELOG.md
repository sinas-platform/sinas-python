# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Chat list pagination.** `client.chats.list()` takes `q`, `limit` and
  `cursor`; with `limit` or `cursor` it returns one page.
  - `client.chats.list_page(limit=50, cursor=None, ...)` returns a `ChatPage`
    (`chats`, `next_cursor`, `truncated`), the cursor taken from the server's
    `X-Next-Cursor` header.
  - `client.chats.iter_all(page_size=200, ...)` iterates over every chat,
    following `X-Next-Cursor`. Against a server from before pagination, the
    first response holds every chat without a cursor, so it yields them all
    and stops.
  - The FastAPI chat router's list endpoint passes `include_archived`, `q`,
    `limit` and `cursor` through and returns `X-Next-Cursor`/`X-Truncated`.

### Changed

- Sinas 0.5.0 caps `GET /chats` without `limit` or `cursor` at
  `CHATS_UNPAGINATED_MAX` (10,000 by default). `client.chats.list()` without
  them still makes that request, and now emits a `UserWarning` when the
  server says it cut the list short (`X-Truncated: true`). Use `iter_all()`
  to get every chat.

## [0.2.0] - 2026-05-15

### Added

- **Bulk submission for functions and agents.** Apps doing N-at-a-time work
  (ingestion runs, dossier scans) can submit one batch and track aggregate
  progress without a per-item worker loop.
  - `client.functions.submit_batch(namespace, name, inputs, ...)` — submit
    N function executions as one batch. Returns
    `{batch_id, execution_ids, total, status}`.
  - `client.agents.submit_batch(namespace, name, inputs, ...)` — submit N
    fresh agent chats as one batch. Each input is
    `{input_variables, message}`. Returns
    `{batch_id, execution_ids, chat_ids, total, status}`.
  - `client.batches.get(batch_id)` — aggregate status + per-status counts.
  - `client.batches.list_executions(batch_id, status=..., limit=..., offset=...)`
    — drill into child executions.
  - `client.batches.cancel(batch_id)` — cancel any queued/pending children.
- **`client.functions.enqueue(...)`** — fire-and-forget async function call
  with optional `trigger_id`, `delay_seconds`, and `callback_url`.
- **Optional `callback_url` on submissions** — Sinas POSTs once per
  execution termination (success/failure/timeout) and optionally once per
  batch terminus via `batch_callback_url`. Callbacks carry a fresh
  short-lived access token for the originating user so downstream apps can
  validate via the standard auth path. Fire-and-forget; polling is the
  resilience fallback.

### Changed

- Per-execution access tokens are now bounded by the function's `timeout`
  plus a 5-minute buffer (capped at 24h), instead of the prior fixed 15-min
  TTL. Most functions now get *shorter* tokens; long-running functions get
  tokens that outlive the execution. No caller-side change required.

See ADR `sinas/backend/docs/adrs/2026-05-14-external-app-bulk-enqueue.md`.

## [0.1.8] - 2026-04-29

### Added

- `ChatsAPI.invoke()` — synchronous agent invocation combining chat creation
  and message sending in one request. Supports `session_key` for conversation
  continuity across calls, plus `reset` to archive an existing session and
  start fresh, and an optional `input` payload for agent input variables.
- `update_existing` parameter on `FilesAPI.upload()`, `upload_bytes()`, and
  `upload_from_path()`. When true, an existing file with the same name is
  overwritten as a new version instead of being auto-renamed.

## [0.1.5] - 2026-02-04

### Fixed

- FastAPI templates router now uses Pydantic models for proper OpenAPI spec generation
  - Added `TemplateRenderRequest` and `TemplateEmailRequest` models
  - Request bodies now correctly documented in OpenAPI/Swagger UI

## [0.1.4] - 2026-02-04

### Added

- Templates API for rendering and emailing templates
  - `client.templates.render()` - Render templates with variables
  - `client.templates.send_email()` - Send emails using templates
- FastAPI templates router with `create_templates_router()`
- Templates endpoints included in `create_runtime_router()`

## [0.1.3] - 2026-01-27

### Added

- FastAPI `/logout` endpoint for revoking refresh tokens

## [0.1.0] - 2025-12-04

### Added

- Initial release of SINAS Python SDK
- Complete API coverage for SINAS AI Agent Platform
- Authentication API with OTP login and API key management
- Chats API with message sending and streaming support
- Assistants API for managing AI assistants
- Functions API for serverless function execution
- LLM Providers API for managing LLM configurations
- MCP (Model Context Protocol) API for tool integration
- Groups API for user group and permission management
- Users API for user management (admin only)
- Webhooks API for webhook endpoint management
- FastAPI integration (`sinas.integrations.fastapi`) for zero-boilerplate auth
  - Auto-generated auth endpoints (`/login`, `/verify-otp`, `/me`)
  - Permission-based route protection with `sinas.require()`
  - Automatic token extraction from Authorization headers
- Configurable base URL via environment variable or constructor
- Support for both JWT tokens and API keys
- Comprehensive error handling with custom exception classes
- Type hints throughout for better IDE support
- Context manager support for automatic resource cleanup
- Streaming support for chat messages via Server-Sent Events

### Documentation

- Complete README with usage examples for all APIs
- FastAPI integration guide with examples
- Jupyter notebook (`test_sdk.ipynb`) for testing all SDK features
- Example FastAPI application (`examples/fastapi_app.py`)
- Example basic usage script (`examples/basic_usage.py`)
- Type stub file (`py.typed`) for PEP 561 compliance

### Developer Experience

- Optional FastAPI extras: `pip install sinas[fastapi]`
- Development extras with testing and linting tools
- Black and Ruff configuration for code formatting
- MyPy configuration for type checking

[0.1.0]: https://github.com/sinas/sinas-sdk/releases/tag/v0.1.0
