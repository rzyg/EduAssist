from dataclasses import dataclass
from datetime import date


@dataclass
class DayData:
    """
    日数据类
    @param holiday: 是否是节假日（补班）
    @:param date: 日期
    @:param name: 节假日名称
    @:param after: 是否假期后补班
    """

    holiday: bool
    date: date
    name: str
    after: bool

    def __post_init__(self):
        if self.holiday and self.after:
            raise ValueError("节假日不能是假期后补班")
