"""
测试 core/pdf/compress.py — 全维度参数化 PDF 压缩
"""
from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter

from core.pdf.compress import (
    CompressOptions,
    PRESETS,
    PRESET_DESCRIPTIONS,
    compress,
    compress_with_options,
    resolve_preset,
    merge_options,
)


# =============================================================================
# 夹具
# =============================================================================

@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    """生成一个 3 页空白测试 PDF"""
    pdf_path = tmp_path / "sample.pdf"
    writer = PdfWriter()
    for _ in range(3):
        writer.add_blank_page(612, 792)
    with open(pdf_path, "wb") as f:
        writer.write(f)
    return pdf_path


@pytest.fixture
def pdf_with_jpeg(tmp_path: Path) -> Path:
    """生成一个含 JPEG 图像的 PDF（3 页，每页一张大图）"""
    from io import BytesIO
    from PIL import Image
    import img2pdf

    pdf_path = tmp_path / "with_jpeg.pdf"
    images = []
    for i in range(3):
        img = Image.new("RGB", (1200, 800), (i * 50 + 30, 100, 200))
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=95)
        buf.seek(0)
        images.append(buf)
    pdf_bytes = img2pdf.convert(images)
    pdf_path.write_bytes(pdf_bytes)
    return pdf_path


# =============================================================================
# 测试 CompressOptions / PRESETS / resolve / merge
# =============================================================================

class TestCompressOptions:
    def test_defaults(self):
        opts = CompressOptions()
        assert opts.stream_level == 2
        assert opts.image_quality is None
        assert opts.convert_all_to_jpg is False
        assert opts.max_dimension is None
        assert opts.remove_metadata is False

    def test_presets_defined(self):
        """四种预设都应定义且参数合理"""
        assert set(PRESETS.keys()) == {"mild", "moderate", "aggressive", "extreme"}
        for name, opts in PRESETS.items():
            assert 0 <= opts.stream_level <= 3
            if opts.image_quality is not None:
                assert 0 <= opts.image_quality <= 100

    def test_mild_preset(self):
        opts = PRESETS["mild"]
        assert opts.remove_metadata is False
        assert opts.convert_all_to_jpg is False
        assert opts.max_dimension is None

    def test_extreme_preset(self):
        opts = PRESETS["extreme"]
        assert opts.remove_metadata is True
        assert opts.convert_all_to_jpg is True
        assert opts.max_dimension == 800

    def test_preset_descriptions(self):
        """每个预设都有友好的面向用户的描述"""
        for name, desc in PRESET_DESCRIPTIONS.items():
            assert "label" in desc
            assert "icon" in desc
            assert "desc" in desc
            assert "warning" in desc

    def test_resolve_preset_known(self):
        for name in PRESETS:
            opts = resolve_preset(name)
            assert opts == PRESETS[name]

    def test_resolve_preset_unknown_falls_back(self):
        opts = resolve_preset("nonexistent")
        assert opts == PRESETS["moderate"]

    def test_resolve_preset_case_insensitive(self):
        assert resolve_preset("Mild") == PRESETS["mild"]

    def test_merge_options_no_overrides(self):
        merged = merge_options(PRESETS["aggressive"], {})
        assert merged == PRESETS["aggressive"]

    def test_merge_options_partial(self):
        merged = merge_options(PRESETS["moderate"], {"image_quality": 80})
        assert merged.image_quality == 80
        # 未覆盖的字段保持预设值
        assert merged.stream_level == PRESETS["moderate"].stream_level
        assert merged.remove_metadata == PRESETS["moderate"].remove_metadata

    def test_merge_options_ignores_unknown_keys(self):
        merged = merge_options(PRESETS["mild"], {"unknown_key": 999})
        assert merged == PRESETS["mild"]

    def test_merge_options_all_overrides(self):
        overrides = {
            "stream_level": 3,
            "image_quality": 50,
            "convert_all_to_jpg": True,
            "max_dimension": 1200,
            "remove_metadata": True,
        }
        merged = merge_options(PRESETS["mild"], overrides)
        assert merged.stream_level == 3
        assert merged.image_quality == 50
        assert merged.convert_all_to_jpg is True
        assert merged.max_dimension == 1200
        assert merged.remove_metadata is True


