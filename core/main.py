from fastapi import FastAPI
from loguru import logger
from core.db.init import initDatabase
from core.logger import setup_logging

# 初始化日志
setup_logging()
# 初始化数据库
initDatabase()

app = FastAPI()

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/api/v1/register")
async def register(username: str, phone:str,identity:str):
    logger.info(f"username:{username},phone:{phone},identity:{identity}")

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
