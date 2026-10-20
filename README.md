# SINAS Python SDK

Python SDK for [SINAS](https://github.com/pulsr-ai/SINAS) - AI Agent & Automation Orchestration Platform.

**Runtime API Client** for executing agents, managing state, running webhooks, and tracking executions.

## Installation

```bash
pip install sinas
```

With FastAPI integration:
```bash
pip install sinas[fastapi]
```

## Quick Start

### Authentication

```python
from sinas import SinasClient

# Initialize client with base URL
client = SinasClient(base_url="http://localhost:51245")

# Step 1: Login with email (sends OTP)
login_response = client.auth.login("user@example.com")
session_id = login_response["session_id"]

# Step 2: Verify OTP and get access + refresh tokens
response = client.auth.verify_otp(session_id, "123456")
# Tokens are automatically set on the client
access_token = response["access_token"]
refresh_token = response["refresh_token"]

# Or use an API key directly
client = SinasClient(
    base_url="http://localhost:51245",
    api_key="your-api-key"
)
```

### Environment Variables

Configure the client using environment variables:

```bash
export SINAS_BASE_URL="http://localhost:51245"
export SINAS_API_KEY="your-api-key"
# or
export SINAS_TOKEN="your-jwt-token"
```

```python
from sinas import SinasClient

# Automatically uses environment variables
client = SinasClient()
```

## Core Features

### State Management

Store and retrieve key-value data with namespacing and visibility controls:

```python
# Create/set a state value
state = client.state.set(
    namespace="user_prefs",
    key="theme",
    value={"mode": "dark", "accent": "blue"},
    description="User theme preferences",
    visibility="private"  # private, group, or public
)

# Get a specific state
state = client.state.get(state["id"])
print(state["value"])  # {"mode": "dark", "accent": "blue"}

# List states with filtering
states = client.state.list(
    namespace="user_prefs",
    visibility="private",
    tags="settings",
    search="theme"
)

# Update state
updated = client.state.update(
    state["id"],
    value={"mode": "light", "accent": "green"}
)

# Delete state
client.state.delete(state["id"])
```

### Agent Chats

Create chats with agents and send messages:

```python
# Create a chat with an agent
chat = client.chats.create(
    namespace="customer-support",
    agent_name="cs-agent-v1",
    title="Customer Inquiry",
    input={"customer_id": "12345"}  # Optional input validated by agent
)

# Send a message (blocking)
response = client.chats.send(
    chat_id=chat["id"],
    content="What's the status of my order?"
)
print(response["content"])

# Stream a message (Server-Sent Events)
for chunk in client.chats.stream(
    chat_id=chat["id"],
    content="Tell me about your services"
):
    # Parse SSE data
    import json
    try:
        data = json.loads(chunk)
        if "content" in data:
            print(data["content"], end="", flush=True)
    except:
        pass

# Get chat with all messages
chat_data = client.chats.get(chat["id"])
messages = chat_data["messages"]

# List chats: one page at a time, or every chat (follows X-Next-Cursor)
page = client.chats.list_page(limit=50)          # page.chats, page.next_cursor
more = client.chats.list_page(limit=50, cursor=page.next_cursor)
for chat in client.chats.iter_all():
    print(chat["title"])

# Update chat
client.chats.update(chat["id"], title="Updated Title")

# Delete chat
client.chats.delete(chat["id"])
```

### When the Agent Asks or Waits

An agent with the `askUser` system tool can stop a turn to ask the user a
question; one with `background` can wait for a background run. `invoke()` and
`send()` say how the turn ended in `status` (Sinas 0.5.0+; against older
servers it is always `"completed"`):

| `status` | Meaning |
|---|---|
| `completed` | The final reply is in the response |
| `input_required` | The agent asked; `pending_inputs` lists the questions |
| `in_progress` | Background work outlasted the request; follow `channel_id` |
| `injected` | The chat was busy, so the message went into the turn already there |

Both also return `usage`: the LLM calls (tokens, `cost_usd`) of that request.

```python
result = client.chats.invoke("support", "triage", "Where is my order?",
                             session_key="slack:U1")

while result["status"] == "input_required":
    question = result["pending_inputs"][0]
    answer = input(f"{question['question']} {question['options'] or ''} ")
    # wait=True returns the resumed turn: completed, or the next question
    result = client.chats.answer(result["chat_id"], question["tool_call_id"],
                                 answer, wait=True)

if result["status"] == "in_progress":
    for event in client.chats.follow_channel(result["chat_id"], result["channel_id"]):
        if event.event == "message" and event.data.get("content"):
            print(event.data["content"], end="")
else:
    print(result["reply"])

# Open questions of a chat, e.g. after a restart
client.chats.list_pending_inputs(chat_id)

# Without wait, the answer returns where the resumed turn streams
accepted = client.chats.answer(chat_id, tool_call_id, "123")
if accepted["resumed"]:
    events = client.chats.follow_channel(chat_id, accepted["channel_id"])
```

`stream_events()` streams a turn as parsed events with their names
(`stream()` yields only the data). A question arrives as `input_required`,
followed by `round_suspended` (with the round's `channel_id`), and the stream
ends with `done` `{"status": "suspended"}`:

```python
for event in client.chats.stream_events(chat_id, "Where is my order?"):
    if event.event == "message":
        print(event.data.get("content", ""), end="")
    elif event.event == "input_required":
        print("\nAgent asks:", event.data["question"])
    elif event.event == "approval_required":
        # Approve (optionally for the rest of the chat) or reject a tool call
        decision = client.chats.approve_tool(
            chat_id, event.data["tool_call_id"], True, always_allow=True
        )
        if decision["resume"] == "queued":  # last decision of the round
            resumed = client.chats.follow_channel(chat_id, decision["channel_id"])
    elif event.event == "done":
        print("\n", event.data["status"])  # "completed" or "suspended"
```

### Webhook Execution

Execute webhooks by path:

```python
# Execute a webhook
result = client.webhooks.run(
    path="process-payment",
    method="POST",
    body={"amount": 100, "currency": "USD"},
    headers={"X-Custom-Header": "value"},
    query={"idempotency_key": "abc123"}
)

print(result["execution_id"])  # Track execution
print(result["result"])  # Function output
```

### Executions

Track and manage function executions:

```python
# List recent executions
executions = client.executions.list(
    function_name="payment-processor",
    status="completed",
    limit=10
)

# Get execution details
execution = client.executions.get("execution-id")
print(execution["status"])  # running, completed, failed, awaiting_input
print(execution["output_data"])

# Get execution steps
steps = client.executions.get_steps("execution-id")
for step in steps:
    print(f"{step['step_name']}: {step['status']}")

# Continue a paused execution
result = client.executions.continue_execution(
    "execution-id",
    input={"user_choice": "approve"}
)
```

### Authentication Methods

```python
# Refresh access token
refreshed = client.auth.refresh(refresh_token)
new_access_token = refreshed["access_token"]

# Exchange external OIDC token
response = client.auth.external_auth(external_oidc_token)

# Get current user info
user = client.auth.get_me()
print(user["email"])

# Check user permissions with OR logic (user needs at least one)
check = client.auth.check_permissions(
    ["sinas.functions.read:all", "sinas.functions.create:own"],
    logic="OR"
)
print(check["result"])  # True if user has at least one permission
print(check["checks"])  # Detailed results for each permission

# Check user permissions with AND logic (user needs all)
check = client.auth.check_permissions(
    ["sinas.admin:all", "sinas.functions.write:all"],
    logic="AND"
)
print(check["result"])  # True only if user has all permissions

# Logout (revoke refresh token)
client.auth.logout(refresh_token)
```

## FastAPI Integration

SINAS provides **two powerful approaches** for FastAPI integration:

### Approach 1: Ready-to-Mount Routers

Mount SINAS Runtime API endpoints directly in your FastAPI app with automatic authentication:

```python
from fastapi import FastAPI
from sinas.integrations.routers import create_runtime_router

app = FastAPI()

# Mount ALL runtime endpoints at once
app.include_router(
    create_runtime_router("http://localhost:51245", include_auth=False),
    prefix="/api/runtime"
)

# This automatically creates endpoints like:
# - GET    /api/runtime/states
# - POST   /api/runtime/states
# - GET    /api/runtime/chats
# - POST   /api/runtime/agents/{namespace}/{agent}/chats
# - POST   /api/runtime/webhooks/{path}
# - GET    /api/runtime/executions
```

Or mount individual routers:

```python
from sinas.integrations.routers import (
    create_state_router,
    create_chat_router,
    create_webhook_router,
    create_executions_router
)

app.include_router(create_state_router("http://localhost:51245"), prefix="/runtime/states")
app.include_router(create_chat_router("http://localhost:51245"), prefix="/runtime/chats")
app.include_router(create_webhook_router("http://localhost:51245"), prefix="/runtime/webhooks")
app.include_router(create_executions_router("http://localhost:51245"), prefix="/runtime/executions")
```

### Approach 2: Custom Endpoints with SDK Client

Build custom endpoints with business logic using the authenticated client:

```python
import asyncio
from fastapi import FastAPI, Depends
from sinas import SinasClient
from sinas.integrations.fastapi import SinasAuth

app = FastAPI()
sinas = SinasAuth(base_url="http://localhost:51245")

# Include auto-generated auth endpoints
app.include_router(sinas.router, prefix="/auth")

# Custom endpoint with auto-authentication
@app.get("/my-states")
async def get_my_states(client: SinasClient = Depends(sinas)):
    """List user's states with custom filtering."""
    states = await asyncio.to_thread(client.state.list, limit=10)
    return [{"id": s["id"], "key": s["key"]} for s in states]

# Combine multiple SDK calls
@app.post("/quick-chat")
async def quick_chat(
    agent_namespace: str,
    agent_name: str,
    message: str,
    client: SinasClient = Depends(sinas)
):
    """Create chat and send message in one request."""
    chat = await asyncio.to_thread(client.chats.create, agent_namespace, agent_name)
    response = await asyncio.to_thread(client.chats.send, chat["id"], message)
    return {"chat_id": chat["id"], "response": response}

# Permission-protected endpoint
@app.post("/admin/cleanup")
async def cleanup_states(
    namespace: str,
    client: SinasClient = Depends(sinas.require("sinas.contexts.delete:all"))
):
    """Admin-only: Clean up states (requires permission)."""
    states = await asyncio.to_thread(client.state.list, namespace=namespace)
    for state in states:
        await asyncio.to_thread(client.state.delete, state["id"])
    return {"deleted": len(states)}
```

### Auto-Generated Auth Endpoints

The `sinas.router` automatically provides:

- `POST /auth/login` - Send OTP to email
- `POST /auth/verify-otp` - Verify OTP and get tokens
- `POST /auth/refresh` - Refresh access token using refresh token
- `GET /auth/me` - Get current authenticated user

### Permission-Based Access Control

Use `sinas.require()` to protect endpoints with flexible AND/OR logic:

```python
# Require a single permission
@app.delete("/states/{state_id}")
async def delete_state(
    state_id: str,
    client: SinasClient = Depends(sinas.require("sinas.contexts.delete:own"))
):
    await asyncio.to_thread(client.state.delete, state_id)
    return {"message": "Deleted"}

# Require ANY of multiple permissions (OR logic - default)
@app.post("/moderate-content")
async def moderate_content(
    client: SinasClient = Depends(
        sinas.require("sinas.admin:all", "sinas.moderation.write:all")
    )
):
    # User needs EITHER admin:all OR moderation.write:all
    return {"message": "Content moderated"}

# Require ALL permissions (AND logic)
@app.post("/admin-action")
async def admin_action(
    client: SinasClient = Depends(
        sinas.require("sinas.admin:all", "sinas.functions.write:all", logic="AND")
    )
):
    # User needs BOTH admin:all AND functions.write:all
    return {"message": "Admin action completed"}

# Alternative: Use require_all() for AND logic
@app.post("/super-admin-action")
async def super_admin_action(
    client: SinasClient = Depends(
        sinas.require_all("sinas.admin:all", "sinas.functions.write:all", "sinas.contexts.write:all")
    )
):
    # User needs ALL three permissions
    return {"message": "Super admin action completed"}
```

**Permission Logic:**
- **OR logic (default)**: User needs at least one of the specified permissions
- **AND logic**: User needs all of the specified permissions
- Use `logic="AND"` parameter or `require_all()` method for AND logic

### Complete Example

See [examples/fastapi_app.py](examples/fastapi_app.py) for a complete working example with both approaches.

Run it with:
```bash
uvicorn examples.fastapi_app:app --reload
```

Then visit `http://localhost:8000/docs` for interactive API documentation.

## Context Manager

The client can be used as a context manager for proper resource cleanup:

```python
with SinasClient(base_url="http://localhost:51245") as client:
    states = client.state.list()
    # Client is automatically closed when exiting
```

## Error Handling

```python
from sinas import (
    SinasClient,
    SinasAPIError,
    SinasAuthError,
    SinasNotFoundError,
    SinasValidationError
)

client = SinasClient(base_url="http://localhost:51245")

try:
    state = client.state.get("non-existent-id")
except SinasNotFoundError as e:
    print(f"State not found: {e}")
except SinasAuthError as e:
    print(f"Authentication failed: {e}")
except SinasValidationError as e:
    print(f"Validation error: {e}")
except SinasAPIError as e:
    print(f"API error: {e}")
    print(f"Status code: {e.status_code}")
    print(f"Response: {e.response}")
```

## API Reference

### SinasClient

#### `auth`
- `login(email)` - Send OTP to email
- `verify_otp(session_id, otp_code)` - Verify OTP and get tokens
- `external_auth(token)` - Exchange external OIDC token
- `refresh(refresh_token)` - Refresh access token
- `logout(refresh_token)` - Revoke refresh token
- `get_me()` - Get current user info
- `check_permissions(permissions, logic="AND")` - Check if user has permissions with AND/OR logic

#### `state`
- `set(namespace, key, value, ...)` - Create/update state
- `get(state_id)` - Get state by ID
- `list(namespace?, visibility?, ...)` - List states with filters
- `update(state_id, value?, ...)` - Update state
- `delete(state_id)` - Delete state

#### `chats`
- `create(namespace, agent_name, input?, title?)` - Create chat with agent
- `send(chat_id, content)` - Send message (blocking)
- `stream(chat_id, content)` - Send message (streaming SSE)
- `get(chat_id)` - Get chat with messages
- `list(include_archived?, q?, limit?, cursor?)` - List user's chats; without `limit`/`cursor` the
  server returns at most its CHATS_UNPAGINATED_MAX (10,000 by default) and warns when it cut the list
- `list_page(include_archived?, q?, limit=50, cursor?)` - One page as a `ChatPage` (`chats`, `next_cursor`, `truncated`)
- `iter_all(include_archived?, q?, page_size=200)` - Iterate over every chat, following `X-Next-Cursor`
- `update(chat_id, title?)` - Update chat
- `delete(chat_id)` - Delete chat

#### `webhooks`
- `run(path, method?, body?, headers?, query?)` - Execute webhook

#### `executions`
- `list(function_name?, status?, skip?, limit?)` - List executions
- `get(execution_id)` - Get execution details
- `get_steps(execution_id)` - Get execution steps
- `continue_execution(execution_id, input)` - Continue paused execution

### FastAPI Integration

#### `SinasAuth(base_url, auto_error=True)`
FastAPI dependency for authentication and authorization.

**Methods:**
- `require(*permissions, logic="OR")` - Create dependency requiring permissions with AND/OR logic
- `require_all(*permissions)` - Create dependency requiring ALL permissions (AND logic)

#### Router Functions
- `create_runtime_router(base_url, include_auth=False)` - Complete runtime router
- `create_state_router(base_url, prefix="")` - State endpoints
- `create_chat_router(base_url, prefix="")` - Chat endpoints
- `create_webhook_router(base_url, prefix="")` - Webhook endpoints
- `create_executions_router(base_url, prefix="")` - Execution endpoints

## Development

### Install Development Dependencies

```bash
pip install -e ".[dev]"
```

### Run Examples

```bash
# Basic usage
python examples/basic_usage.py

# FastAPI app
uvicorn examples.fastapi_app:app --reload
```

### Code Formatting

```bash
black sinas
ruff check sinas
```

## License

MIT
