"""Example FastAPI application using SINAS Runtime API.

Run with:
    uvicorn examples.fastapi_app:app --reload

Then visit:
    http://localhost:8000/docs
"""

import asyncio
from typing import Any, Dict, List

from fastapi import Depends, FastAPI
from sinas import SinasClient
from sinas.integrations.fastapi import SinasAuth
from sinas.integrations.routers import (
    create_runtime_router,
    create_state_router,
    create_chat_router,
)

# Initialize FastAPI app
app = FastAPI(
    title="SINAS Runtime Example API",
    description="Example API using SINAS Runtime API for authentication and data operations",
)

# SINAS API base URL
SINAS_BASE_URL = "http://localhost:51245"

# Initialize SINAS auth
sinas = SinasAuth(base_url=SINAS_BASE_URL)

# Include auto-generated auth endpoints (/auth/login, /auth/verify-otp, /auth/me)
app.include_router(sinas.router, prefix="/auth", tags=["Authentication"])


# ==================== Approach 1: Mount Ready-to-Use Routers ====================
# These routers proxy directly to SINAS Runtime API with automatic authentication

# Option A: Mount all runtime endpoints at once
app.include_router(
    create_runtime_router(SINAS_BASE_URL, include_auth=False),
    prefix="/api/runtime"
)

# Option B: Mount individual routers (commented out to avoid duplication)
# app.include_router(create_state_router(SINAS_BASE_URL), prefix="/api/runtime/states")
# app.include_router(create_chat_router(SINAS_BASE_URL), prefix="/api/runtime/chats")


# ==================== Approach 2: Custom Endpoints Using SDK Client ====================
# Build your own endpoints with custom logic using the SinasClient


@app.get("/")
async def root() -> Dict[str, str]:
    """Public endpoint - no authentication required."""
    return {
        "message": "Welcome to SINAS Runtime Example API",
        "docs": "/docs",
        "runtime_api": "/api/runtime"
    }


@app.get("/my-states")
async def get_my_states(
    client: SinasClient = Depends(sinas)
) -> List[Dict[str, Any]]:
    """Custom endpoint: List user's states with custom filtering.

    This demonstrates using the SDK client to build custom endpoints.
    Requires authentication via Bearer token.
    """
    # You can add custom business logic here
    states = await asyncio.to_thread(client.state.list, limit=10)

    # Transform or filter results
    return [{
        "id": s["id"],
        "namespace": s["namespace"],
        "key": s["key"],
        "created_at": s.get("created_at")
    } for s in states]


@app.post("/quick-chat")
async def quick_chat(
    agent_namespace: str,
    agent_name: str,
    message: str,
    client: SinasClient = Depends(sinas),
) -> Dict[str, Any]:
    """Custom endpoint: Create chat and send message in one request.

    This demonstrates combining multiple SDK calls in a custom endpoint.
    Requires authentication via Bearer token.
    """
    # Create chat
    chat = await asyncio.to_thread(
        client.chats.create,
        namespace=agent_namespace,
        agent_name=agent_name,
        title=f"Quick chat: {message[:30]}..."
    )

    # Send message
    response = await asyncio.to_thread(
        client.chats.send,
        chat_id=chat["id"],
        content=message
    )

    return {
        "chat_id": chat["id"],
        "response": response
    }


@app.get("/health")
async def health_check(client: SinasClient = Depends(sinas)) -> Dict[str, Any]:
    """Health check endpoint that verifies SINAS connectivity.

    Requires authentication via Bearer token.
    """
    try:
        user = await asyncio.to_thread(client.auth.get_me)
        return {
            "status": "healthy",
            "sinas_connected": True,
            "user": user["email"]
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "sinas_connected": False,
            "error": str(e)
        }


# ==================== Permission-Protected Custom Endpoints ====================


@app.post("/admin/cleanup-states")
async def cleanup_old_states(
    namespace: str,
    client: SinasClient = Depends(sinas.require("sinas.contexts.delete:all")),
) -> Dict[str, Any]:
    """Admin-only: Clean up states in a namespace.

    Requires:
    - Authentication via Bearer token
    - Permission: sinas.contexts.delete:all
    """
    states = await asyncio.to_thread(client.state.list, namespace=namespace)

    deleted_count = 0
    for state in states:
        try:
            await asyncio.to_thread(client.state.delete, state["id"])
            deleted_count += 1
        except:
            pass

    return {
        "namespace": namespace,
        "total_found": len(states),
        "deleted": deleted_count
    }


# ==================== Run Instructions ====================

if __name__ == "__main__":
    import uvicorn

    print("Starting SINAS Runtime Example API...")
    print("Visit http://localhost:8000/docs for API documentation")
    print("\nAPI Structure:")
    print("  - /auth/*              : Authentication endpoints (login, verify-otp, etc.)")
    print("  - /api/runtime/*       : Direct proxy to SINAS Runtime API")
    print("  - /my-states           : Custom endpoint using SDK")
    print("  - /quick-chat          : Custom endpoint combining multiple SDK calls")
    print("\nTo authenticate:")
    print("1. POST /auth/login with your email")
    print("2. POST /auth/verify-otp with session_id and OTP code from email")
    print("3. Use the access_token as Bearer token in Authorization header")
    print("\nExample runtime endpoints (auto-mounted):")
    print("  - GET    /api/runtime/states")
    print("  - POST   /api/runtime/states")
    print("  - GET    /api/runtime/chats")
    print("  - POST   /api/runtime/agents/{namespace}/{agent}/chats")
    print("  - POST   /api/runtime/webhooks/{path}")
    print("  - GET    /api/runtime/executions")

    uvicorn.run(app, host="0.0.0.0", port=8000)
