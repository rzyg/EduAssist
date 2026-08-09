"""
PDF 压缩 — 基于 pikepdf 的全维度参数化压缩。

零外部程序依赖。支持四种预设方案 + 高级选项微调。

预设方案:
  mild       — 质量优先，略微减体积
  moderate   — 平衡质量和体积，适合日常使用
  aggressive — 大幅压缩，适合邮件发送
  extreme    — 极致压缩，适合存储空间极度紧张
"""
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Optional, Union

import pikepdf
from loguru import logger
from PIL import Image

from core.config import OUTPUT_DIR


# =============================================================================
# 压缩选项定义
# =============================================================================


@dataclass
class CompressOptions:
    """压缩全维度参数。"""

    # 流压缩级别: 0=关闭, 1=基本, 2=中等(含对象流), 3=最高(含recompress_flate)
    stream_level: int = 2
    # JPEG 重压缩质量 0-100; None 表示不重压缩图像
    image_quality: Optional[int] = None
    # 全转 JPG: 将非 JPEG 图像也转为 JPEG（透明背景可能变白）
    convert_all_to_jpg: bool = False
    # 降采样: 限制图像最长边像素数; None 表示不限制
    max_dimension: Optional[int] = None
    # 移除文档元数据（作者、标题等）
    remove_metadata: bool = False


# ── 四种预设方案 ─────────────────────────────────────────────────────────────

PRESETS: dict[str, CompressOptions] = {
    "mild": CompressOptions(
        stream_level=2,
        image_quality=None,
        convert_all_to_jpg=False,
        max_dimension=None,
        remove_metadata=False,
    ),
    "moderate": CompressOptions(
        stream_level=3,
        image_quality=70,
        convert_all_to_jpg=False,
        max_dimension=None,
        remove_metadata=True,
    ),
    "aggressive": CompressOptions(
        stream_level=3,
        image_quality=50,
        convert_all_to_jpg=True,
        max_dimension=1600,
        remove_metadata=True,
    ),
    "extreme": CompressOptions(
        stream_level=3,
        image_quality=30,
        convert_all_to_jpg=True,
        max_dimension=800,
        remove_metadata=True,
    ),
}

PRESET_DESCRIPTIONS: dict[str, dict] = {
    "mild": {
        "label": "轻度",
        "icon": "📄",
        "desc": "质量优先，略微减小体积",
        "warning": "",
    },
    "moderate": {
        "label": "中度",
        "icon": "⚖️",
        "desc": "平衡质量和体积，适合日常使用",
        "warning": "",
    },
    "aggressive": {
        "label": "重度",
        "icon": "🗜️",
        "desc": "大幅压缩，适合邮件发送",
        "warning": "⚠️ 图像质量会有可见损失",
    },
    "extreme": {
        "label": "极度",
        "icon": "⚡",
        "desc": "极致压缩，适合存储空间极度紧张",
        "warning": "⚠️⚠️ 图像质量明显下降，仅限空间紧张时使用",
    },
}


def resolve_preset(preset: str) -> CompressOptions:
    """按名称获取预设方案，未知名称回退到 moderate。"""
    if preset.lower() in PRESETS:
        return PRESETS[preset.lower()]
    logger.warning(f"未知预设 '{preset}'，使用默认 moderate")
    return PRESETS["moderate"]


def merge_options(base: CompressOptions, overrides: dict) -> CompressOptions:
    """用用户高级选项覆盖预设值。"""
    allowed = {"stream_level", "image_quality", "convert_all_to_jpg",
               "max_dimension", "remove_metadata"}
    kwargs = {k: v for k, v in overrides.items() if k in allowed}
    return CompressOptions(
        stream_level=kwargs.get("stream_level", base.stream_level),
        image_quality=kwargs.get("image_quality", base.image_quality),
        convert_all_to_jpg=kwargs.get("convert_all_to_jpg", base.convert_all_to_jpg),
        max_dimension=kwargs.get("max_dimension", base.max_dimension),
        remove_metadata=kwargs.get("remove_metadata", base.remove_metadata),
    )


# =============================================================================
# 路径工具
# =============================================================================


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


# =============================================================================
# 图像处理
# =============================================================================


