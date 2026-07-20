from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os
import time


from config import settings
from database import init_db
from routers import auth, documents, chat, images, sessions, mcp


# 将 settings 中的敏感配置同步到环境变量（部分第三方库直接读取环境变量）
if settings.TAVILY_API_KEY:
    os.environ["TAVILY_API_KEY"] = settings.TAVILY_API_KEY


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化数据库
    await init_db()
    # 创建上传目录
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    description="MiniCodeAI 代码智能体 API",
    version="1.0.0",
    lifespan=lifespan
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
app.include_router(documents.router, prefix="/api/documents", tags=["文档管理"])
app.include_router(chat.router, prefix="/api/chat", tags=["对话"])
app.include_router(images.router, prefix="/api/images", tags=["图片识别"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["会话管理"])
app.include_router(mcp.router, prefix="/api/mcp", tags=["MCP 工具"])


@app.get("/api/health")
async def health_check():
    """健康检查接口 - 检查各服务组件状态"""
    services = {}
    status = "healthy"
    
    # 检查 Redis 连接
    redis_status = "healthy"
    redis_error = None
    try:
        import redis
        redis_client = redis.Redis.from_url(settings.REDIS_URL)
        redis_client.ping()
    except Exception as e:
        redis_status = "unhealthy"
        redis_error = str(e)
        status = "degraded"
    services["redis"] = {"status": redis_status, "error": redis_error}
    
    # 检查 Chroma 向量库
    chroma_status = "healthy"
    chroma_error = None
    try:
        from services.vector_store import vector_store
        stats = vector_store.get_collection_stats()
        services["chroma"] = {
            "status": chroma_status,
            "error": chroma_error,
            "total_chunks": stats.get("total_chunks", 0),
            "total_documents": stats.get("total_documents", 0),
        }
    except Exception as e:
        chroma_status = "unhealthy"
        chroma_error = str(e)
        status = "degraded"
        services["chroma"] = {"status": chroma_status, "error": chroma_error}
    
    # 检查 DeepSeek LLM API
    llm_status = "healthy"
    llm_error = None
    try:
        if settings.DEEPSEEK_API_KEY:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    f"{settings.DEEPSEEK_BASE_URL}/chat/completions",
                    headers={"Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}"},
                    json={
                        "model": settings.DEEPSEEK_MODEL,
                        "messages": [{"role": "user", "content": "test"}],
                        "max_tokens": 1
                    }
                )
                if response.status_code != 200:
                    llm_status = "unhealthy"
                    llm_error = f"HTTP {response.status_code}: {response.text[:100]}"
                    status = "degraded"
        else:
            llm_status = "warning"
            llm_error = "DEEPSEEK_API_KEY not configured"
    except Exception as e:
        llm_status = "unhealthy"
        llm_error = str(e)
        status = "degraded"
    services["llm"] = {"status": llm_status, "error": llm_error}
    
    # 检查 VLM API
    vlm_status = "healthy"
    vlm_error = None
    try:
        if settings.QWEN_VL_API_KEY:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{settings.QWEN_VL_BASE_URL}/models",
                    headers={"Authorization": f"Bearer {settings.QWEN_VL_API_KEY}"}
                )
                if response.status_code != 200:
                    vlm_status = "unhealthy"
                    vlm_error = f"HTTP {response.status_code}"
        else:
            vlm_status = "warning"
            vlm_error = "QWEN_VL_API_KEY not configured"
    except Exception as e:
        vlm_status = "unhealthy"
        vlm_error = str(e)
    services["vlm"] = {"status": vlm_status, "error": vlm_error}
    
    # 检查数据库
    db_status = "healthy"
    db_error = None
    try:
        from database import get_db
        async for db in get_db():
            break
    except Exception as e:
        db_status = "unhealthy"
        db_error = str(e)
        status = "degraded"
    services["database"] = {"status": db_status, "error": db_error}
    
    return {
        "status": status,
        "service": settings.APP_NAME,
        "version": "1.0.0",
        "timestamp": time.time(),
        "services": services
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
