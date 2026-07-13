from core.score.models import ClassManager, ClassStatistics, Student, StreamingMap

from typing import List, Tuple
from loguru import logger


def analysis(
    classesData: ClassManager, LineScore: StreamingMap
) -> Tuple[List[ClassStatistics], str]:
    """
    :param classesData: 班级管理器
    :param LineScore: 分数线映射
    :return: 各班各科单双上线统计
    """
    class_list = classesData.get_all_classes()
    if not class_list:
        logger.warning("没有班级数据")
        raise ValueError("没有班级数据")
    statistics_list = list()
    # 通过第一个班判断选科方向，而不是逐个班判断
    first_class = classesData.get_class(class_list[0])
    direction = detect_selection_direction(first_class)
    for class_name in class_list:
        count = classesData.get_student_count(class_name)
        students = classesData.get_class(class_name)
        statistics = run_statistics(class_name, count, students, LineScore, direction)
        statistics_list.append(statistics)
    return statistics_list, direction


def run_statistics(
    class_name,
    count: int,
    students: List[Student],
    LineScore: StreamingMap,
    direction: str,
) -> ClassStatistics:
    """
    :param class_name: 班级名称
    :param count: 学生数量
    :param students: 学生列表
    :param LineScore: 分数线映射
    :param direction: 选科方向
    :return: 班级各科单双上线统计
    """
    statistics = ClassStatistics(class_name, count)

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
        "小语种",
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
            for line in total_lines:
                # 初始化单双上线统计
                statistics.init_subject(f"{subject}{line}")
                # 获取分数、分数线、总分分数线
                if subject in person.subjects:
                    line_total_score = LineScore.get(f"{direction}总分_{line}")
                    score = person.get_data(subject)
                    line_score = LineScore.get(f"{direction}{subject}_{line}")
                    # 判断单双上线
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
        raise ValueError("无法判断选科方向")
