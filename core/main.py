from fastapi import FastAPI
from loguru import logger
from core.db.init import initDatabase
from core.logger import setup_logging
from core.route import register_routers

app = FastAPI(title="EduAssist API", version="0.1.0")
# 初始化日志
setup_logging()
# 初始化数据库
initDatabase()
# 注册路由
register_routers(app)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/v1/register")
async def register(username: str, phone: str, identity: str):
    logger.info(f"username:{username},phone:{phone},identity:{identity}")
    from pathlib import Path
    from core.db.CRUD import create_record

    databasePath = Path.cwd() / "data" / "data.db"
    try:
        create_record(
            databasePath,
            "user",
            {"username": username, "phone": phone, "identity": identity},
        )
        return {"message": "注册成功"}
    except Exception as e:
        logger.error(e)
        return {"message": "注册失败"}


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