# =============================================================================
# 测试 compress / compress_with_options — 基础功能
# =============================================================================

class TestCompress:
    def test_basic_compression(
        self, sample_pdf: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """基本压缩流程"""
        monkeypatch.setattr("core.pdf.compress.OUTPUT_DIR", tmp_path)
        result = compress(str(sample_pdf), "compressed", "medium")
        assert result.exists()
        assert result.suffix == ".pdf"
        reader = PdfReader(result)
        assert len(reader.pages) == 3

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError, match="PDF 文件不存在"):
            compress("/nonexistent/path.pdf", "test", "medium")

    def test_pages_preserved(
        self, sample_pdf: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        monkeypatch.setattr("core.pdf.compress.OUTPUT_DIR", tmp_path)
        result = compress(str(sample_pdf), "pages_test", 5)
        assert len(PdfReader(result).pages) == len(PdfReader(sample_pdf).pages)

    def test_all_old_levels_produce_valid_pdf(
        self, sample_pdf: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """旧 API 所有等级（0-9）均应生成合法 PDF"""
        monkeypatch.setattr("core.pdf.compress.OUTPUT_DIR", tmp_path)
        for level in range(10):
            result = compress(str(sample_pdf), f"level_{level}", level)
            assert result.exists()
            reader = PdfReader(result)
            assert len(reader.pages) == 3

    def test_string_levels_backward_compat(
        self, sample_pdf: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """旧 API 字符串等级兼容"""
        monkeypatch.setattr("core.pdf.compress.OUTPUT_DIR", tmp_path)
        for level_str in ("low", "medium", "high"):
            result = compress(str(sample_pdf), f"str_{level_str}", level_str)
            assert result.exists()
            reader = PdfReader(result)
            assert len(reader.pages) == 3

    def test_output_directory_created(
        self, sample_pdf: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        monkeypatch.setattr("core.pdf.compress.OUTPUT_DIR", tmp_path)
        output_root = tmp_path / "auto_created"
        monkeypatch.setattr("core.pdf.compress.OUTPUT_DIR", output_root)
        assert not output_root.exists()
        result = compress(str(sample_pdf), "auto_dir", "medium")
        assert result.exists()
        assert output_root.exists()

    def test_filename_collision(
        self, sample_pdf: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        monkeypatch.setattr("core.pdf.compress.OUTPUT_DIR", tmp_path)
        r1 = compress(str(sample_pdf), "collision_test", "medium")
        r2 = compress(str(sample_pdf), "collision_test", "medium")
        assert r2.name != r1.name

    def test_output_dir_structure(
        self, sample_pdf: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        monkeypatch.setattr("core.pdf.compress.OUTPUT_DIR", tmp_path)
        result = compress(str(sample_pdf), "check_dir", "medium")
        assert result.parent == tmp_path / "PDF" / "压缩"


# =============================================================================
# 测试 compress_with_options — 新 API
# =============================================================================

class TestCompressWithOptions:
    def test_each_preset(
        self, sample_pdf: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """四种预设均应正常工作"""
        monkeypatch.setattr("core.pdf.compress.OUTPUT_DIR", tmp_path)
        for name in PRESETS:
            opts = resolve_preset(name)
            result = compress_with_options(str(sample_pdf), f"preset_{name}", opts)
            assert result.exists()
            assert len(PdfReader(result).pages) == 3

    def test_remove_metadata(
        self, sample_pdf: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """移除元数据选项"""
        monkeypatch.setattr("core.pdf.compress.OUTPUT_DIR", tmp_path)
        opts = CompressOptions(stream_level=1, remove_metadata=True)
        result = compress_with_options(str(sample_pdf), "no_meta", opts)
        assert result.exists()

        import pikepdf
        with pikepdf.open(result) as pdf:
            assert len(list(pdf.docinfo.keys())) == 0

    def test_stream_level_0(
        self, sample_pdf: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """stream_level=0 且无图像处理时应为纯复制"""
        monkeypatch.setattr("core.pdf.compress.OUTPUT_DIR", tmp_path)
        opts = CompressOptions(stream_level=0)
        result = compress_with_options(str(sample_pdf), "no_stream", opts)
        assert result.exists()
        assert len(PdfReader(result).pages) == 3

    def test_stream_level_3(
        self, sample_pdf: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """stream_level=3 最高压缩"""
        monkeypatch.setattr("core.pdf.compress.OUTPUT_DIR", tmp_path)
        opts = CompressOptions(stream_level=3, image_quality=95)
        result = compress_with_options(str(sample_pdf), "max_stream", opts)
        assert result.exists()
        assert len(PdfReader(result).pages) == 3

    def test_convert_all_to_jpg(
        self, pdf_with_jpeg: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """全转 JPG 选项应生成合法输出"""
        monkeypatch.setattr("core.pdf.compress.OUTPUT_DIR", tmp_path)
        opts = CompressOptions(
            stream_level=1, image_quality=50, convert_all_to_jpg=True
        )
        result = compress_with_options(str(pdf_with_jpeg), "all_jpg", opts)
        assert result.exists()
        assert len(PdfReader(result).pages) == 3

    def test_downsample(
        self, pdf_with_jpeg: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """降采样选项应生成更小的文件"""
        monkeypatch.setattr("core.pdf.compress.OUTPUT_DIR", tmp_path)

        opts_no = CompressOptions(
            stream_level=1, image_quality=95, convert_all_to_jpg=False,
            max_dimension=None,
        )
        opts_yes = CompressOptions(
            stream_level=1, image_quality=95, convert_all_to_jpg=True,
            max_dimension=400,
        )

        r_no = compress_with_options(str(pdf_with_jpeg), "ds_no", opts_no)
        r_yes = compress_with_options(str(pdf_with_jpeg), "ds_yes", opts_yes)

        # 降采样到 400px 应显著更小
        assert r_yes.stat().st_size < r_no.stat().st_size * 0.7

    def test_jpeg_recompression_high_smaller(
        self, pdf_with_jpeg: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """high 预设应比 mild 预设显著小（含图像的 PDF）"""
        monkeypatch.setattr("core.pdf.compress.OUTPUT_DIR", tmp_path)

        r_mild = compress_with_options(
            str(pdf_with_jpeg), "jpg_mild", PRESETS["mild"]
        )
        r_high = compress_with_options(
            str(pdf_with_jpeg), "jpg_high", PRESETS["aggressive"]
        )

        ratio = r_high.stat().st_size / r_mild.stat().st_size
        assert ratio < 0.80, (
            f"aggressive({r_high.stat().st_size}B) 应小于 "
            f"mild({r_mild.stat().st_size}B), 实际 ratio={ratio:.2%}"
        )

    def test_output_still_valid(
        self, pdf_with_jpeg: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """含图像的 PDF 压缩后仍是合法可读的"""
        monkeypatch.setattr("core.pdf.compress.OUTPUT_DIR", tmp_path)
        import pikepdf as pk

        opts = CompressOptions(
            stream_level=3, image_quality=40, convert_all_to_jpg=True,
            max_dimension=800, remove_metadata=True,
        )
        result = compress_with_options(str(pdf_with_jpeg), "valid_test", opts)
        assert result.exists()

        with pk.open(result) as pdf:
            assert len(pdf.pages) == 3
            for page in pdf.pages:
                xobj = getattr(page.Resources, "XObject", None)
                if xobj:
                    for name in xobj.keys():
                        obj = xobj[name]
                        if obj.get("/Subtype") == pk.Name.Image:
                            assert obj.get("/Filter") == pk.Name.DCTDecode
                            raw = obj.read_raw_bytes()
                            assert len(raw) > 0
