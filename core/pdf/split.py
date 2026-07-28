from datetime import datetime
from pathlib import Path
from typing import List

from loguru import logger
from pypdf import PdfReader, PdfWriter

from core.config import OUTPUT_DIR


def _split_pdf_save_path(base_name: str, range_str: str) -> Path:
    """
    确保输出目录存在，处理文件名冲突，返回最终保存路径。
    目录为 OUTPUT_DIR/PDF/拆分/
    """
    output_dir = OUTPUT_DIR / "PDF" / "拆分"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 基础文件名：原文件名_范围
    file_name = f"{base_name}_{range_str}"
    output_path = output_dir / f"{file_name}.pdf"

    if output_path.exists():
        timestamp = datetime.now().strftime("%H%M%S")
        output_path = output_dir / f"{file_name}_{timestamp}.pdf"
        logger.info(f"文件已存在，使用新文件名: {output_path}")

    return output_path


def split(base_name: str, pdf_path: str, page_range: List) -> Path:
    """
    按指定页码范围拆分 PDF 文件。

    Args:
        pdf_path: 源 PDF 文件路径
        page_range: 拆分范围列表，每个元素为 {"start": int, "end": int}，页码从 1 开始

    Returns:
        拆分后生成的文件路径列表

    Raises:
        FileNotFoundError: PDF 文件不存在
        ValueError: 页码范围无效或超出总页数
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")

    reader = PdfReader(pdf_path)
    total_pages = len(reader.pages)

    for idx, range_dict in enumerate(page_range):
        start = range_dict.get("start")
        end = range_dict.get("end")

        # 参数校验
        if start is None or end is None:
            raise ValueError(f"范围 {idx + 1} 缺少 'start' 或 'end' 字段")
        if not (1 <= start <= total_pages):
            raise ValueError(
                f"范围 {idx + 1} 的起始页 {start} 超出总页数 {total_pages}"
            )
        if not (1 <= end <= total_pages):
            raise ValueError(f"范围 {idx + 1} 的结束页 {end} 超出总页数 {total_pages}")
        if start > end:
            raise ValueError(f"范围 {idx + 1} 的起始页 {start} 大于结束页 {end}")

        # 提取页面（页码转索引）
        writer = PdfWriter()
        for page_num in range(start - 1, end):
            writer.add_page(reader.pages[page_num])

        # 生成范围字符串（用于文件名）
        range_str = f"p{start}-p{end}" if start != end else f"p{start}"
        output_path = _split_pdf_save_path(base_name, range_str)

        # 写入文件
        with open(output_path, "wb") as f:
            writer.write(f)

        logger.info(f"已拆分范围 {start}-{end} 到: {output_path}")

    return OUTPUT_DIR / "PDF" / "拆分"
