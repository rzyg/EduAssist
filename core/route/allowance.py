from datetime import date

from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from core.allowance.utils.holiday import get_holiday_data

router = APIRouter(
    prefix="/api/v1/allowance",
    tags=["津贴相关"],
)


@router.get("/get_calendar")
async def get_calendar(year: int = Query(..., description="年份")):
    """
    获取节假日数据以生成日历
    """
    # 获取元旦星期几，星期一为1，星期二为2，依此类推
    first_day = date(year, 1, 1).weekday() + 1
    try:
        results = get_holiday_data(year)
    except Exception as e:
        logger.error(f"获取节假日数据失败: {e}")
        raise HTTPException(status_code=500, detail="获取节假日数据失败")
    return {"first_day": first_day, "holidays": results}
