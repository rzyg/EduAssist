"""
节假日数据处理：从 timor.tech 在线获取数据，解析后写入 SQLite 数据库。

不再落盘 JSON 文件，数据直接存入 holiday 表：
  id(索引键) / year(年) / month_day(月日 MM-DD) / holiday(假期) /
  leave_school(离校) / return_school(返校) / schedule_modification(课表修改) / remark(备注)
"""

from datetime import date, timedelta
import json
import re
from typing import Any

import httpx
from loguru import logger

from core.config import DATA_DIR
from core.db.CRUD import (
    batch_create_records,
    create_record,
    get_connection,
    read_records,
    update_record,
)

# timor.tech 节假日 API
BASE_URL = "https://timor.tech/api/holiday/year/"

# 与 core/db/init.py 中 initDatabase() 使用的路径保持一致
DB_PATH = DATA_DIR / "data.db"


def _fetch_holiday_data(year: int) -> dict[str, dict[str, Any]]:
    """
    请求 timor.tech 获取指定年份的节假日数据（不落盘）。

    Returns:
        {"MM-DD": {"holiday": bool, "name": str, "date": "YYYY-MM-DD", ...}}

    Raises:
        RuntimeError: 请求失败（状态码非 200）
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    with httpx.Client(follow_redirects=True, timeout=15) as client:
        response = client.get(f"{BASE_URL}{year}?week=Y", headers=headers)

    if response.status_code != 200:
        raise RuntimeError(f"请求失败，状态码: {response.status_code}")

    data = response.json()
    holiday_dict: dict[str, dict[str, Any]] = data.get("holiday") or {}
    return holiday_dict


def _group_holiday_blocks(holiday_days: set[date]) -> list[tuple[date, date]]:
    """按日期连续性把放假日分组为假期段，返回 [(起始日, 结束日), ...]（按起始日升序）。"""
    blocks: list[tuple[date, date]] = []
    for day in sorted(holiday_days):
        if blocks and day - blocks[-1][1] == timedelta(days=1):
            blocks[-1] = (blocks[-1][0], day)
        else:
            blocks.append((day, day))
    return blocks


def _new_day_record(day: date) -> dict:
    """构造 holiday 表的一行数据（不含 id，布尔以 0/1 存储）。"""
    return {
        "year": day.year,
        "month_day": day.strftime("%m-%d"),
        "holiday": 0,
        "leave_school": 0,
        "return_school": 0,
        "schedule_modification": None,
        "remark": None,
    }


def _compute_day_flags(year: int, holiday_dict: dict[str, dict[str, Any]]) -> list[dict]:
    """
    解析 timor.tech 数据，计算每天记录（含离校/返校标记）。

    规则：假期（包括周末）连续段的开始日前一天标记为离校，段末日标记为返校。
    返回按日期升序的记录列表（字段与 holiday 表一致，不含 id）。
    """
    records: dict[date, dict] = {}
    holiday_days: set[date] = set()

    for key, item in holiday_dict.items():
        date_str = item.get("date", "")
        if date_str:
            day = date.fromisoformat(date_str)
        else:
            # date 字段缺失时由 key（MM-DD）和当前年份拼出
            day = date(year, int(key[:2]), int(key[3:5]))
        is_holiday = bool(item.get("holiday", False))

        record = records.setdefault(day, _new_day_record(day))
        record["holiday"] = 1 if is_holiday else 0
        if is_holiday:
            holiday_days.add(day)

    # 每个连续假期段：开始日的前一天离校，最后一天返校
    for start, end in _group_holiday_blocks(holiday_days):
        leave_day = start - timedelta(days=1)
        records.setdefault(leave_day, _new_day_record(leave_day))["leave_school"] = 1
        records[end]["return_school"] = 1

    return [records[day] for day in sorted(records)]


def _has_synced_year_data(db_path: str, year: int) -> bool:
    """
    判断某年是否已同步过完整节假日数据。

    以“该年是否存在 holiday=true 的记录”为准，避免跨年自动生成的
    离校/返校标记记录（holiday=false）被误判为已同步。
    """
    return bool(read_records(db_path, "holiday", {"year": year, "holiday": 1}))


def _upsert_day_records(db_path: str, records: list[dict]) -> None:
    """
    批量 UPSERT 节假日记录。

    以 (year, month_day) 为键：已存在则合并布尔标记（0/1 取较大值，等价于 OR），
    且不覆盖已有的课表修改/备注（保护人工维护字段）；不存在则插入。
    用于处理跨年边界：同一天可能既是一年的假期、又是另一年假期段的离校日。
    """
    sql = """
        INSERT INTO holiday
            (year, month_day, holiday, leave_school, return_school, schedule_modification, remark)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(year, month_day) DO UPDATE SET
            holiday = excluded.holiday,
            leave_school = MAX(leave_school, excluded.leave_school),
            return_school = MAX(return_school, excluded.return_school)
    """
    values = [
        [
            record["year"],
            record["month_day"],
            record["holiday"],
            record["leave_school"],
            record["return_school"],
            record["schedule_modification"],
            record["remark"],
        ]
        for record in records
    ]
    with get_connection(db_path) as conn:
        conn.executemany(sql, values)


def sync_holiday_data(year: int, db_path: str = DB_PATH) -> int:
    """
    请求 timor.tech 并解析入库（幂等）。

    仅当该年不存在 holiday=true 的记录时才同步，避免覆盖人工维护的课表修改/备注字段；
    跨年自动生成的离校/返校标记记录不会阻止该年首次同步。
    返回写入/合并的记录条数。
    """
    if _has_synced_year_data(db_path, year):
        logger.info(f"{year} 年节假日数据已存在，跳过同步")
        return 0

    holiday_dict = _fetch_holiday_data(year)
    day_records = _compute_day_flags(year, holiday_dict)
    _upsert_day_records(db_path, day_records)
    written = len(day_records)
    logger.info(f"✅ 已写入 {year} 年节假日数据 {written} 条")
    return written


def get_holiday_data(year: int, db_path: str = DB_PATH) -> list[dict]:
    """
    获取指定年份的节假日记录（按 month_day 升序）。

    仅当该年没有完整节假日数据（无 holiday=true 记录）时才自动请求 timor.tech 入库；
    跨年自动生成的离校/返校标记记录不视为该年已同步。
    返回记录中 holiday/leave_school/return_school 为 bool 值。
    """
    if not _has_synced_year_data(db_path, year):
        sync_holiday_data(year, db_path)

    records = read_records(db_path, "holiday", {"year": year})
    records.sort(key=lambda r: r["month_day"])
    # 布尔字段转成 Python bool（数据库以 0/1 存储）
    for record in records:
        record["holiday"] = bool(record["holiday"])
        record["leave_school"] = bool(record["leave_school"])
        record["return_school"] = bool(record["return_school"])
    return records


def _serialize_schedule_modification(value: Any) -> str:
    """把课表修改序列化为 JSON 字符串；str 原样存储，其余结构 json.dumps。"""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _validate_month_day(year: int, month_day: str) -> None:
    """校验月日为合法日期（MM-DD），非法抛 ValueError。"""
    if not re.fullmatch(r"\d{2}-\d{2}", month_day):
        raise ValueError(f"月日格式非法: {month_day!r}，应为 MM-DD 格式")
    try:
        date(year, int(month_day[:2]), int(month_day[3:5]))
    except ValueError:
        raise ValueError(f"非法日期: {year}-{month_day}") from None


def update_holiday_record(
    year: int,
    month_day: str,
    leave_school: bool | None = None,
    return_school: bool | None = None,
    schedule_modification: Any | None = None,
    remark: str | None = None,
    db_path: str = DB_PATH,
) -> dict:
    """
    修改指定日期的假期记录；表中不存在该天则新增一条，已存在则部分更新。

    可修改字段：离校(leave_school)、返校(return_school)、课表修改(schedule_modification)、备注(remark)。
    未传入（None）的字段保持原值/默认值；新增记录时 holiday 固定为 false。
    课表修改接受任意 JSON（dict/list 等），存储为 JSON 字符串；传 {} 表示清空。
    返回更新/新增后的完整记录（布尔字段为 bool）。

    Raises:
        ValueError: month_day 不是合法的 MM-DD 日期
    """
    _validate_month_day(year, month_day)

    records = read_records(db_path, "holiday", {"year": year, "month_day": month_day})
    if records:
        # 部分更新：仅更新本次传入的字段
        record_id = records[0]["id"]
        updates: dict[str, Any] = {}
        if leave_school is not None:
            updates["leave_school"] = 1 if leave_school else 0
        if return_school is not None:
            updates["return_school"] = 1 if return_school else 0
        if schedule_modification is not None:
            updates["schedule_modification"] = _serialize_schedule_modification(
                schedule_modification
            )
        if remark is not None:
            updates["remark"] = remark
        if updates:
            update_record(db_path, "holiday", record_id, updates)
    else:
        # 新增记录：holiday 固定 false，其余取默认值
        new_record = _new_day_record(date(year, int(month_day[:2]), int(month_day[3:5])))
        if leave_school is not None:
            new_record["leave_school"] = 1 if leave_school else 0
        if return_school is not None:
            new_record["return_school"] = 1 if return_school else 0
        if schedule_modification is not None:
            new_record["schedule_modification"] = _serialize_schedule_modification(
                schedule_modification
            )
        if remark is not None:
            new_record["remark"] = remark
        create_record(db_path, "holiday", new_record)

    # 读回完整记录
    updated = read_records(db_path, "holiday", {"year": year, "month_day": month_day})[0]
    updated["holiday"] = bool(updated["holiday"])
    updated["leave_school"] = bool(updated["leave_school"])
    updated["return_school"] = bool(updated["return_school"])
    return updated
