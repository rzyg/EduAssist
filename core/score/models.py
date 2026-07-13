import json
from typing import Dict, NamedTuple, Optional, Any, List
from pathlib import Path
from dataclasses import dataclass, field
from loguru import logger


class SubjectScore(NamedTuple):
    """单科成绩和排名"""

    score: float
    class_rank: Any
    school_rank: Any


class Student:
    def __init__(
        self,
        student_class: Any,
        name: str,
        subjects: Dict[str, SubjectScore],
        selection: str,
    ):
        self.student_class = student_class
        self.name = name
        self.subjects = subjects  # {"语文": SubjectScore(120, 5, 20), ...}
        self.selection = selection

    # 便捷属性：快速获取某科数据
    def get_data(self, context: str):
        if context in self.subjects:
            return self.subjects[context].score
        elif context.endswith("班名"):
            subject = context.replace("班名", "")
            if subject in self.subjects:
                return self.subjects[subject].class_rank
            logger.warning(f"{subject}科不存在")
            return None
        elif context.endswith("校名"):
            subject = context.replace("校名", "")
            if subject in self.subjects:
                return self.subjects[subject].school_rank
            logger.warning(f"{subject}科不存在")
            return None
        else:
            logger.warning(f"{context}科不存在")
            return None

    def get_selection(self):
        """
        :return: 返回有效科目列表
        """
        return list(self.subjects)


@dataclass
class StreamingMap:
    """
    分科索引表 - 存储 Excel 中各字段的列坐标

    使用示例:
        mapping = StreamingMap()
        mapping.set("姓名", 3)
        mapping.set("语文成绩", 8)
        mapping.set("总分", 6)

        # 或批量设置
        mapping.update({
            "姓名": 3,
            "语文成绩": 8,
            "数学成绩": 9,
            "英语成绩": 10,
            "总分": 6,
        })

        # 获取列号
        col = mapping.get("姓名")  # 返回 3
        col = mapping["姓名"]      # 也可以用下标
    """

    # 存储字段名 -> 列号的映射
    _map: Dict[str, int | float] = field(default_factory=dict)

    def set(self, field_name: str, column: int | float) -> None:
        """
        设置字段的列号
        """
        self._map[field_name] = column

    def get(
        self, field_name: str, default: Optional[int | float] = None
    ) -> Optional[int | float]:
        """
        获取字段的列号
        """
        return self._map.get(field_name, default)

    def update(self, mappings: Dict[str, int | float]) -> None:
        """
        批量设置映射
        """
        self._map.update(mappings)

    def remove(self, field_name: str) -> None:
        """
        移除字段映射
        """
        self._map.pop(field_name, None)

    def has(self, field_name: str) -> bool:
        """
        检查字段是否存在
        """
        return field_name in self._map

    def get_all(self) -> Dict[str, int | float]:
        """
        获取所有映射（返回副本）
        """
        return self._map.copy()

    def clear(self) -> None:
        """
        清空所有映射
        """
        self._map.clear()

    def __getitem__(self, field_name: str) -> int | float:
        """
        支持下标访问: mapping["姓名"]
        """
        return self._map[field_name]

    def __setitem__(self, field_name: str, column: int | float) -> None:
        """
        支持下表赋值: mapping["姓名"] = 3
        """
        self._map[field_name] = column

    def __contains__(self, field_name: str) -> bool:
        """
        支持 in 操作: "姓名" in mapping
        """
        return field_name in self._map

    def __len__(self) -> int:
        """返回映射数量"""
        return len(self._map)

    def __repr__(self) -> str:
        return f"StreamingMap({self._map})"

    # ========== 保存和加载配置 ==========

    def save_to_file(self, path: str | Path) -> None:
        """
        保存映射配置到 JSON 文件
        """
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._map, f, ensure_ascii=False, indent=2)

    def load_from_file(self, path: str | Path) -> None:
        """
        从 JSON 文件加载映射配置
        """
        with open(path, "r", encoding="utf-8") as f:
            self._map = json.load(f)

    def load_from_json_text(self, json_text: str) -> None:
        """
        从 JSON 格式文本加载映射配置（键值对）

        Args:
            json_text: JSON 格式的字符串，包含所有映射数据
        """
        self._map = json.loads(json_text)


class ClassManager:
    """
    班级管理器 - 按班级分组管理学生

    使用示例:
        manager = ClassManager()
        manager.add_student(student1)
        manager.add_student(student2)

        # 获取某班所有学生
        students = manager.get_class("高三1班")

        # 获取所有班级
        all_classes = manager.get_all_classes()
    """

    def __init__(self):
        self.classes: Dict[str, List[Student]] = {}

    def add_student(self, student: Student) -> None:
        """添加学生到对应班级"""
        if not student.student_class:
            logger.warning(f"学生 {student.name} 没有班级信息，跳过添加")
            return

        self.classes.setdefault(student.student_class, []).append(student)

    def get_class(self, class_name: str) -> List[Student]:
        """获取指定班级的学生列表"""
        return self.classes.get(class_name, [])

    def get_all_classes(self) -> List[str]:
        """获取所有班级名称"""
        return list(self.classes.keys())

    def get_student_count(self, class_name: str) -> int:
        """获取指定班级的学生人数"""
        return len(self.classes.get(class_name, []))

    def export_to_dict(self) -> Dict[str, List[Student]]:
        """导出为字典格式"""
        return self.classes.copy()


@dataclass
class SubjectStatistics:
    """单科统计数据"""

    single: int = 0  # 单上线人数
    double: int = 0  # 双上线人数


class ClassStatistics:
    """
    班级统计类 - 统计各科目单双上线情况

    使用示例:
        stats = ClassStatistics("高三1班")
        stats.increment_single("语文清北线")
        stats.increment_double("数学985线")

        data = stats.get_statistics_data()
    """

    def __init__(self, name: str, count: int):
        self.name = name
        self.statistics: Dict[str, SubjectStatistics] = {}
        self.count = count

    def init_subject(self, subject: str) -> None:
        """确保科目统计对象存在"""
        if subject not in self.statistics:
            self.statistics[subject] = SubjectStatistics()

    def increment_single(self, subject: str) -> None:
        """增加单上线计数"""
        self.statistics[subject].single += 1

    def increment_double(self, subject: str) -> None:
        """增加双上线计数"""
        self.statistics[subject].double += 1

    def get_statistics_data(self) -> Dict[str, SubjectStatistics]:
        """获取统计数据副本"""
        return self.statistics.copy()
