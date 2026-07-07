from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.page import PageMargins

from core.score.models import StreamingMap
from loguru import logger
from pathlib import Path


def create_table(
    title,
    students_list,
    Line: StreamingMap,
):
    """
    输出成绩单

    参数:
    - title: 表格标题
    - students_list: 一个列表，包含所有学生的数据
    - Line: 一个StreamingMap对象，包含分数线的数据
    """
    title = title.replace("/", "") + "成绩公示"

    # 判断一下选科，以第一名考试科目代表本班选科
    subject_list_total = [
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
    # 移除多余科目
    subject_list = []
    for subject in subject_list_total:
        if students_list[0].get_data(subject):
            subject_list.append(subject)

    # 创建表头
    wb = Workbook()
    ws = wb.active
    # 确保 ws 不为 None
    if ws is None:
        raise ValueError("无法创建工作表")

    ws.append([title])

    ws["A2"] = "姓名"
    ws.merge_cells("A2:A3")
    for i in range(2, len(subject_list) * 3, 3):
        ws.cell(row=2, column=i, value=subject_list[i // 3])
        ws.cell(row=3, column=i, value="分数")
        ws.cell(row=3, column=i + 1, value="班名")
        ws.cell(row=3, column=i + 2, value="校名")
        ws.merge_cells(start_row=2, start_column=i, end_row=2, end_column=i + 2)

    # 填充分数线
    line_list = ["清北线", "985线", "211线", "特控线", "本科线"]
    for line in line_list:
        fill_list = [line]
        direction = ""
        if students_list[0].selection:
            direction, _, _ = expand_subject_abbreviation(students_list[0].selection)
        for score in subject_list:
            line_key = f"{direction}{score}_{line}"
            if Line.has(line_key):
                fill_list.extend([Line[line_key], "", ""])
            else:
                logger.warning(f"分数线数据缺失: {line_key}")
                fill_list.extend(["", "", ""])
        ws.append(fill_list)

    # 填充学生成绩和过线情况
    for index, student in enumerate(students_list):
        data = [student.name]
        direction = ""
        if student.selection:
            direction, selecting1, selecting2 = expand_subject_abbreviation(
                student.selection
            )
            subject_list_total = [
                "总分",
                "语文",
                "数学",
                "英语",
                direction,
                selecting1,
                selecting2,
            ]
        for subject in subject_list_total:
            try:
                score = student.get_data(subject)
                class_rank = student.get_data(f"{subject}班名")
                school_rank = student.get_data(f"{subject}校名")
                data.extend([score, class_rank, school_rank])
            except KeyError:
                data.extend(["", "", ""])

        ws.append(data)
        for line in line_list:
            line_score = Line[f"{direction}总分_{line}"]
            if (
                index < len(students_list) - 1
                and student.get_data("总分") is not None
                and students_list[index + 1].get_data("总分") is not None
                and student.get_data("总分")
                >= line_score
                > students_list[index + 1].get_data("总分")
            ):
                ws.append([f"{line}过线{index + 1}人"])
                row = ws.max_row
                ws.merge_cells(
                    start_row=row, start_column=1, end_row=row, end_column=ws.max_column
                )
    # 合并表头
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ws.max_column)
    # 定义样式
    alignment = Alignment(horizontal="center", vertical="center")
    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )
    header_fill = PatternFill(
        start_color="dbdbdb", end_color="dbdbdb", fill_type="solid"
    )
    # 为数据行添加样式
    for row in range(2, ws.max_row + 1):
        for col in range(1, ws.max_column):
            cell = ws.cell(row=row, column=col)
            cell.alignment = alignment
            cell.border = thin_border

    ws["A1"].alignment = alignment

    # 为表头添加样式时应用背景填充
    for row in range(2, 4):
        for col in range(1, ws.max_column + 1):
            cell = ws.cell(row=row, column=col)
            cell.alignment = alignment
            if row > 1:  # 第一行除外都加边框
                cell.border = thin_border
            # 为表头添加背景填充
            cell.fill = header_fill

    # 为数据行添加样式
    for row in range(4, ws.max_row + 1):
        for col in range(1, ws.max_column + 1):
            cell = ws.cell(row=row, column=col)
            cell.alignment = alignment
            cell.border = thin_border
            # 为分数列(每3列中的第1列)添加背景填充
            if (col - 2) % 3 == 0 and col >= 2:  # 分数列: 2, 5, 8, 11, 14, 17, 20
                cell.fill = header_fill

    # 自动调整列宽
    # 获取工作表中的最大列数
    max_col = ws.max_column
    # 获取工作表中的最大行数
    max_row = ws.max_row

    # 按列循环，查找每一列的最大值
    for j in range(2, max_col + 1):
        # 按行循环，查找当前列的最大值
        max_d = 1  # 定义初始列宽为1
        for i in range(4, max_row + 1):
            cell_value = ws.cell(i, j).value
            if isinstance(cell_value, str):  # 中文占用多个字节，需要分开处理
                d = len(cell_value.encode("utf-8"))
            else:
                d = len(str(cell_value))

            if d > max_d:
                max_d = d

        k = get_column_letter(j)  # 将数字转化为列名
        ws.column_dimensions[k].width = max_d + 1
    ws.page_margins = PageMargins(
        left=0.1, right=0.1, top=0.1, bottom=0.1, header=0, footer=0
    )

    # 设置页面缩放和居中
    ws.page_setup.fitToWidth = 1  # 将所有列压缩到 1 页宽度
    ws.page_setup.fitToHeight = 0  # 高度不限页数（0 表示自动）

    ws.print_options.horizontalCentered = True
    # （可选）设置纸张方向或纸张大小
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    from core.config import OUTPUT_DIR
    # 确保目录存在
    output_dir = OUTPUT_DIR / "成绩单"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / f"{title}.xlsx"
    # 检查文件是否存在，如果存在则添加时间戳
    if output_path.exists():
        from datetime import datetime

        timestamp = datetime.now().strftime("%H%M%S")
        output_path = output_dir / f"{title}_{timestamp}.xlsx"
        logger.info(f"文件已存在，使用新文件名: {output_path}")
    wb.save(output_path)
    logger.info(f"保存成功: {output_path}")
    return output_path


"""
走班学生成绩映射工具

处理走班制度下的成绩数据标准化问题。
策略: 以第一名的选科组合为主选科,其他学生的缺失科目填充默认值
例如: 第1名是物化地 → 所有学生统一映射为物化地格式
"""


def expand_subject_abbreviation(abbreviation: str) -> tuple[str, str, str]:
    """
    从选科简称还原为完整科目列表

    参数:
        abbreviation: 选科简称,如 "物化地"、"史政地"、"物化生"

    返回:
        完整科目元组,如 ("物理", "化学", "地理")

    异常:
        IndexError: 当 abbreviation 长度不足 3（选科简称应恰好3字）
    """
    # 定义简称到全称的映射
    abbreviation_map = {
        "物": "物理",
        "化": "化学",
        "生": "生物",
        "史": "历史",
        "政": "政治",
        "地": "地理",
    }

    # 逐字转换
    result: list[str] = []
    for char in abbreviation:
        if char in abbreviation_map:
            result.append(abbreviation_map[char])
        else:
            logger.warning(f"未知的选科简称字符: {char}")

    if len(result) != 3:
        logger.error(
            f"选科简称 '{abbreviation}' 转换后只有 {len(result)} 科，期望 3 科"
        )
        # 补全到 3 个，防止 IndexError
        while len(result) < 3:
            result.append("")
    return (result[0], result[1], result[2])
