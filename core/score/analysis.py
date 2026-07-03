from core.score.models import ClassManager, ClassStatistics, Student, StreamingMap

from typing import Dict, NamedTuple, Optional, Any, List
from loguru import logger


def analysis(
    classesData: ClassManager, LineScore: StreamingMap
) -> List[ClassStatistics]:
    """
    :param classesData: 班级管理器
    :param LineScore: 分数线映射
    :return: 各班各科单双上线统计
    """
    class_list = classesData.get_all_classes()
    statistics_list = list()
    for class_name in class_list:
        students = classesData.get_class(class_name)
        statistics = run_statistics(class_name, students, LineScore)
        statistics_list.append(statistics)
    return statistics_list


def run_statistics(
    class_name, students: List[Student], LineScore: StreamingMap
) -> ClassStatistics:
    """
    :param class_name: 班级名称
    :param students: 学生列表
    :param LineScore: 分数线映射
    :return: 班级各科单双上线统计
    """
    statistics = ClassStatistics(class_name)
    direction = detect_selection_direction(students)
    total_subjects_list = [
        "总分",
        "语文",
        "数学",
        "英语",
        "物理",
        "化学",
        "生物",
        "历史",
        "政治",
        "地理",
    ]
    total_lines = ["清北线", "985线", "211线", "特控线", "本科线"]
    if direction == "物理":
        total_subjects_list.remove("历史")
    elif direction == "历史":
        total_subjects_list.remove("物理")
    else:
        direction = ""
    for person in students:
        logger.debug(f"正在处理学生 {person.name} 的数据")
        total_score = person.get_data("总分")
        for subject in total_subjects_list:
            if subject in person.subjects:
                for line in total_lines:
                    line_total_score = LineScore.get(f"{direction}总分_{line}")
                    score = person.get_data(subject)
                    line_score = LineScore.get(f"{direction}{subject}_{line}")
                    if score and line_score and score >= line_score:
                        statistics.increment_single(f"{subject}{line}")
                        if (
                            subject != "总分"
                            and line_total_score
                            and total_score >= line_total_score
                        ):
                            statistics.increment_double(f"{subject}{line}")
    return statistics


def detect_selection_direction(students: List[Student]) -> str:
    """
    判断班级的选科方向（物理方向/历史方向）

    原理：
    - 如果学生有物理科目，则为物理方向
    - 如果学生有历史科目，则为历史方向

    Args:
        students: 学生列表

    Returns:
        "物理" 或 "历史"，如果无法判断则返回 "未知"
    """
    has_physics = False
    has_history = False

    for student in students:
        for subject in student.subjects.keys():
            if subject == "物理":
                has_physics = True
            elif subject == "历史":
                has_history = True

        # 提前退出：如果已经确定两个都有，可以根据第一个学生的情况判断
        if has_physics or has_history:
            break

    if has_physics and not has_history:
        return "物理"
    elif has_history and not has_physics:
        return "历史"
    elif has_physics and has_history:
        return "未分科"
    else:
        return "未知"
