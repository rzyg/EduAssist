from fastapi import FastAPI

from .allowance import router as allowance_router
from .auth import router as auth_router
from .config import router as config_router
from .onlineclass import config_router as onlineclass_config_router
from .onlineclass import router as onlineclass_router
from .pdf import router as pdf_router
from .score import router as score_router


def register_routers(app: FastAPI):
    """注册所有路由"""
    app.include_router(auth_router)
    app.include_router(score_router)
    app.include_router(config_router)
    app.include_router(pdf_router)
    app.include_router(allowance_router)
    app.include_router(onlineclass_router)
    app.include_router(onlineclass_config_router)
