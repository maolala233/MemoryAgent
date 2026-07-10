"""FastAPI 应用入口。"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ..config.settings import apply_env_overrides, settings
from ..routers import agents, chat, documents, mandol, memory, search, stats
from ..routers import settings as settings_router
from ..routers import llm as llm_router
from ..routers import system_admin as system_admin_router
from ..services.agent_service import agent_service
from ..services.background_service import background_service
from ..services.mandol_service import mandol_service
from ..services.memory_service import memory_service
from ..utils.logger import info, setup_logging
from .websocket_manager import ws_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    apply_env_overrides(settings)
    settings.ensure_directories()
    setup_logging(settings.log_level)
    info("启动记忆智能问答平台后端")

    # 初始化 Mandol 记忆引擎
    if settings.mandol_enabled:
        info("正在初始化 Mandol 记忆引擎...")
        if mandol_service.initialize():
            info("Mandol 记忆引擎已启用（懒加载，首次使用时初始化）")
        else:
            info("Mandol 初始化标记失败，继续启动")

    memory_service.ensure_seed_data()
    # 启动时重新索引已有的 vault 文件到 SQLite
    if settings.vault_dir.exists() and any(settings.vault_dir.rglob("*.md")):
        try:
            memory_service.rescan_vault()
        except Exception as exc:
            info(f"初始重扫描已跳过: {exc}")
    agent_service.ensure_loaded()
    background_service.start_default()
    yield
    # 关闭 Mandol
    if mandol_service.is_enabled:
        mandol_service.shutdown()
    background_service.stop()
    info("关闭完成")


def create_app() -> FastAPI:
    app = FastAPI(
        title="记忆智能问答平台",
        description="基于 Mandol 的记忆构建、检索与智能问答平台",
        version="0.2.0",
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
    app.include_router(mandol.router)
    app.include_router(settings_router.router)
    app.include_router(llm_router.router)
    app.include_router(system_admin_router.router)

    @app.get("/api/health")
    def health() -> dict:
        return {
            "status": "ok",
            "vault": str(settings.vault_dir),
            "db": str(settings.db_path),
            "active_connections": ws_manager.get_active_connections(),
            "agents": len(agent_service.list_agents()),
            "mandol_enabled": mandol_service.is_enabled,
            "mandol_ready": mandol_service.is_ready,
        }

    @app.get("/api/system")
    def system() -> dict:
        stats = memory_service.get_stats()
        mandol_stats = mandol_service.get_stats()
        return {
            "status": "ok",
            "version": "0.2.0",
            "vault_dir": str(settings.vault_dir),
            "db_path": str(settings.db_path),
            "mandol_enabled": settings.mandol_enabled,
            "mandol_ready": mandol_service.is_ready,
            "llm_model": settings.mandol_llm_model,
            "embedder_model": settings.mandol_embedder_model,
            "reranker_model": settings.mandol_reranker_model,
            "docs_count": stats.get("total_docs", 0),
            "mandol_units": mandol_stats.get("total_units", 0),
        }

    @app.get("/")
    def root() -> dict:
        return {"name": "记忆智能问答平台 API", "docs": "/docs", "health": "/api/health"}

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request, exc):  # type: ignore[no-untyped-def]
        from ..utils.logger import error
        error("未处理的异常", exc=exc)
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
