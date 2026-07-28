"""
测试 core/pdf/compress.py — PDF 压缩功能（基于 ocrmypdf）

集成测试需要 Ghostscript 可用，否则自动跳过。
"""
import shutil
from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter

from core.pdf.compress import (
    compress,
    _level_to_ocrmypdf_params,
    _resolve_compression_level,
)


# =============================================================================
# Ghostscript 可用性检查（集成测试的跳过条件）
# =============================================================================
def _ghostscript_available() -> bool:
    """检查系统是否安装了 Ghostscript（ocrmypdf 的必需依赖）。"""
    try:
        from ocrmypdf._exec.ghostscript import version

        version.get_version("gs")
        return True
    except Exception:
        pass
    try:
        version.get_version("gswin64c")
        return True
    except Exception:
        pass
    try:
        version.get_version("gswin32c")
        return True
    except Exception:
        pass
    return False


_has_gs = _ghostscript_available()


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
# 测试 _level_to_ocrmypdf_params
# =============================================================================
class TestLevelToOcrmypdfParams:
    def test_level_zero(self):
        params = _level_to_ocrmypdf_params(0)
        assert params["optimize"] == 0
        assert params["output_type"] == "pdf"
        assert "jpg_quality" not in params

    def test_level_low(self):
        params = _level_to_ocrmypdf_params(1)
        assert params["optimize"] == 1
        assert params["jpg_quality"] == 85

        params = _level_to_ocrmypdf_params(3)
        assert params["optimize"] == 1

    def test_level_medium(self):
        params = _level_to_ocrmypdf_params(5)
        assert params["optimize"] == 2
        assert params["jpg_quality"] == 65

        params = _level_to_ocrmypdf_params(6)
        assert params["optimize"] == 2

    def test_level_high(self):
        params = _level_to_ocrmypdf_params(9)
        assert params["optimize"] == 3
        assert params["jpg_quality"] == 35

        params = _level_to_ocrmypdf_params(7)
        assert params["optimize"] == 3

    def test_all_levels_include_output_type_pdf(self):
        for level in range(10):
            params = _level_to_ocrmypdf_params(level)
            assert params["output_type"] == "pdf"


# =============================================================================
# 测试 compress 函数基础行为（不依赖 Ghostscript）
# =============================================================================
class TestCompressBasic:
    def test_file_not_found(self):
        """源文件不存在时应抛出 FileNotFoundError"""
        with pytest.raises(FileNotFoundError, match="PDF 文件不存在"):
            compress("/nonexistent/path.pdf", "test", "medium")


# =============================================================================
# 集成测试（需要 Ghostscript）
# =============================================================================
@pytest.mark.skipif(not _has_gs, reason="系统未安装 Ghostscript，跳过集成测试")
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

    def test_pages_preserved(
        self, sample_pdf: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """压缩后页数应与原 PDF 一致"""
        monkeypatch.setattr("core.pdf.compress.OUTPUT_DIR", tmp_path)

        result = compress(str(sample_pdf), "pages_test", 5)

        original_reader = PdfReader(sample_pdf)
        compressed_reader = PdfReader(result)
        assert len(compressed_reader.pages) == len(original_reader.pages)

    def test_compressed_file_smaller_or_equal(
        self, sample_pdf: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """优化等级 >=1 时压缩文件不应大于原文件"""
        monkeypatch.setattr("core.pdf.compress.OUTPUT_DIR", tmp_path)

        result = compress(str(sample_pdf), "smaller_test", 5)

        original_size = sample_pdf.stat().st_size
        compressed_size = result.stat().st_size
        assert compressed_size <= original_size + 1024, (
            f"压缩后 ({compressed_size}B) 不应显著大于原文件 ({original_size}B)"
        )

    def test_higher_level_smaller_or_equal(
        self, sample_pdf: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """较高压缩等级不应产生更大的文件"""
        monkeypatch.setattr("core.pdf.compress.OUTPUT_DIR", tmp_path)

        result_low = compress(str(sample_pdf), "level_low", 1)
        result_high = compress(str(sample_pdf), "level_high", 9)

        size_low = result_low.stat().st_size
        size_high = result_high.stat().st_size
        # 允许一些容差（对于空白页不同等级的差异可能极小）
        assert size_high <= size_low + 512, (
            f"高压缩 ({size_high}B) 不应显著大于低压缩 ({size_low}B)"
        )

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