def _image_to_jpeg(
    pil_img: Image.Image, quality: int, max_dim: Optional[int] = None
) -> tuple[bytes, int, int]:
    """将 PIL 图像转 JPEG 字节，可选降采样。

    Returns:
        (jpeg_bytes, width, height)
    """
    if pil_img.mode in ("RGBA", "P"):
        pil_img = pil_img.convert("RGB")

    # 降采样
    if max_dim is not None:
        w, h = pil_img.size
        if max(w, h) > max_dim:
            ratio = max_dim / max(w, h)
            new_size = (int(w * ratio), int(h * ratio))
            pil_img = pil_img.resize(new_size, Image.LANCZOS)

    width, height = pil_img.size
    buf = BytesIO()
    pil_img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue(), width, height


def _recompress_xobject_image(
    obj: pikepdf.Object,
    quality: int,
    convert_all: bool,
    max_dim: Optional[int],
) -> None:
    """重压缩单个图像 XObject，支持 JPEG 和非 JPEG。

    降采样后同步更新 PDF XObject 的 /Width /Height，
    避免 PDF 阅读器用旧尺寸解码导致乱码。
    """
    filt = obj.get("/Filter")
    is_jpeg = filt == pikepdf.Name.DCTDecode

    # 非 JPEG 且没开全转 JPG → 跳过
    if not is_jpeg and not convert_all:
        return

    try:
        raw = obj.read_raw_bytes()
        if len(raw) < 2000:
            return

        pil_img = Image.open(BytesIO(raw))

        # 解码后即获得实际像素尺寸
        orig_w, orig_h = pil_img.size

        # 判断是否需要降采样
        need_downsample = (
            max_dim is not None and max(orig_w, orig_h) > max_dim
        )

        # 如果是已损 JPEG 且无需降采样且不转 JPG，走原 JPEG 重压缩路径
        if is_jpeg and not convert_all and not need_downsample:
            if pil_img.mode in ("RGBA", "P"):
                pil_img = pil_img.convert("RGB")
            buf = BytesIO()
            pil_img.save(buf, format="JPEG", quality=quality, optimize=True)
            new_data = buf.getvalue()
            new_w, new_h = orig_w, orig_h
        else:
            # 全转 JPG 或需降采样
            new_data, new_w, new_h = _image_to_jpeg(pil_img, quality, max_dim)

        if new_data and len(new_data) < len(raw):
            obj.write(new_data, filter=pikepdf.Name.DCTDecode)
            # 同步更新 PDF XObject 尺寸
            if new_w != orig_w or new_h != orig_h:
                obj.Width = new_w
                obj.Height = new_h
    except Exception as exc:
        logger.warning(f"跳过图像重压缩: {exc}")


def _process_page_images(
    page: pikepdf.Page,
    quality: int,
    convert_all: bool,
    max_dim: Optional[int],
) -> None:
    """处理单页中所有图像。"""
    xobjects = getattr(page.Resources, "XObject", None)
    if xobjects is None:
        return

    for name in list(xobjects.keys()):
        obj = xobjects[name]
        if obj.get("/Subtype") != pikepdf.Name.Image:
            continue
        _recompress_xobject_image(obj, quality, convert_all, max_dim)


# =============================================================================
# 主入口（新 API）
# =============================================================================


