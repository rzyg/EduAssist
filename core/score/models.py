import json
from typing import Dict, NamedTuple, Optional, Any
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
            return self.subjects[context.replace("班名", "")].class_rank
        elif context.endswith("校名"):
            return self.subjects[context.replace("校名", "")].school_rank
        else:
            logger.warning(f"{context}科不存在")
            return None


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
