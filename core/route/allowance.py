from typing import Any

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field

from core.allowance.utils.holiday import get_holiday_data, update_holiday_record

router = APIRouter(
    prefix="/api/v1/allowance",
    tags=["津贴相关"],
)


class UpdateHolidayRequest(BaseModel):
    """修改假期表请求体（部分更新：缺省的字段保持不变）"""

    year: int = Field(..., description="年份")
    month_day: str = Field(..., description="月日，MM-DD 格式")
    leave_school: bool | None = Field(None, description="离校")
    return_school: bool | None = Field(None, description="返校")
    schedule_modification: Any | None = Field(None, description="课表修改（任意 JSON，传 {} 表示清空）")
    remark: str | None = Field(None, description="备注")


@router.get("/get_calendar")
async def get_calendar(year: int = Query(..., description="年份")):
    """
    获取节假日数据以生成日历

    返回结构: {"holiday": {"01-01": {数据库字段..., "date": "2026-01-01"}, ...}}
    """
    try:
        results = get_holiday_data(year)
    except Exception as e:
        logger.error(f"获取节假日数据失败: {e}")
        raise HTTPException(status_code=500, detail="获取节假日数据失败")

    holiday = {}
    for record in results:
        item = dict(record)
        item["date"] = f"{item['year']:04d}-{item['month_day']}"
        holiday[item["month_day"]] = item
    return {"holiday": holiday}


@router.put("/update_holiday")
async def update_holiday(payload: UpdateHolidayRequest):
    """
    修改假期表中的一天记录；表中不存在该天则新增一条。

    可修改字段：离校、返校、课表修改、备注（部分更新，缺省字段保持原值）。
    返回修改后的完整记录（含拼接 date）。
    """
    try:
        record = update_holiday_record(
            year=payload.year,
            month_day=payload.month_day,
            leave_school=payload.leave_school,
            return_school=payload.return_school,
            schedule_modification=payload.schedule_modification,
            remark=payload.remark,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"修改节假日数据失败: {e}")
        raise HTTPException(status_code=500, detail="修改节假日数据失败")

    item = dict(record)
    item["date"] = f"{item['year']:04d}-{item['month_day']}"
    return item
