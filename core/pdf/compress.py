from datetime import datetime
from pathlib import Path
from typing import Union

import pikepdf
from loguru import logger

from core.config import OUTPUT_DIR


def _compressed_pdf_save_path(file_name: str) -> Path:
    """确保输出目录存在 → 处理文件名冲突 → 保存并返回路径。"""
    output_dir = OUTPUT_DIR / "PDF" / "压缩"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / f"{file_name}.pdf"
    if output_path.exists():
        timestamp = datetime.now().strftime("%H%M%S")
        output_path = output_dir / f"{file_name}_{timestamp}.pdf"
        logger.info(f"文件已存在，使用新文件名: {output_path}")
    return output_path


def _resolve_compression_level(level: Union[int, str]) -> int:
    """
    将压缩等级统一转换为 pikepdf 可用的整数 (0-9)。

    支持字符串: "low" / "medium" / "high"
    也直接接受整数 0-9。
    """
    if isinstance(level, str):
        level_map = {"low": 1, "medium": 5, "high": 9}
        resolved = level_map.get(level.lower(), 5)
        if level.lower() not in level_map:
            logger.warning(f"未知压缩等级 '{level}'，使用默认 'medium'(5)")
        return resolved

    # 整数范围钳制
    if level < 0:
        return 0
    if level > 9:
        return 9
    return level


def compress(
    pdf_path: str,
    file_name: str,
    compression_level: Union[int, str] = 5,
) -> Path:
    """
    压缩 PDF 文件。

    使用 pikepdf 进行流压缩（FlateDecode）、资源清理。
    不同压缩等级控制是否压缩流及清理未引用资源。

    Args:
        pdf_path: 源 PDF 文件路径
        file_name: 输出文件名（不含扩展名）
        compression_level: 压缩等级。
            整数 0-9，0=不压缩、9=最大压缩；
            字符串 "low" / "medium" / "high"。

    Returns:
        压缩后的文件路径

    Raises:
        FileNotFoundError: PDF 文件不存在
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")

    level = _resolve_compression_level(compression_level)

    # 读取原文件信息
    original_size = pdf_path.stat().st_size
    logger.info(f"开始压缩: {pdf_path.name} (大小={original_size / 1024:.1f}KB, 等级={level})")

    with pikepdf.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        save_path = _compressed_pdf_save_path(file_name)

        # 根据压缩等级配置压缩行为
        compress_streams = level > 0          # 等级>=1 时压缩流
        clean_resources = level >= 4           # 等级>=4 时清理未引用资源

        # 清理未引用资源（在 save 前调用）
        if clean_resources:
            pdf.remove_unreferenced_resources()

        pdf.save(
            save_path,
            compress_streams=compress_streams,
            object_stream_mode=pikepdf.ObjectStreamMode.generate,
            recompress_flate=compress_streams,
        )

    # 计算压缩前后大小对比
    compressed_size = save_path.stat().st_size
    ratio = (1 - compressed_size / original_size) * 100 if original_size > 0 else 0
    logger.info(
        f"压缩完成: {original_size / 1024:.1f}KB → {compressed_size / 1024:.1f}KB "
        f"({ratio:+.1f}%) 共 {total_pages} 页"
    )

    return save_path
