from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from loguru import logger
from core.db.init import initDatabase
from core.logger import setup_logging
import tempfile
import os

# 初始化日志
setup_logging()
# 初始化数据库
initDatabase()

app = FastAPI()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/v1/register")
async def register(username: str, phone: str, identity: str):
    logger.info(f"username:{username},phone:{phone},identity:{identity}")
    from pathlib import Path
    from core.db.CRUD import create_record

    databasePath = Path.cwd() / "data" / "data.db"
    try:
        create_record(
            databasePath,
            "user",
            {"username": username, "phone": phone, "identity": identity},
        )
        return {"message": "注册成功"}
    except Exception as e:
        logger.error(e)
        return {"message": "注册失败"}


@app.post("/api/v1/transcript-upload-1-xlsx")
async def transcript_1(
    title: str,
    scoreSheet: UploadFile = File(...),
    lineJSON: str = Form(...),
):
    tmp_score_path = None
    try:
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
        from core.score.transcript.extract import extract_score
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


@app.post("/api/v1/transcript-upload-2-xlsx")
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
        from core.score.transcript.extract import extract_score
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


if __name__ == "__main__":
    import uvicorn

    config = uvicorn.Config(
        "core.main:app",
        host="127.0.0.1",
        port=8000,
        log_level="warning",  # 只显示 warning 及以上
        access_log=False,  # 完全关闭访问日志
    )
    server = uvicorn.Server(config)
    server.run()
