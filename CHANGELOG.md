# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
