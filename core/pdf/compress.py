"""
PDF 压缩 — 基于 pikepdf 的无损/有损优化。

零外部程序依赖：pikepdf 的 wheel 已内嵌编译好的 qpdf 引擎，开箱即用。
对于含 JPEG 图像的 PDF，中/高等级会自动降品质重压缩，显著减小体积。
"""
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Union

import pikepdf
from loguru import logger
from PIL import Image

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


# ── 图像重压缩 ──────────────────────────────────────────────────────────────


def _recompress_page_images(
    page: pikepdf.Page, jpg_quality: int
) -> None:
    """
    对页面中 DCTDecode（JPEG）图像进行降品质重压缩。
    跳过小图像（< 2000 字节，避免 overhead 超过收益）。
    """
    xobjects = getattr(page.Resources, "XObject", None)
    if xobjects is None:
        return

    for name in list(xobjects.keys()):
        obj = xobjects[name]
        if obj.get("/Subtype") != pikepdf.Name.Image:
            continue

        # 只处理 DCTDecode (JPEG) 图像
        filt = obj.get("/Filter")
        if filt != pikepdf.Name.DCTDecode:
            continue

        try:
            raw = obj.read_raw_bytes()
            if len(raw) < 2000:  # 小图像跳过
                continue

            pil_img = Image.open(BytesIO(raw))
            if pil_img.mode in ("RGBA", "P"):
                pil_img = pil_img.convert("RGB")

            buf = BytesIO()
            pil_img.save(
                buf, format="JPEG", quality=jpg_quality, optimize=True
            )
            new_data = buf.getvalue()

            if new_data and len(new_data) < len(raw):
                obj.write(new_data, filter=pikepdf.Name.DCTDecode)
        except Exception as exc:
            logger.debug(f"跳过图像 '{name}' 重压缩: {exc}")


# ── 主函数 ──────────────────────────────────────────────────────────────────


def compress(
    pdf_path: str,
    file_name: str,
    compression_level: Union[int, str] = 5,
) -> Path:
    """
    压缩 PDF 文件。

    使用 pikepdf（qpdf 引擎）进行流压缩和图像优化。
    纯 Python 实现，不依赖任何外部可执行程序。

    等级:
      0      — 仅复制
      low    — FlateDecode 流压缩（无损）
      medium — 流压缩 + JPEG 图像重压缩 quality=65 + 资源清理
      high   — 流压缩 + JPEG 重压缩 quality=35/25/15 + 资源清理

    Args:
        pdf_path: 源 PDF 文件路径
        file_name: 输出文件名（不含扩展名）
        compression_level: 压缩等级

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

    # ── 等级 1-3：轻度（无损流压缩） ──────────────────────────────
    if level <= 3:
        with pikepdf.open(source) as pdf:
            pdf.save(
                target,
                compress_streams=True,
                object_stream_mode=pikepdf.ObjectStreamMode.generate,
            )
        return

    # ── 等级 4-6：中度（流压缩 + JPEG 重压缩 quality=65 + 资源清理）
    if level <= 6:
        _compress_with_images(source, target, jpg_quality=65)
        return

    # ── 等级 7-9：激进（流压缩 + JPEG 重压缩 + 资源清理 + 内容流重压缩）
    #    等级越高 JPEG 质量越低
    quality_map = {7: 50, 8: 35, 9: 20}
    _compress_with_images(source, target, jpg_quality=quality_map[level])


def _compress_with_images(
    source: Path, target: Path, jpg_quality: int
) -> None:
    """
    执行含图像重压缩的优化流程。

    流程：
      1. 打开源文件
      2. 遍历每页，重压缩 JPEG 图像
      3. 清理未引用资源
      4. 保存（compress_streams 压缩非图像流）
      5. 第二次打开，重压缩内容流（recompress_flate）
    """
    tmp = target.with_suffix(".tmp.pdf")
    try:
        # 第一遍：图像重压缩 + 资源清理
        with pikepdf.open(source) as pdf:
            for page in pdf.pages:
                _recompress_page_images(page, jpg_quality)
            pdf.remove_unreferenced_resources()
            pdf.save(
                tmp,
                compress_streams=True,
                object_stream_mode=pikepdf.ObjectStreamMode.generate,
            )

        # 第二遍：内容流重压缩
        with pikepdf.open(tmp) as pdf:
            pdf.save(
                target,
                compress_streams=True,
                object_stream_mode=pikepdf.ObjectStreamMode.generate,
                recompress_flate=True,
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
