from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from loguru import logger
import tempfile
import os


# 创建路由器实例
router = APIRouter(
    prefix="/api/v1/score",  # 统一前缀
    tags=["成绩"],  # 文档分组
)


@router.post("/transcript-upload-1-xlsx")
async def transcript_1(
    title: str,
    scoreSheet: UploadFile = File(...),
    lineJSON: str = Form(...),
):
    tmp_score_path = None
    try:
        # 限制 JSON 大小，防止恶意 / 超大 payload
        MAX_JSON_SIZE = 100 * 1024  # 100 KB
        if len(lineJSON) > MAX_JSON_SIZE:
            raise HTTPException(
                status_code=400, detail="分数线 JSON 数据过大（上限 100KB）"
            )

        # 创建临时文件
        tmp_score_path = await summon_temp_file(scoreSheet)

        # 加载表格并构建映射
        from core.score.map import build_score_mapping, loadData
        from core.score.models import StreamingMap

        score_ws = loadData(tmp_score_path)
        map_list = build_score_mapping(score_ws)
        lines = StreamingMap()
        lines.load_from_json_text(lineJSON)

        # 提取学生成绩
        from core.score.extract import extract_score
        from core.score.transcript.output import create_table

        students_list = extract_score(score_ws, map_list)
        output_path = create_table(title, students_list, lines)
        return {"output_path": output_path}
    except HTTPException:
        # 直接抛出的 HTTP 异常
        raise
    except Exception as e:
        logger.error(f"处理失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if tmp_score_path and os.path.exists(tmp_score_path):
            os.unlink(tmp_score_path)


@router.post("/transcript-upload-2-xlsx")
async def transcript_2(
    title: str,
    scoreSheet: UploadFile = File(..., description="原始成绩单"),
    lineSheet: UploadFile = File(..., description="分数线"),
):
    tmp_score_path = None
    try:
        # 创建临时文件
        tmp_score_path = await summon_temp_file(scoreSheet)
        tmp_line_path = await summon_temp_file(lineSheet)

        # 加载表格并构建映射
        from core.score.map import build_score_mapping, loadData, get_lines

        score_ws = loadData(tmp_score_path)
        line_ws = loadData(tmp_line_path)
        map_list = build_score_mapping(score_ws)
        lines = get_lines(line_ws)

        # 提取学生成绩
        from core.score.extract import extract_score
        from core.score.transcript.output import create_table

        students_list = extract_score(score_ws, map_list)
        output_path = create_table(title, students_list, lines)
        return {"output_path": output_path}
    except HTTPException:
        # 直接抛出的 HTTP 异常
        raise
    except Exception as e:
        logger.error(f"处理失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if tmp_score_path and os.path.exists(tmp_score_path):
            os.unlink(tmp_score_path)


async def summon_temp_file(scoreSheet: UploadFile) -> str:
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
        content = await scoreSheet.read()
        tmp_file.write(content)
        tmp_file_path = tmp_file.name
        logger.info(f"临时文件保存在：{tmp_file_path}")
    return tmp_file_path
