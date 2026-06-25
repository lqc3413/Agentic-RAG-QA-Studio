import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# =========================================================================
# 关键：在任何读取配置的导入前准备好路径和环境变量
# =========================================================================
ROOT_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = ROOT_DIR / "project"

if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

load_dotenv(PROJECT_DIR / ".env")

# 清理 no_proxy 环境变量，防止 IPv6 导致 httpx/urllib 抛出 InvalidURL 错误
from utils import sanitize_no_proxy_env
sanitize_no_proxy_env()

# 像 app.py 一样压制 OTel detached 警告，不影响链路跟踪
import logging
class _SuppressOtelDetachWarning(logging.Filter):
    def filter(self, record):
        return "Failed to detach context" not in record.getMessage()

logging.getLogger("opentelemetry.context").addFilter(_SuppressOtelDetachWarning())
# =========================================================================

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.routers import auth, chat, documents, eval_reports, memory
from backend.schemas import HealthResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时：执行异步初始化以支持 AsyncSqliteSaver
    from backend.dependencies import init_rag_system_async
    await init_rag_system_async()
    yield
    # 关闭时：释放连接
    from backend.dependencies import get_rag_system
    try:
        sys_obj = get_rag_system()
        if hasattr(sys_obj, "close_async"):
            await sys_obj.close_async()
    except Exception as e:
        print(f"Error closing RAGSystem connection context: {e}")


app = FastAPI(
    title="Agentic RAG QA Studio API",
    description="Backend API for Document Management and Agentic RAG reasoning.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 跨域配置
origins = [
    "http://127.0.0.1:5173",
    "http://localhost:5173"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由器模块
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(documents.router)
app.include_router(eval_reports.router)
app.include_router(memory.router)



@app.get("/api/health", response_model=HealthResponse, tags=["health"])
async def health_check():
    return HealthResponse(status="ok")
