"""任务中心 API —— 刷课任务与流程配置的查询 / 控制。

- 任务路由: ``/api/v1/tasks``(创建任务用配置**文件名**,不带路径)
- 配置路由: ``/api/v1/configs``(本地配置列表 / 在线配置列表)
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.onlineclass.configs import (
    download_config,
    list_local_configs,
    list_online_configs,
)
from core.onlineclass.task_manager import task_center

# ── 任务路由 ───────────────────────────────────────────────────────────
router = APIRouter(
    prefix="/api/v1/tasks",
    tags=["任务中心"],
)


class TaskCreateRequest(BaseModel):
    """创建刷课任务的请求体(配置以文件名引用,不带路径)"""

    config_name: str
    username: str
    password: str
    headless: bool | None = None  # 覆盖浏览器有头/无头;None 沿用剧本 global.headless
    playback_rate: int = Field(
        default=1,
        ge=1,
        alias="playbackRate",
        description="视频播放倍速(正整数,默认 1 倍速)",
    )


class CaptchaSubmitRequest(BaseModel):
    """提交验证码的请求体"""

    captcha: str


@router.post("", summary="创建并启动刷课任务")
def create_task(payload: TaskCreateRequest) -> dict:
    try:
        task = task_center.create(
            payload.config_name,
            payload.username,
            payload.password,
            headless=payload.headless,
            playback_rate=payload.playback_rate,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return task.to_dict()


@router.get("", summary="列出全部任务")
def list_tasks() -> list[dict]:
    return task_center.list()


@router.get("/{task_id}", summary="查询任务详情")
def get_task(task_id: str) -> dict:
    data = task_center.get_dict(task_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
    return data


@router.post("/{task_id}/start", summary="启动待运行任务")
def start_task(task_id: str) -> dict:
    try:
        task = task_center.start(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return task.to_dict()


@router.post("/{task_id}/stop", summary="请求停止任务")
def stop_task(task_id: str) -> dict:
    try:
        task = task_center.stop(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return task.to_dict()


@router.post("/{task_id}/captcha", summary="提交验证码,继续执行任务")
def submit_captcha(task_id: str, payload: CaptchaSubmitRequest) -> dict:
    try:
        task = task_center.submit_captcha(task_id, payload.captcha)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (RuntimeError, ValueError) as exc:
        # 409: 状态不允许(非等待中/重复提交); 400: 校验失败(空串/超长)
        status_code = 409 if isinstance(exc, RuntimeError) else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return task.to_dict()


@router.delete("/{task_id}", summary="删除已结束任务")
def remove_task(task_id: str) -> dict:
    try:
        removed = task_center.remove(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not removed:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
    return {"ok": True, "task_id": task_id}


# ── 配置路由 ───────────────────────────────────────────────────────────
config_router = APIRouter(
    prefix="/api/v1/configs",
    tags=["流程配置"],
)


@config_router.get("/local", summary="查询本地流程配置列表")
def list_local_configs_api() -> list[dict]:
    """返回 ``data/onlineclass/*.yaml`` 的 ``[{name, created_at}]``。"""
    return list_local_configs()


@config_router.get("/online", summary="查询在线流程配置列表")
def list_online_configs_api() -> list[dict]:
    """从在线配置仓库(AList 直链)拉取 ``[{name, updated_at}]``。"""
    try:
        return list_online_configs()
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


class ConfigDownloadRequest(BaseModel):
    """批量下载在线配置的请求体(配置以文件名引用,不带后缀)"""

    names: list[str] = Field(..., description="要下载的配置名列表")


@config_router.post("/download", summary="批量下载在线配置到本地剧本目录")
def download_configs_api(payload: ConfigDownloadRequest) -> dict:
    """按配置名批量下载,自动保存到 ``data/onlineclass/``(目录不存在会自动创建)。

    返回 ``{downloaded: [{name, path}], failed: [{name, error}]}``;
    单个配置失败不阻塞其余下载,错误信息逐项返回。
    """
    downloaded: list[dict] = []
    failed: list[dict] = []
    for name in payload.names:
        try:
            path = download_config(name)
            downloaded.append({"name": name, "path": str(path)})
        except (ValueError, RuntimeError) as exc:
            failed.append({"name": name, "error": str(exc)})
    return {"downloaded": downloaded, "failed": failed}
