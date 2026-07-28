"""
PDF 压缩 — 基于 ocrmypdf 的有损/无损优化。

仅使用 ocrmypdf 的压缩/优化功能，跳过 OCR 识别步骤（skip_text=True）。
底层依赖 Ghostscript 进行 PDF 重写和流压缩。
"""
from datetime import datetime
from pathlib import Path
from typing import Union

import ocrmypdf
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
    将压缩等级统一转换为整数 (0-9)。

    支持字符串: "low" / "medium" / "high"
    也直接接受整数 0-9。
    """
    if isinstance(level, str):
        level_map = {"low": 1, "medium": 5, "high": 9}
        resolved = level_map.get(level.lower(), 5)
        if level.lower() not in level_map:
            logger.warning(f"未知压缩等级 '{level}'，使用默认 'medium'(5)")
        return resolved

    if level < 0:
        return 0
    if level > 9:
        return 9
    return level


def _level_to_ocrmypdf_params(level: int) -> dict:
    """
    将 0-9 整数等级映射为 ocrmypdf.ocr() 的参数。

    等级划分:
      0        — 不压缩（optimize=0，仅复制）
      1-3      — 轻度压缩（optimize=1，无损优化 + 高 JPEG 质量）
      4-6      — 中等压缩（optimize=2，有损优化 + 中度 JPEG 质量）
      7-9      — 激进压缩（optimize=3，激进有损 + 低 JPEG 质量）
    """
    if level == 0:
        return {
            "optimize": 0,
            "output_type": "pdf",
        }

    if level <= 3:
        return {
            "optimize": 1,
            "jpg_quality": 85,
            "output_type": "pdf",
        }

    if level <= 6:
        return {
            "optimize": 2,
            "jpg_quality": 65,
            "output_type": "pdf",
        }

    # level 7-9
    return {
        "optimize": 3,
        "jpg_quality": 35,
        "output_type": "pdf",
    }


def compress(
    pdf_path: str,
    file_name: str,
    compression_level: Union[int, str] = 5,
) -> Path:
    """
    压缩 PDF 文件（跳过 OCR）。

    使用 ocrmypdf 的优化管线：
      1. 通过 Ghostscript 重写 PDF 流（FlateDecode / JPEG 压缩）
      2. 按等级控制 optimize 级别和图片质量
      3. 跳过 OCR 识别步骤（skip_text=True）

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
        ocrmypdf.MissingDependencyError: Ghostscript 或 Tesseract 未安装
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")

    level = _resolve_compression_level(compression_level)

    # 读取原文件信息
    original_size = pdf_path.stat().st_size
    logger.info(
        f"开始压缩: {pdf_path.name} (大小={original_size / 1024:.1f}KB, 等级={level})"
    )

    save_path = _compressed_pdf_save_path(file_name)

    # 构建 ocrmypdf 参数
    ocr_params = _level_to_ocrmypdf_params(level)
    ocr_params["skip_text"] = True  # 跳过 OCR 识别
    ocr_params["progress_bar"] = False

    # 调用 ocrmypdf 进行压缩
    exit_code = ocrmypdf.ocr(
        str(pdf_path),
        str(save_path),
        **ocr_params,
    )

    if exit_code != ocrmypdf.ExitCode.ok:
        raise RuntimeError(
            f"ocrmypdf 返回非正常退出码 {exit_code}，压缩可能未完成"
        )

    # 计算压缩前后大小对比
    compressed_size = save_path.stat().st_size
    ratio = (1 - compressed_size / original_size) * 100 if original_size > 0 else 0
    logger.info(
        f"压缩完成: {original_size / 1024:.1f}KB → {compressed_size / 1024:.1f}KB "
        f"({ratio:+.1f}%)"
    )

    return save_path
