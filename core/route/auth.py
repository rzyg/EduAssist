from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from loguru import logger
from pathlib import Path
from core.db.CRUD import create_record

router = APIRouter(
    prefix="/api/v1",
    tags=["认证"],
)


class RegisterRequest(BaseModel):
    """注册请求体（自动校验字段）"""

    username: str = Field(..., min_length=1, max_length=50, description="用户名")
    phone: str = Field(..., pattern=r"^\d{7,15}$", description="手机号（7-15位数字）")
    identity: str = Field(..., min_length=1, max_length=100, description="身份/角色")


@router.post("/register")
async def register(body: RegisterRequest):
    """
    用户注册
    将用户信息写入本地数据库
    """
    database_path = Path(__file__).resolve().parent.parent.parent / "data" / "data.db"
    try:
        create_record(
            database_path,
            "user",
            {
                "username": body.username,
                "phone": body.phone,
                "identity": body.identity,
            },
        )
        logger.info(f"注册成功: {body.username}, {body.phone}")
        return {"message": "注册成功"}
    except Exception as e:
        logger.error(f"注册失败: {e}")
        raise HTTPException(status_code=500, detail="注册失败，请稍后重试")
