from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.db.init import initDatabase
from core.logger import setup_logging
from core.route import register_routers

app = FastAPI(title="EduAssist API", version="0.1.0")

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:1420",
        "tauri://localhost",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化日志
setup_logging()
# 初始化数据库（确保表存在）
initDatabase()
# 注册路由
register_routers(app)


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    config = uvicorn.Config(
        "core.main:app",
        host="127.0.0.1",
        port=8000,
        log_level="warning",  # 只显示 warning 及以上
        access_log=False,  # 完全关闭访问日志
    )
    server = uvicorn.Server(config)
    server.run()
