import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.exceptions import HTTPException as StarletteHTTPException

from core.db.init import initDatabase
from core.logger import setup_logging
from core.route import register_routers

app = FastAPI(title="EduAssist API", version="0.1.0")


# ── 全局异常处理 ────────────────────────────────────────────────────────
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """统一 HTTP 异常响应：保持 {"detail": ...} 结构，兼容现有前端"""
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """未捕获异常兜底：记录完整堆栈，对外返回固定文案，不泄露内部细节"""
    logger.opt(exception=exc).error(f"未捕获异常: {request.method} {request.url.path}")
    return JSONResponse(status_code=500, content={"detail": "服务器内部错误"})

# ── Bearer Token 验证 ────────────────────────────────────────────────────
AUTH_TOKEN = os.environ.get("EDUASSIST_TOKEN", "")


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    # /health 和 OPTIONS 预检请求放行
    if request.url.path == "/health" or request.method == "OPTIONS":
        return await call_next(request)

    # dev 模式（无 token）也放行
    if not AUTH_TOKEN:
        return await call_next(request)

    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {AUTH_TOKEN}":
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

    return await call_next(request)


# ── CORS ─────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
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
        app,
        host=app_config["server"]["host"],
        port=app_config["server"]["port"],
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(cfg)
    server.run()
