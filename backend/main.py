from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import uvicorn
import os

from database import init_db
from agent_service import router as agent_router
from discussion_service import router as discussion_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动和关闭时的生命周期管理"""
    # 启动时初始化数据库
    await init_db()
    print("✅ 数据库初始化完成")
    yield
    # 关闭时的清理工作（如果需要）
    print("👋 应用关闭")


app = FastAPI(
    title="Opinion Room API",
    description="AI多智能体讨论平台",
    version="1.0.0",
    lifespan=lifespan
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该配置具体的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(agent_router)
app.include_router(discussion_router)

# 静态文件服务
frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")
    
    @app.get("/")
    async def read_root():
        """返回前端页面"""
        index_file = os.path.join(frontend_path, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"message": "Welcome to Opinion Room API"}
else:
    @app.get("/")
    async def read_root():
        return {"message": "Welcome to Opinion Room API"}


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "healthy"}


if __name__ == "__main__":
    print("🚀 启动 Opinion Room 服务器...")
    print("📍 访问地址: http://localhost:8000")
    print("📚 API文档: http://localhost:8000/docs")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

