from pathlib import Path
from loguru import logger
from core.score.models import StreamingMap
from openpyxl import load_workbook, Workbook
from openpyxl.worksheet.worksheet import Worksheet


# 加载excel文件
def loadData(path: str | Path) -> Worksheet:
    """
    加载excel文件
    :param path: 文件路径
    :return: 工作表
    """
    wb = load_workbook(filename=path)
    return wb.worksheets[0]


def getPosition(ws: Worksheet, context: str, start_row: int = 1, start_col: int = 1):
    """返回 (row, col) 元组"""
    for row_idx in range(start_row, ws.max_row + 1):
        for col_idx in range(start_col, ws.max_column + 1):
            value = ws.cell(row=row_idx, column=col_idx).value
            if value and context in str(value):
                return [row_idx, col_idx]
    logger.warning(f"未找到包含 '{context}' 的单元格")
    return None


def build_mapping(ws: Worksheet) -> StreamingMap:
    """
    根据工作表构建列映射
    自动适配赋分/非赋分：优先匹配赋分列，不存在则匹配原始分列

    Args:
        ws: Excel 工作表

    Returns:
        StreamingMap 实例，包含所有字段的列号
    """
    mapping = StreamingMap()

    class_name = getPosition(ws, "班", 1, 1)
    if class_name is None:
        raise ValueError("Excel 表中缺少班级字段")
    mapping["班级"] = class_name[1]

    # ========== 1. 总分（自动适配赋分/原始）==========
    # getPosition 会优先查"赋分总分"，没有则查"总分"
    total_pos = getPosition(ws, "总分", 1, 2)
    if total_pos is None:
        raise ValueError("Excel 表中缺少总分字段")

    total_x = total_pos[1]
    mapping["总分"] = total_x
    mapping["总分班名"] = getPosition(ws, "班", 1, total_x)[1]
    mapping["总分校名"] = getPosition(ws, "校", 1, total_x)[1]

    # ========== 2. 固定科目（语数英）==========
    for subject in ["语文", "数学", "英语"]:
        pos = getPosition(ws, subject, 1, 1)
        if pos is None:
            raise ValueError(f"Excel 表中缺少必要字段: {subject}")

        subject_x = pos[1]
        mapping[f"{subject}"] = subject_x
        mapping[f"{subject}班名"] = getPosition(ws, "班", 1, subject_x)[1]
        mapping[f"{subject}校名"] = getPosition(ws, "校", 1, subject_x)[1]

    # ========== 3. 选考科目（动态匹配，存在则添加）==========
    optional_subjects = ["物理", "历史", "生物", "化学", "地理", "政治"]
    found_subjects = []

    for subject in optional_subjects:
        pos = getPosition(ws, subject, 1, total_x)
        if pos:
            subject_x = pos[1]
            mapping[f"{subject}"] = subject_x
            mapping[f"{subject}班名"] = getPosition(ws, "班", 1, subject_x)[1]
            mapping[f"{subject}校名"] = getPosition(ws, "校", 1, subject_x)[1]
            found_subjects.append(subject)
            logger.debug(f"找到选考科目: {subject}，列号: {subject_x}")
        else:
            logger.debug(f"未找到选考科目: {subject}，跳过")

    logger.info(f"列映射构建完成，共 {len(mapping)} 个字段，选考科目: {found_subjects}")
    return mapping
