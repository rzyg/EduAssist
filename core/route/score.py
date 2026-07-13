from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from loguru import logger
import tempfile
import os

# 创建路由器实例
router = APIRouter(
    prefix="/api/v1/score",  # 统一前缀
    tags=["成绩"],  # 文档分组
)


@router.post("/transcript")
def transcript(
    title: str = Form(..., description="成绩单标题"),
    scoreSheet: UploadFile = File(..., description="原始成绩单"),
    lineSheet: UploadFile = File(None, description="分数线表格（可选）"),
    lineJSON: str = Form(None, description="分数线 JSON 文本（可选）"),
):
    """
    上传成绩单并生成分析报表

    :param title: 成绩单标题（必填）
    :param scoreSheet: 原始成绩单文件（必填）
    :param lineSheet: 分数线表格文件（可选，与 lineJSON 二选一）
    :param lineJSON: 分数线 JSON 文本（可选，与 lineSheet 二选一）
    :return: 生成的 Excel 文件路径
    """
    tmp_score_path = None
    tmp_line_path = None

    try:
        # 验证分数线参数：必须提供且只能提供一个
        if lineSheet and lineJSON:
            raise HTTPException(
                status_code=400,
                detail="分数线表格和 JSON 文本不能同时提供，请选择其中一种方式",
            )

        if not lineSheet and not lineJSON:
            raise HTTPException(
                status_code=400, detail="必须提供分数线表格或 JSON 文本其中之一"
            )

        # 如果提供了 JSON，验证大小
        if lineJSON:
            MAX_JSON_SIZE = 100 * 1024  # 100 KB
            if len(lineJSON) > MAX_JSON_SIZE:
                raise HTTPException(
                    status_code=400, detail="分数线 JSON 数据过大（上限 100KB）"
                )

        # 创建临时文件
        tmp_score_path = save_upload_file(scoreSheet)

        # 加载成绩单表格并构建映射
        from core.score.map import build_score_mapping, loadData

        score_ws = loadData(tmp_score_path)
        map_list = build_score_mapping(score_ws)

        # 处理分数线数据
        from core.score.models import StreamingMap

        lines = StreamingMap()

        if lineJSON:
            # 方式1：从 JSON 文本加载
            lines.load_from_json_text(lineJSON)
        else:
            # 方式2：从分数线表格加载
            tmp_line_path = save_upload_file(lineSheet)
            from core.score.map import get_lines

            line_ws = loadData(tmp_line_path)
            lines = get_lines(line_ws)

        # 提取学生成绩
        from core.score.extract import extract_score
        from core.score.output.transcript import output_transcript

        students_list = extract_score(score_ws, map_list)
        output_path = output_transcript(title, students_list, lines)

        return {"output_path": str(output_path)}

    except HTTPException:
        # 直接抛出的 HTTP 异常
        raise
    except Exception as e:
        logger.error(f"处理失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # 清理临时文件
        if tmp_score_path and os.path.exists(tmp_score_path):
            os.unlink(tmp_score_path)
        if tmp_line_path and os.path.exists(tmp_line_path):
            os.unlink(tmp_line_path)


@router.post("/analysis")
def analysis_upload(
    title: str = Form(..., description="分析报表标题"),
    scoreSheet: UploadFile = File(..., description="原始成绩单"),
    lineSheet: UploadFile = File(None, description="分数线表格（可选）"),
    lineJSON: str = Form(None, description="分数线 JSON 文本（可选）"),
):
    """
    上传成绩单并生成成绩分析报表

    :param title: 分析报表标题（必填）
    :param scoreSheet: 原始成绩单文件（必填）
    :param lineSheet: 分数线表格文件（可选，与 lineJSON 二选一）
    :param lineJSON: 分数线 JSON 文本（可选，与 lineSheet 二选一）
    :return: 生成的 Excel 文件路径
    """
    tmp_score_path = None
    tmp_line_path = None

    try:
        # 验证分数线参数：必须提供且只能提供一个
        if lineSheet and lineJSON:
            raise HTTPException(
                status_code=400,
                detail="分数线表格和 JSON 文本不能同时提供，请选择其中一种方式",
            )

        if not lineSheet and not lineJSON:
            raise HTTPException(
                status_code=400, detail="必须提供分数线表格或 JSON 文本其中之一"
            )

        # 如果提供了 JSON，验证大小
        if lineJSON:
            MAX_JSON_SIZE = 100 * 1024  # 100 KB
            if len(lineJSON) > MAX_JSON_SIZE:
                raise HTTPException(
                    status_code=400, detail="分数线 JSON 数据过大（上限 100KB）"
                )

        # 创建临时文件
        tmp_score_path = save_upload_file(scoreSheet)

        # 加载成绩单表格并构建映射
        from core.score.map import build_score_mapping, loadData

        score_ws = loadData(tmp_score_path)
        map_list = build_score_mapping(score_ws)

        # 处理分数线数据
        from core.score.models import StreamingMap

        lines = StreamingMap()

        if lineJSON:
            # 方式1：从 JSON 文本加载
            lines.load_from_json_text(lineJSON)
        else:
            # 方式2：从分数线表格加载
            tmp_line_path = save_upload_file(lineSheet)
            from core.score.map import get_lines

            line_ws = loadData(tmp_line_path)
            lines = get_lines(line_ws)

        # 提取学生成绩
        from core.score.extract import extract_score

        students_list = extract_score(score_ws, map_list)

        # 导入班级管理器，用于将学生分班级管理
        from core.score.models import ClassManager

        class_manager = ClassManager()
        for student in students_list:
            class_manager.add_student(student)

        # 执行成绩分析
        from core.score.analysis import analysis

        statistics_list, direction = analysis(class_manager, lines)

        # 导出分析报表
        from core.score.output.analysis import output_statistics

        output_path = output_statistics(title, statistics_list, direction, lines)

        return {"output_path": str(output_path)}

    except HTTPException:
        # 直接抛出的 HTTP 异常
        raise
    except Exception as e:
        logger.error(f"处理失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # 清理临时文件
        if tmp_score_path and os.path.exists(tmp_score_path):
            os.unlink(tmp_score_path)
        if tmp_line_path and os.path.exists(tmp_line_path):
            os.unlink(tmp_line_path)


def save_upload_file(scoreSheet: UploadFile) -> str:
    """
    从上传的文件中创建临时文件
    :param scoreSheet: 上传的文件
    :return: 临时文件的路径
    """
    # 检查文件名是否存在
    if not scoreSheet.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    suffix = os.path.splitext(scoreSheet.filename)[1]
    # 如果没有扩展名，默认使用 .xlsx
    if not suffix:
        suffix = ".xlsx"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
        content = scoreSheet.file.read()
        tmp_file.write(content)
        tmp_file_path = tmp_file.name
        logger.info(f"临时文件保存在：{tmp_file_path}")
    return tmp_file_path
