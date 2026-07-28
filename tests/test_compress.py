"""
测试 core/pdf/compress.py — PDF 压缩功能（基于 pikepdf，零外部依赖）
"""
from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter

from core.pdf.compress import compress, _resolve_compression_level


# =============================================================================
# 夹具：生成一个简单的测试 PDF
# =============================================================================
@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    """生成一个 3 页的测试 PDF"""
    pdf_path = tmp_path / "sample.pdf"
    writer = PdfWriter()
    for _ in range(3):
        writer.add_blank_page(612, 792)
    with open(pdf_path, "wb") as f:
        writer.write(f)
    return pdf_path


# =============================================================================
# 测试 _resolve_compression_level
# =============================================================================
class TestResolveCompressionLevel:
    def test_low_string(self):
        assert _resolve_compression_level("low") == 1

    def test_medium_string(self):
        assert _resolve_compression_level("medium") == 5

    def test_high_string(self):
        assert _resolve_compression_level("high") == 9

    def test_case_insensitive(self):
        assert _resolve_compression_level("Low") == 1
        assert _resolve_compression_level("MEDIUM") == 5

    def test_integer_zero(self):
        assert _resolve_compression_level(0) == 0

    def test_integer_mid(self):
        assert _resolve_compression_level(5) == 5

    def test_integer_max(self):
        assert _resolve_compression_level(9) == 9

    def test_negative_clamped(self):
        assert _resolve_compression_level(-1) == 0

    def test_overflow_clamped(self):
        assert _resolve_compression_level(99) == 9

    def test_unknown_string_defaults_to_medium(self):
        assert _resolve_compression_level("super") == 5


# =============================================================================
# 测试 compress 函数 — 全部零外部依赖
# =============================================================================
class TestCompress:
    def test_basic_compression(
        self, sample_pdf: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """基本压缩流程：输入 PDF → 输出压缩后的 PDF"""
        monkeypatch.setattr("core.pdf.compress.OUTPUT_DIR", tmp_path)

        result = compress(str(sample_pdf), "compressed", "medium")

        assert result.exists()
        assert result.suffix == ".pdf"
        assert "compressed" in result.name

        # 验证输出文件是合法的 PDF
        reader = PdfReader(result)
        assert len(reader.pages) == 3

    def test_file_not_found(self):
        """源文件不存在时应抛出 FileNotFoundError"""
        with pytest.raises(FileNotFoundError, match="PDF 文件不存在"):
            compress("/nonexistent/path.pdf", "test", "medium")

    def test_pages_preserved(
        self, sample_pdf: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """压缩后页数应与原 PDF 一致"""
        monkeypatch.setattr("core.pdf.compress.OUTPUT_DIR", tmp_path)

        result = compress(str(sample_pdf), "pages_test", 5)

        original_reader = PdfReader(sample_pdf)
        compressed_reader = PdfReader(result)
        assert len(compressed_reader.pages) == len(original_reader.pages)

    def test_all_levels_produce_valid_pdf(
        self, sample_pdf: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """所有等级（0-9）都应生成合法的 PDF"""
        monkeypatch.setattr("core.pdf.compress.OUTPUT_DIR", tmp_path)

        for level in range(10):
            name = f"level_{level}"
            result = compress(str(sample_pdf), name, level)
            assert result.exists(), f"等级 {level} 未能生成文件"
            reader = PdfReader(result)
            assert len(reader.pages) == 3, f"等级 {level} 页数不一致"

    def test_level_0_is_copy(
        self, sample_pdf: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """等级 0 应生成与原文件大小相同的有效 PDF"""
        monkeypatch.setattr("core.pdf.compress.OUTPUT_DIR", tmp_path)

        result = compress(str(sample_pdf), "copy_test", 0)
        assert result.exists()
        reader = PdfReader(result)
        assert len(reader.pages) == 3

    def test_output_directory_created(
        self, sample_pdf: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """输出目录不存在时应自动创建"""
        output_root = tmp_path / "auto_created"
        monkeypatch.setattr("core.pdf.compress.OUTPUT_DIR", output_root)

        assert not output_root.exists()
        result = compress(str(sample_pdf), "auto_dir", "medium")
        assert result.exists()
        assert output_root.exists()

    def test_filename_collision(
        self, sample_pdf: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """同名文件已存在时，应使用带时间戳的新文件名"""
        monkeypatch.setattr("core.pdf.compress.OUTPUT_DIR", tmp_path)

        result1 = compress(str(sample_pdf), "collision_test", "medium")
        assert result1.exists()

        result2 = compress(str(sample_pdf), "collision_test", "medium")
        assert result2.exists()
        assert result2.name != result1.name

    def test_output_in_pdf_compressed_dir(
        self, sample_pdf: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """输出文件应位于 OUTPUT_DIR/PDF/压缩/ 目录下"""
        monkeypatch.setattr("core.pdf.compress.OUTPUT_DIR", tmp_path)

        result = compress(str(sample_pdf), "check_dir", "medium")

        expected_dir = tmp_path / "PDF" / "压缩"
        assert result.parent == expected_dir
        assert expected_dir.exists()

    def test_string_levels(
        self, sample_pdf: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """字符串等级参数应正常工作"""
        monkeypatch.setattr("core.pdf.compress.OUTPUT_DIR", tmp_path)

        for level_str in ("low", "medium", "high"):
            result = compress(str(sample_pdf), f"str_{level_str}", level_str)
            assert result.exists(), f"字符串等级 '{level_str}' 失败"
            reader = PdfReader(result)
            assert len(reader.pages) == 3


# =============================================================================
# 测试 JPEG 图像重压缩
# =============================================================================
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


class TestJpegRecompression:
    def test_high_smaller_than_low(
        self, pdf_with_jpeg: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """含图像的 PDF：high 等级应比 low 等级显著更小"""
        monkeypatch.setattr("core.pdf.compress.OUTPUT_DIR", tmp_path)

        result_low = compress(str(pdf_with_jpeg), "jpg_low", "low")
        result_high = compress(str(pdf_with_jpeg), "jpg_high", "high")

        size_low = result_low.stat().st_size
        size_high = result_high.stat().st_size

        # high 必须比 low 至少小 10%
        ratio = size_high / size_low
        assert ratio < 0.90, (
            f"high({size_high}B) 应显著小于 low({size_low}B), "
            f"实际 ratio={ratio:.2%}"
        )

    def test_output_still_valid(
        self, pdf_with_jpeg: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """含图像的 PDF 压缩后仍是合法且可读的 PDF"""
        monkeypatch.setattr("core.pdf.compress.OUTPUT_DIR", tmp_path)

        result = compress(str(pdf_with_jpeg), "jpg_valid", "high")
        assert result.exists()

        # 用 pikepdf 重新打开验证
        import pikepdf as pk
        with pk.open(result) as pdf:
            assert len(pdf.pages) == 3
            for page in pdf.pages:
                xobj = getattr(page.Resources, "XObject", None)
                if xobj:
                    for name in xobj.keys():
                        obj = xobj[name]
                        if obj.get("/Subtype") == pk.Name.Image:
                            # 图像应有正确的 /Filter
                            assert obj.get("/Filter") == pk.Name.DCTDecode, (
                                f"{name} 缺少 DCTDecode 过滤器"
                            )
                            # 应能读出像素数据
                            raw = obj.read_raw_bytes()
                            assert len(raw) > 0
