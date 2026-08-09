import os
import tempfile
from typing import Any

from fastapi import APIRouter, File, Query, UploadFile
from loguru import logger
from pydantic import BaseModel, Field

from core.allowance.check.load_data import load_teachers
from core.allowance.check.output import output_statistics
from core.allowance.check.statistics import build_holiday_map, compute_attendance
from core.allowance.utils.holiday import get_holiday_data, update_holiday_record
from core.errors import AppError
from core.score.map import loadData

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
    schedule_modification: Any | None = Field(
        None, description="课表修改（任意 JSON，传 {} 表示清空）"
    )
    remark: str | None = Field(None, description="备注")


@router.get("/get_calendar")
async def get_calendar(year: int = Query(..., description="年份")):
    """
    获取节假日数据以生成日历

    返回结构: {"holiday": {"01-01": {数据库字段..., "date": "2026-01-01"}, ...}}
    """
    results = get_holiday_data(year)

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
        raise AppError(status_code=422, detail=str(e))

    item = dict(record)
    item["date"] = f"{item['year']:04d}-{item['month_day']}"
    return item


@router.post("/attendance_statistics")
async def attendance_statistics(
    sheet: UploadFile = File(..., description="坐班签到表 Excel 文件"),
):
    """
    上传坐班签到表，结合假期表统计有效坐班次数并生成统计 Excel。

    签到表结构：第 1 行表头（姓名、部门、各日期列如 '周一 26-03-09'）；
    每位教师 6 行（上午签到/签退、下午签到/签退、晚上签到/签退）。
    输出保存到 output/津贴/坐班签到统计/，返回生成的文件路径列表。
    """
    tmp_path = None
    try:
        tmp_path = save_upload_file(sheet)
        worksheet = loadData(tmp_path)
        teachers = load_teachers(worksheet)

        # 收集涉及的年份并从数据库获取假期数据
        years = {
            workday.date.year for teacher in teachers for workday in teacher.workdays
        }
        records = []
        for year in years:
            records.extend(get_holiday_data(year))
        holiday_map = build_holiday_map(records)
        compute_attendance(teachers, holiday_map)

        # 日期范围：所有打卡日的最小/最大日期
        all_days = [
            workday.date.date() for teacher in teachers for workday in teacher.workdays
        ]
        date_range = (min(all_days), max(all_days))
        paths = output_statistics(teachers, date_range)
        return {"output_path": [str(path) for path in paths]}

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


def save_upload_file(sheet: UploadFile) -> str:
    """从上传的文件创建临时文件，返回临时文件路径。"""
    if not sheet.filename:
        raise AppError(status_code=400, detail="文件名不能为空")

    suffix = os.path.splitext(sheet.filename)[1]
    if not suffix:
        suffix = ".xlsx"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
        content = sheet.file.read()
        tmp_file.write(content)
        tmp_path = tmp_file.name
        logger.info(f"临时文件保存在：{tmp_path}")
    return tmp_path
