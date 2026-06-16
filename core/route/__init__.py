from fastapi import FastAPI
from .score import router as score_router


def register_routers(app: FastAPI):
    """注册所有路由"""
    app.include_router(score_router)
