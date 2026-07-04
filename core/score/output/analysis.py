from pydoc import classname

from core.score.models import ClassStatistics, StreamingMap
from typing import List

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.page import PageMargins

from loguru import logger
from pathlib import Path


def output_statistics(
    title, statistics_list: List[ClassStatistics], direction: str, Line: StreamingMap
) -> Path:
    """
    :param title 表名、文件名
    :param statistics_list: 各班各科单双上线统计
    :param direction: 选科方向
    :param Line 分数线
    :return: 输出单双上线统计表
    """
    # 创建表
    wb = Workbook()
    ws = wb.active
    # 确保 ws 不为 None
    if ws is None:
        raise ValueError("无法创建工作表")

    # 写入表头
    title = title.replace("/", "") + "成绩分析"
    write_sheet_head(ws, direction, Line)

    # 写入数据
    write_data(ws, statistics_list, direction)
    # 设置表格样式
    theme_excel(ws)
    # 确保目录存在
    output_dir = Path.cwd() / "output" / "成绩分析"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{title}.xlsx"
    wb.save(output_path)
    logger.info(f"保存成功: {output_path}")
    return output_path


def write_sheet_head(ws, direction: str, Line: StreamingMap):
    """
    :param ws: 工作表
    :param direction: 选科方向
    :param Line: 分数线
    :return:
    """
    subject_list = [
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
    if direction == "物理":
        subject_list.remove("历史")
    elif direction == "历史":
        subject_list.remove("物理")
    total_line = [
        "清北线",
        "985线",
        "211线",
        "特控线",
        "本科线",
    ]

    first_line = ["班级", "科目"]
    second_line = ["", ""]
    third_line = ["", "人数"]
    for subject in subject_list:
        first_line.extend([subject, "", "", "", ""])
        for line in total_line:
            line_score = Line.get(f"{direction}{subject}_{line}")
            third_line.append(f"{line_score}")

    ws.append(first_line)

    for i in range(len(subject_list)):
        second_line.extend(
            [
                "清北线",
                "985线",
                "211线",
                "特控线",
                "本科线",
            ]
        )
        ws.merge_cells(
            f"{get_column_letter(i * 5 + 3)}{1}:{get_column_letter(i * 5 + 7)}{1}"
        )
    ws.append(second_line)
    ws.append(third_line)
    ws.merge_cells("A1:A3")
    ws.merge_cells("B1:B2")


def write_data(ws, statistics_list: List[ClassStatistics], direction: str):
    """
    :param ws: 工作表
    :param statistics_list: 各班各科单双上线统计
    :param direction: 选科方向
    :return:
    """
    subject_list = [
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
    if direction == "物理":
        subject_list.remove("历史")
    elif direction == "历史":
        subject_list.remove("物理")
    total_line = [
        "清北线",
        "985线",
        "211线",
        "特控线",
        "本科线",
    ]
    for statistics in statistics_list:
        class_name = statistics.name
        count = statistics.count
        logger.debug(f"正在处理班级 {class_name} 的数据")
        data: dict = statistics.get_statistics_data()
        write_info = [statistics.name, count]
        for subject in subject_list:
            for line in total_line:
                obj = data[f"{subject}{line}"]
                if line.startswith("总分"):
                    single = obj.single | 0
                    write_info.append(single)
                else:
                    single = obj.single | 0
                    double = obj.double | 0
                    write_info.append(f"{single}/{double}")
        ws.append(write_info)


def theme_excel(ws):
    """
    为工作表添加框线和居中对齐

    :param ws: 工作表
    :return:
    """
    # 定义边框样式
    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )

    # 定义居中对齐样式
    center_alignment = Alignment(horizontal="center", vertical="center")

    # 遍历所有单元格，应用边框和居中
    for row in ws.iter_rows(
        min_row=1, max_row=ws.max_row, min_col=1, max_col=ws.max_column
    ):
        for cell in row:
            cell.border = thin_border
            cell.alignment = center_alignment

    logger.debug(f"表格样式设置完成，共 {ws.max_row} 行，{ws.max_column} 列")
