from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.mcp.server import create_mcp_http_app

mcp_app = create_mcp_http_app()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with mcp_app.lifespan(app):
        yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Workout Agent",
        description="MCP + CLI planner. Notion is the workout source of truth; ExerciseDB supplies demos.",
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

    app.mount("/mcp", mcp_app)
    return app


app = create_app()
