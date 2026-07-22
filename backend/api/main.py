"""FastAPI 应用入口。"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# 进程启动时把项目根 .env 加载到 os.environ,
# 这样 Mandol / Milvus / 其它通过 os.getenv() 读配置的子模块
# (例如 OpenAICompatibleEmbeddingProvider 用 token_env 取 API key) 也能拿到值。
# pydantic-settings 只把 .env 装载到 Settings 模型,不会写入 os.environ。
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_PROJECT_ROOT / ".env", override=False)

from ..config.settings import apply_env_overrides, settings  # noqa: E402
from ..routers import agents, chat, documents, mandol, memory, search, stats
from ..routers import settings as settings_router
from ..routers import llm as llm_router
from ..routers import system_admin as system_admin_router
from ..services.agent_service import agent_service
from ..services.background_service import background_service
from ..services.config_loader import apply_external_stores_config, apply_model_store_config
from ..services.mandol_service import mandol_service
from ..services.memory_service import memory_service
from ..utils.logger import info, setup_logging, warn
from .websocket_manager import ws_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    apply_env_overrides(settings)
    # 启动时优先加载前端保存的外部存储配置（Milvus / Neo4j）
    # 使其覆盖环境变量默认值，作为下次启动的默认连接
    apply_external_stores_config(settings)
    # 启动时优先加载前端保存的本地模型配置（embedder / reranker 离线拉起）
    apply_model_store_config(settings)
    settings.ensure_directories()
    setup_logging(settings.log_level)
    info("启动记忆智能问答平台后端")
    info(
        f"外部存储默认连接: Milvus={settings.mandol_milvus_uri}, "
        f"Neo4j={settings.mandol_neo4j_uri}"
    )
    info(
        f"本地模型: embedder={settings.mandol_embedder_local_path or settings.mandol_embedder_model} "
        f"(offline={settings.mandol_embedder_offline_only}), "
        f"reranker={settings.mandol_reranker_local_path or settings.mandol_reranker_model} "
        f"(offline={settings.mandol_reranker_offline_only})"
    )

    # 初始化 Mandol 记忆引擎（启动时预热，避免首请求 SSE 卡 5s+）
    # 原因：Mandol 初始化会同步加载 SentenceTransformer + CrossEncoder 模型
    # 以及 1000+ 图谱/单元 JSON；如放到首次 /api/chat/stream 请求中执行，
    # 会阻塞事件循环导致首条 SSE 事件延迟 > 5s，
    # Next.js 代理层默认 5s 超时返回 HTTP 500。
    if settings.mandol_enabled:
        info("正在初始化 Mandol 记忆引擎...")
        # 旧接口：仅标记 _enabled，不做实际工作（懒加载）
        mandol_service.initialize()
        # 新接口：启动期就执行 _do_initialize()，把模型/快照加载完
        try:
            ok = mandol_service.warmup()
            if ok:
                info("Mandol 记忆引擎预热完成（启动期加载，无需懒加载）")
            else:
                info("Mandol 预热失败/未启用，将回退为懒加载")
        except Exception as exc:
            warn(f"Mandol 预热异常（将回退为懒加载）: {exc}")

    # memory_service.ensure_seed_data()  # 临时禁用种子数据，用于干净测试
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
