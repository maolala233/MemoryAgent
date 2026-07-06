"""FastAPI application entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ..config.settings import apply_env_overrides, settings
from ..routers import agents, chat, documents, memory, search, stats
from ..services.agent_service import agent_service
from ..services.background_service import background_service
from ..services.memory_service import memory_service
from ..utils.logger import info, setup_logging
from .websocket_manager import ws_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    apply_env_overrides(settings)
    settings.ensure_directories()
    setup_logging(settings.log_level)
    info("Starting Codex Memory backend")
    memory_service.ensure_seed_data()
    # Re-index any existing vault files into SQLite on boot
    if settings.vault_dir.exists() and any(settings.vault_dir.rglob("*.md")):
        try:
            memory_service.rescan_vault()
        except Exception as exc:
            info(f"Initial rescan skipped: {exc}")
    agent_service.ensure_loaded()
    background_service.start_default()
    yield
    background_service.stop()
    info("Shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Codex Memory",
        description="Long-term memory platform for LLM agents (FastAPI backend).",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(search.router)
    app.include_router(memory.router)
    app.include_router(chat.router)
    app.include_router(agents.router)
    app.include_router(stats.router)
    app.include_router(documents.router)

    @app.get("/api/health")
    def health() -> dict:
        return {
            "status": "ok",
            "vault": str(settings.vault_dir),
            "db": str(settings.db_path),
            "active_connections": ws_manager.get_active_connections(),
            "agents": len(agent_service.list_agents()),
        }

    @app.get("/api/system")
    def system() -> dict:
        from ..services.llm_adapter import LLMFactory, get_embedding_provider
        from ..services.config_loader import get_models_config
        from ..database import db
        cfg = get_models_config()
        stats = memory_service.get_stats()
        return {
            "status": "ok",
            "version": "0.1.0",
            "vault_dir": str(settings.vault_dir),
            "db_path": str(settings.db_path),
            "llm_provider": cfg.get("default_provider", settings.default_llm_provider),
            "embedding_provider": settings.embedding_provider,
            "embedding_dim": settings.embedding_dim,
            "providers": list(cfg.get("providers", {}).keys()),
            "agents_count": len(agent_service.list_agents()),
            "docs_count": stats.get("total_docs", 0),
        }

    @app.get("/")
    def root() -> dict:
        return {"name": "Codex Memory API", "docs": "/docs", "health": "/api/health"}

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request, exc):  # type: ignore[no-untyped-def]
        from ..utils.logger import error
        error("Unhandled exception", exc=exc)
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc), "type": exc.__class__.__name__},
        )

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.api.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level=settings.log_level.lower(),
    )
