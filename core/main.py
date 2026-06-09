from fastapi import FastAPI
from loguru import logger
from .db.init import initDatabase
from .logger import setup_logging

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
