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
    from core.config import config as app_config

    cfg = uvicorn.Config(
        "core.main:app",
        host=app_config["server"]["host"],
        port=app_config["server"]["port"],
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(cfg)
    server.run()