def compress_with_options(
    pdf_path: str,
    file_name: str,
    options: CompressOptions,
) -> Path:
    """
    按 CompressOptions 参数压缩 PDF。

    Args:
        pdf_path: 源 PDF 文件路径
        file_name: 输出文件名（不含扩展名）
        options: 压缩全维度参数

    Returns:
        压缩后的文件路径
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")

    original_size = pdf_path.stat().st_size
    logger.info(
        f"开始压缩: {pdf_path.name} (大小={original_size / 1024:.1f}KB, "
        f"流级别={options.stream_level}, 图片质量={options.image_quality})"
    )

    save_path = _compressed_pdf_save_path(file_name)
    _run_compression(pdf_path, save_path, options)

    compressed_size = save_path.stat().st_size
    _log_result(pdf_path.name, original_size, compressed_size)
    return save_path


# =============================================================================
# 兼容旧 API（compress(level="low/medium/high") → 映射到预设）
# =============================================================================

_OLD_LEVEL_TO_PRESET = {
    0: "mild",
    1: "mild",
    2: "mild",
    3: "mild",
    4: "moderate",
    5: "moderate",
    6: "moderate",
    7: "aggressive",
    8: "aggressive",
    9: "extreme",
}


def compress(
    pdf_path: str,
    file_name: str,
    compression_level: Union[int, str] = 5,
) -> Path:
    """兼容旧 API：将 level/low/medium/high 映射到预设后调用 compress_with_options。"""
    if isinstance(compression_level, str):
        preset_map = {"low": "mild", "medium": "moderate", "high": "aggressive"}
        preset = preset_map.get(compression_level.lower(), "moderate")
        return compress_with_options(pdf_path, file_name, resolve_preset(preset))

    level = compression_level
    if level < 0:
        level = 0
    if level > 9:
        level = 9
    preset = _OLD_LEVEL_TO_PRESET.get(level, "moderate")
    return compress_with_options(pdf_path, file_name, resolve_preset(preset))


# =============================================================================
# 内部实现
# =============================================================================


def _run_compression(source: Path, target: Path, opts: CompressOptions) -> None:
    """根据 CompressOptions 执行压缩。"""
    # ── 等级 0：流不压缩、不处理图像 ──────────────────────────────
    if opts.stream_level == 0 and opts.image_quality is None:
        with pikepdf.open(source) as pdf:
            _remove_metadata_if_needed(pdf, opts.remove_metadata)
            pdf.save(
                target,
                compress_streams=False,
                object_stream_mode=pikepdf.ObjectStreamMode.disable,
            )
        return

    has_image_work = (
        opts.image_quality is not None
        or opts.convert_all_to_jpg
        or opts.max_dimension is not None
    )

    if not has_image_work:
        # ── 纯流压缩，无图像处理 ────────────────────────────────
        with pikepdf.open(source) as pdf:
            _remove_metadata_if_needed(pdf, opts.remove_metadata)
            pdf.save(
                target,
                compress_streams=opts.stream_level >= 1,
                object_stream_mode=(
                    pikepdf.ObjectStreamMode.generate
                    if opts.stream_level >= 2
                    else pikepdf.ObjectStreamMode.disable
                ),
                recompress_flate=opts.stream_level >= 3,
            )
        return

    # ── 含图像处理的流程 ──────────────────────────────────────────
    tmp = target.with_suffix(".tmp.pdf")
    try:
        # 第一遍：图像处理 + 资源清理
        with pikepdf.open(source) as pdf:
            quality = opts.image_quality if opts.image_quality is not None else 95
            for page in pdf.pages:
                _process_page_images(
                    page, quality, opts.convert_all_to_jpg, opts.max_dimension
                )
            pdf.remove_unreferenced_resources()
            _remove_metadata_if_needed(pdf, opts.remove_metadata)
            pdf.save(
                tmp,
                compress_streams=opts.stream_level >= 1,
                object_stream_mode=(
                    pikepdf.ObjectStreamMode.generate
                    if opts.stream_level >= 2
                    else pikepdf.ObjectStreamMode.disable
                ),
            )

        # 第二遍：内容流重压缩
        with pikepdf.open(tmp) as pdf:
            pdf.save(
                target,
                compress_streams=True,
                object_stream_mode=pikepdf.ObjectStreamMode.generate,
                recompress_flate=opts.stream_level >= 3,
            )
    finally:
        tmp.unlink(missing_ok=True)


def _remove_metadata_if_needed(pdf: pikepdf.Pdf, remove: bool) -> None:
    """可选：清除文档元数据。"""
    if not remove:
        return
    # 清除文档信息字典
    for k in list(pdf.docinfo.keys()):
        del pdf.docinfo[k]
    # 清除 Metadata 流
    try:
        del pdf.Root.Metadata
    except KeyError:
        pass


def _log_result(name: str, original: int, compressed: int) -> None:
    """记录压缩前后的文件大小对比。"""
    ratio = (1 - compressed / original) * 100 if original > 0 else 0
    logger.info(
        f"压缩完成: {original / 1024:.1f}KB → {compressed / 1024:.1f}KB "
        f"({ratio:+.1f}%)"
    )
