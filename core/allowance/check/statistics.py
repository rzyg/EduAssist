"""有效坐班统计：时间段规则定义与单次打卡有效性判定"""

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any

from core.allowance.check.modules import Check, Teacher


@dataclass(frozen=True)
class SlotRule:
    """
    一个打卡时段的有效时间区间（均含端点）。

    :param name: 时段名称
    :param start_in: 签到区间起点（含）
    :param end_in: 签到区间终点（含）
    :param start_out: 签退区间起点（含）
    :param end_out: 签退区间终点（含）；None 表示无上限
    """

    name: str
    start_in: time
    end_in: time
    start_out: time
    end_out: time | None


# 正常上午：签到 07:00—08:50，签退 11:00—12:50
MORNING = SlotRule("上午", time(7, 0), time(8, 50), time(11, 0), time(12, 50))

# 正常下午：签到 13:30—15:00，签退 17:00—18:30
AFTERNOON = SlotRule("下午", time(13, 30), time(15, 0), time(17, 0), time(18, 30))

# 离校日下午：签到 13:30—15:00，签退 15:05 及以后（无上限）
LEAVE_AFTERNOON = SlotRule("离校下午", time(13, 30), time(15, 0), time(15, 5), None)

# 晚上：签到 18:35—19:30，签退 21:00 以后（无上限）
EVENING = SlotRule("晚上", time(18, 35), time(19, 30), time(21, 0), None)


def _as_time(value: datetime | time) -> time:
    """datetime 取其 time 部分，time 原样返回。"""
    if isinstance(value, datetime):
        return value.time()
    return value


def is_valid_check(check: Check | None, rule: SlotRule) -> bool:
    """
    签到与签退时间同时满足规定区间，算一次有效打卡。
    签到或签退缺失（None）时返回 False。
    """
    if check is None or check.time_in is None or check.time_out is None:
        return False

    time_in = _as_time(check.time_in)
    time_out = _as_time(check.time_out)

    if not (rule.start_in <= time_in <= rule.end_in):
        return False
    if time_out < rule.start_out:
        return False
    if rule.end_out is not None and time_out > rule.end_out:
        return False
    return True


def build_holiday_map(records: list[dict]) -> dict[date, dict[str, bool]]:
    """
    把假期表记录列表转换为按日期索引的标记字典。

    :param records: get_holiday_data 返回的记录列表（含 year/month_day/holiday/leave_school/return_school）
    :return: {date: {"holiday": bool, "leave_school": bool, "return_school": bool}}
    """
    result: dict[date, dict[str, bool]] = {}
    for record in records:
        month, day = int(record["month_day"][:2]), int(record["month_day"][3:5])
        day_key = date(record["year"], month, day)
        result[day_key] = {
            "holiday": bool(record["holiday"]),
            "leave_school": bool(record["leave_school"]),
            "return_school": bool(record["return_school"]),
        }
    return result


def compute_attendance(
    teachers: list[Teacher], holiday_by_day: dict[date, dict[str, bool]]
) -> None:
    """
    结合假期信息计算每位教师的有效坐班次数（写入 Teacher.count）。

    日期类型与统计口径：
      - 返校日（return_school=true）：仅晚上打卡，数据位于前两行（morning 位），
        按晚上规则（签到 18:35—19:30、签退 ≥21:00）判定，不计上午/下午
      - 离校日（leave_school=true）：上午（正常规则）+ 离校下午（签退 ≥15:05），晚上不统计
      - 假期（holiday=true 且非返校日）：不统计
      - 正常工作日（含无假期标记的普通周末）：上午 + 正常下午 + 晚上
    """
    for teacher in teachers:
        teacher.count = 0
        for workday in teacher.workdays:
            info = holiday_by_day.get(workday.date.date(), {})
            is_holiday = bool(info.get("holiday", False))
            leave_school = bool(info.get("leave_school", False))
            return_school = bool(info.get("return_school", False))

            # 把日期类型标记写回 Workday（与假期表字段一致）
            workday.leave_school = leave_school
            workday.return_school = return_school

            if return_school:
                # 返校日：前两行（morning 位）数据按晚上规则统计
                if is_valid_check(workday.morning, EVENING):
                    teacher.add_count()
            elif leave_school:
                # 离校日：上午 + 离校下午
                if is_valid_check(workday.morning, MORNING):
                    teacher.add_count()
                if is_valid_check(workday.afternoon, LEAVE_AFTERNOON):
                    teacher.add_count()
            elif is_holiday:
                # 假期：不统计
                continue
            else:
                # 正常工作日：上午 + 正常下午 + 晚上
                if is_valid_check(workday.morning, MORNING):
                    teacher.add_count()
                if is_valid_check(workday.afternoon, AFTERNOON):
                    teacher.add_count()
                if is_valid_check(workday.evening, EVENING):
                    teacher.add_count()
