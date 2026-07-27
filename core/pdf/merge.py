from typing import List

from loguru import logger
from pypdf import PdfWriter


def _merged_pdf_save_path(file_name: str):
    """确保输出目录存在 → 处理文件名冲突 → 保存并返回路径。"""
    from core.config import OUTPUT_DIR

    output_dir = OUTPUT_DIR / "PDF" / "合并"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / f"{file_name}.pdf"
    if output_path.exists():
        from datetime import datetime

        timestamp = datetime.now().strftime("%H%M%S")
        output_path = output_dir / f"{file_name}_{timestamp}.pdf"
        logger.info(f"文件已存在，使用新文件名: {output_path}")
    return output_path


def merge(pdf_list: List[str], file_name: str):
    """
    合并PDF文件
    :param pdf_list:PDF文件列表
    :param file_name: 合并后的文件名
    :return:
    """
    merger = PdfWriter()
    for pdf in pdf_list:
        merger.append(pdf)
    save_path = _merged_pdf_save_path(file_name)
    merger.write(save_path)
    merger.close()
    return save_path
