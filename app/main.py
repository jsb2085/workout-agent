from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routers import api_router
from app.config import get_settings
from app.mcp.server import create_mcp_http_app
from app.services import storage

mcp_app = create_mcp_http_app()


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        storage.ensure_bucket()
    except Exception:
        pass
    async with mcp_app.lifespan(app):
        yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Workout Agent API",
        description="User-scoped workout tracker for SwiftUI, plus an MCP server for a planning agent.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=settings.cors_origin_list != ["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def protect_mcp(request: Request, call_next):
        if request.url.path.startswith("/mcp") and request.method != "OPTIONS":
            expected = f"Bearer {get_settings().mcp_agent_token}"
            if request.headers.get("authorization") != expected:
                return JSONResponse({"detail": "Unauthorized"}, status_code=401)
        return await call_next(request)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    app.include_router(api_router)
    app.mount("/mcp", mcp_app)
    return app


app = create_app()
