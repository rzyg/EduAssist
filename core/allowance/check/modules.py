from dataclasses import dataclass
from datetime import datetime


@dataclass
class Check:
    """
    单次打卡记录，包含签到和签出
    """

    time_in: datetime | None = None
    time_out: datetime | None = None


@dataclass
class Workday:
    """
    全天打卡记录，包含早中晚
    """

    date: datetime
    morning: Check | None = None
    afternoon: Check | None = None
    evening: Check | None = None
    before_holiday: bool = False
    after_holiday: bool = False

    def __post_init__(self):
        if self.before_holiday and self.after_holiday:
            raise ValueError("before_holiday 和 after_holiday 不能同时为 True")


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
