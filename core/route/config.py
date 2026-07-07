from fastapi import APIRouter, HTTPException
from loguru import logger

from core.config import config, save_config

router = APIRouter(
    prefix="/api/v1/config",
    tags=["配置"],
)


@router.get("")
async def get_config():
    """获取当前配置"""
    return {"config": config}


@router.post("")
async def update_config(body: dict):
    """更新配置"""
    global config

    allowed_keys = {"server", "paths", "dev_mode"}
    for key in body:
        if key not in allowed_keys:
            raise HTTPException(status_code=400, detail=f"不允许的配置项: {key}")

    try:
        for key, value in body.items():
            if isinstance(value, dict) and isinstance(config.get(key), dict):
                config[key].update(value)
            else:
                config[key] = value
        save_config(config)
        logger.info(f"配置已更新: {body}")
        return {"config": config}
    except Exception as e:
        logger.error(f"保存配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"保存配置失败: {str(e)}")
