import os
import tempfile
from typing import List

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from loguru import logger

# 创建路由器实例
router = APIRouter(
    prefix="/api/v1/pdf",  # 统一前缀
    tags=["PDF编辑"],  # 文档分组
)


@router.post("/merge")
def merge(
    file_name: str = Form(..., description="文件名"),
    pdf_list: List[UploadFile] = File(..., description="PDF列表"),
):
    """
    上传多个PDF合并

    :param file_name: 文件名
    :param pdf_list: 要合并的PDF列表
    :return: 生成的 PDF 文件路径
    """

    tmp_path_list = list()

    try:
        # 创建临时文件
        for pdf in pdf_list:
            tmp_path = save_upload_file(pdf)
            tmp_path_list.append(tmp_path)

        # 合并PDF
        from core.pdf.merge import merge

        output_path = merge(tmp_path_list, file_name)
        return {"output_path": str(output_path)}
    except HTTPException:
        # 直接抛出的 HTTP 异常
        raise
    except Exception as e:
        logger.error(f"处理失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # 清理临时文件
        for tmp_path in tmp_path_list:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)


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
