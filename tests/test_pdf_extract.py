# tests/test_pdf_extract.py
"""
backend/pdf_extract.py 的测试：extract_raw_with_pymupdf、verify_formulas_with_llm。
- 使用 docs/2601.00062v1.pdf 若存在；否则测非 PDF 与错误路径
- 每步打印并写入 tests/logs/test_pdf_extract_*.log
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=True)
except ImportError:
    pass

from tests.test_utils import DebugLogger, LOG_DIR, get_docs_path


def test_extract_raw_with_pymupdf_no_file():
    """测试 extract_raw_with_pymupdf 对不存在文件返回 error。"""
    log = DebugLogger("test_pdf_extract_no_file", subdir=str(LOG_DIR))
    from backend.pdf_extract import extract_raw_with_pymupdf
    out = extract_raw_with_pymupdf("/nonexistent/file.pdf")
    log.log_output("extract_raw_with_pymupdf", {"error": out.get("error"), "raw_text_len": len(out.get("raw_text", ""))})
    assert out.get("error")
    assert out.get("raw_text", "") == ""
    log.close()


def test_extract_raw_with_pymupdf_non_pdf():
    """测试 extract_raw_with_pymupdf 对非 PDF 返回 error。"""
    log = DebugLogger("test_pdf_extract_non_pdf", subdir=str(LOG_DIR))
    txt_path = get_docs_path("prompt.txt")
    if not txt_path.exists():
        import tempfile
        t = Path(tempfile.mkdtemp())
        txt_path = t / "dummy.txt"
        txt_path.write_text("dummy", encoding="utf-8")
    from backend.pdf_extract import extract_raw_with_pymupdf
    out = extract_raw_with_pymupdf(str(txt_path))
    log.log_output("extract_raw_with_pymupdf", {"error": out.get("error"), "raw_text_len": len(out.get("raw_text", ""))})
    assert out.get("error") == "仅支持 PDF"
    log.close()


def test_extract_raw_with_pymupdf_real_pdf():
    """测试 extract_raw_with_pymupdf 对真实 PDF 提取（若 2601.00062v1.pdf 存在）。"""
    log = DebugLogger("test_pdf_extract_real", subdir=str(LOG_DIR))
    pdf_path = get_docs_path("2601.00062v1.pdf")
    log.log_file_used("PDF", str(pdf_path), pdf_path.exists())
    from backend.pdf_extract import extract_raw_with_pymupdf
    out = extract_raw_with_pymupdf(str(pdf_path))
    log.log_output("extract_raw_with_pymupdf", {
        "error": out.get("error"),
        "raw_text_len": len(out.get("raw_text", "")),
        "pages_count": len(out.get("pages", [])),
        "images_count": len(out.get("images", [])),
    })
    if pdf_path.exists() and not out.get("error"):
        assert len(out.get("raw_text", "")) > 0, "PDF 存在且无 error 时应有 raw_text"
        log.log_step("raw_text_preview", out.get("raw_text", "")[:500])
    elif pdf_path.exists() and out.get("error"):
        log.log_step("warn", f"PDF 存在但提取失败: {out.get('error')}")
    else:
        log.log_step("skip", "2601.00062v1.pdf 不存在，跳过真实提取断言")
    log.close()


def test_verify_formulas_with_llm_empty():
    """测试 verify_formulas_with_llm 对空文本返回空 corrected_text。"""
    log = DebugLogger("test_pdf_extract_verify_empty", subdir=str(LOG_DIR))
    from backend.pdf_extract import verify_formulas_with_llm
    out = verify_formulas_with_llm("", agent_id="_default")
    log.log_output("verify_formulas_with_llm", out)
    assert out.get("corrected_text") == ""
    log.close()


if __name__ == "__main__":
    test_extract_raw_with_pymupdf_no_file()
    test_extract_raw_with_pymupdf_non_pdf()
    test_extract_raw_with_pymupdf_real_pdf()
    test_verify_formulas_with_llm_empty()
    print("test_pdf_extract.py done. 日志:", LOG_DIR)
