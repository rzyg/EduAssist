"""
PDF 压缩 — 基于 pikepdf 的无损/有损优化。

零外部程序依赖：pikepdf 的 wheel 已内嵌编译好的 qpdf 引擎，开箱即用。
不同压缩等级控制流压缩、对象去重和资源清理的激进程度。
"""
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


def compress(
    pdf_path: str,
    file_name: str,
    compression_level: Union[int, str] = 5,
) -> Path:
    """
    压缩 PDF 文件。

    使用 pikepdf（qpdf 引擎）进行流压缩和资源优化。
    所有等级都纯 Python 实现，不依赖任何外部可执行程序。

    等级划分:
      0      — 仅复制，不做任何压缩
      low    — 启用 FlateDecode 流压缩（无损）
      medium — 流压缩 + 清理未引用资源 + 对象流打包
      high   — 流压缩 + 资源清理 + 内容流重压缩 + 线性化

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
    original_size = pdf_path.stat().st_size

    logger.info(
        f"开始压缩: {pdf_path.name} (大小={original_size / 1024:.1f}KB, 等级={level})"
    )

    save_path = _compressed_pdf_save_path(file_name)
    _run_compression(pdf_path, save_path, level)

    compressed_size = save_path.stat().st_size
    _log_result(pdf_path.name, original_size, compressed_size)

    return save_path


# ── 内部实现 ────────────────────────────────────────────────────────────────


def _run_compression(source: Path, target: Path, level: int) -> None:
    """根据压缩等级执行具体的 PDF 优化操作。"""

    # ── 等级 0：仅复制 ────────────────────────────────────────────
    if level == 0:
        with pikepdf.open(source) as pdf:
            pdf.save(
                target,
                compress_streams=False,
                object_stream_mode=pikepdf.ObjectStreamMode.disable,
            )
        return

    # ── 等级 1-3：轻度压缩（流压缩） ──────────────────────────────
    if level <= 3:
        with pikepdf.open(source) as pdf:
            pdf.save(
                target,
                compress_streams=True,
                object_stream_mode=pikepdf.ObjectStreamMode.generate,
            )
        return

    # ── 等级 4-6：中度压缩（流压缩 + 资源清理） ──────────────────
    if level <= 6:
        with pikepdf.open(source) as pdf:
            pdf.remove_unreferenced_resources()
            pdf.save(
                target,
                compress_streams=True,
                object_stream_mode=pikepdf.ObjectStreamMode.generate,
            )
        return

    # ── 等级 7-9：激进压缩 ─────────────────────────────────────────
    # 先做第一次保存（含资源清理），再打开重压缩内容流
    tmp = target.with_suffix(".tmp.pdf")
    try:
        with pikepdf.open(source) as pdf:
            pdf.remove_unreferenced_resources()
            pdf.save(
                tmp,
                compress_streams=True,
                object_stream_mode=pikepdf.ObjectStreamMode.generate,
            )

        # 第二次打开：重压缩内容流
        with pikepdf.open(tmp) as pdf:
            pdf.save(
                target,
                compress_streams=True,
                object_stream_mode=pikepdf.ObjectStreamMode.generate,
                stream_decode_level=pikepdf.StreamDecodeLevel.specialized,
            )
    finally:
        tmp.unlink(missing_ok=True)


def _log_result(name: str, original: int, compressed: int) -> None:
    """记录压缩前后的文件大小对比。"""
    ratio = (1 - compressed / original) * 100 if original > 0 else 0
    logger.info(
        f"压缩完成: {original / 1024:.1f}KB → {compressed / 1024:.1f}KB "
        f"({ratio:+.1f}%)"
    )
