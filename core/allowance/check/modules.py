from dataclasses import dataclass
from datetime import datetime, time


@dataclass
class Check:
    """
    单次打卡记录，包含签到和签出
    """

    time_in: time | None = None
    time_out: time | None = None


@dataclass
class Workday:
    """
    全天打卡记录，包含早中晚
    """

    date: datetime
    morning: Check | None = None
    afternoon: Check | None = None
    evening: Check | None = None
    leave_school: bool = False
    return_school: bool = False

    def __post_init__(self):
        if self.leave_school and self.return_school:
            raise ValueError("leave_school 和 return_school 不能同时为 True")


@dataclass
class Teacher:
    """
    :param department 所属部门
    :param workdays 整周打卡数据
    :param count 有效的打卡次数（单次签到签出都在合法范围算一次）
    """

    name: str
    department: str
    workdays: list[Workday]
    count: int = 0

    def add_count(self):
        self.count = self.count + 1
