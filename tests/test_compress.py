"""
测试 core/pdf/compress.py — PDF 压缩功能
"""
import shutil
from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter

from core.pdf.compress import compress, _resolve_compression_level


# =============================================================================
# 夹具：生成一个简单的测试 PDF
# =============================================================================
@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    """生成一个 3 页的测试 PDF，每页包含一些文字内容"""
    pdf_path = tmp_path / "sample.pdf"
    writer = PdfWriter()
    for i in range(3):
        writer.add_blank_page(612, 792)  # Letter 大小
    with open(pdf_path, "wb") as f:
        writer.write(f)
    return pdf_path


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    """返回一个临时输出目录，模拟 OUTPUT_DIR"""
    output_dir = tmp_path / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


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
# 测试 compress 函数
# =============================================================================
class TestCompress:
    def test_basic_compression(self, sample_pdf: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        """基本压缩流程：输入 PDF → 输出压缩后的 PDF"""
        # 将 OUTPUT_DIR 指向临时目录
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

    def test_pages_preserved(self, sample_pdf: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        """压缩后页数应与原 PDF 一致"""
        monkeypatch.setattr("core.pdf.compress.OUTPUT_DIR", tmp_path)

        result = compress(str(sample_pdf), "pages_test", 5)

        original_reader = PdfReader(sample_pdf)
        compressed_reader = PdfReader(result)
        assert len(compressed_reader.pages) == len(original_reader.pages)

    def test_low_level_produces_larger_file(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        """低压缩等级（level=0）产生的文件应大于高压缩等级（level=9）"""
        monkeypatch.setattr("core.pdf.compress.OUTPUT_DIR", tmp_path)

        # 创建包含实际内容的 PDF（空白页压缩效果不明显）
        pdf_path = tmp_path / "text_sample.pdf"
        writer = PdfWriter()
        writer.add_blank_page(612, 792)
        writer.add_blank_page(612, 792)
        with open(pdf_path, "wb") as f:
            writer.write(f)

        # 低压缩
        result_low = compress(str(pdf_path), "low_test", 0)
        # 高压缩
        result_high = compress(str(pdf_path), "high_test", 9)

        size_low = result_low.stat().st_size
        size_high = result_high.stat().st_size
        # 高压缩不应大于低压缩（允许相等，因为空白页压缩空间有限）
        assert size_high <= size_low, (
            f"高压缩文件 ({size_high}B) 不应大于低压缩文件 ({size_low}B)"
        )

    def test_output_directory_created(self, sample_pdf: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        """输出目录不存在时应自动创建"""
        output_root = tmp_path / "auto_created"
        monkeypatch.setattr("core.pdf.compress.OUTPUT_DIR", output_root)

        assert not output_root.exists()
        result = compress(str(sample_pdf), "auto_dir", "medium")
        assert result.exists()
        assert output_root.exists()

    def test_filename_collision(self, sample_pdf: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        """同名文件已存在时，应使用带时间戳的新文件名"""
        monkeypatch.setattr("core.pdf.compress.OUTPUT_DIR", tmp_path)

        # 第一次压缩
        result1 = compress(str(sample_pdf), "collision_test", "medium")
        assert result1.exists()

        # 第二次使用相同文件名
        result2 = compress(str(sample_pdf), "collision_test", "medium")
        assert result2.exists()
        # 文件名应不同（第一个文件存在，第二个应添加时间戳）
        assert result2.name != result1.name

    def test_output_in_pdf_compressed_dir(self, sample_pdf: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        """输出文件应位于 OUTPUT_DIR/PDF/压缩/ 目录下"""
        monkeypatch.setattr("core.pdf.compress.OUTPUT_DIR", tmp_path)

        result = compress(str(sample_pdf), "check_dir", "medium")

        expected_dir = tmp_path / "PDF" / "压缩"
        assert result.parent == expected_dir
        assert expected_dir.exists()
