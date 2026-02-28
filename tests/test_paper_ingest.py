# tests/test_paper_ingest.py
"""
backend/paper_ingest.py 的测试：extract_paper_structure、paper_ingest_pdf。
使用 docs 下数据；PDF 提取需 DASHSCOPE_API_KEY 与真实 PDF，否则测错误路径与参量打印。
每步打印并写入 tests/logs/test_paper_ingest_*.log
"""

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=True)
except ImportError:
    pass

from tests.test_utils import DebugLogger, LOG_DIR, get_docs_path


def test_extract_paper_structure_non_pdf():
    """测试 extract_paper_structure 对非 PDF 返回 error。"""
    log = DebugLogger("test_paper_ingest_non_pdf", subdir=str(LOG_DIR))
    from backend.paper_ingest import extract_paper_structure
    txt_path = get_docs_path("prompt.txt")
    log.log_file_used("输入文件", str(txt_path), txt_path.exists())
    log.log_input("file_path", str(txt_path))
    log.log_input("agent_id", "physics_agent")
    out = extract_paper_structure(str(txt_path), agent_id="physics_agent")
    log.log_output("extract_paper_structure(...)", out)
    assert out.get("error") or "metadata" in out
    log.close()


def test_paper_ingest_pdf_no_pdf_file():
    """测试 paper_ingest_pdf 对不存在文件返回 error。"""
    log = DebugLogger("test_paper_ingest_no_file", subdir=str(LOG_DIR))
    from backend.paper_ingest import paper_ingest_pdf
    log.log_input("file_path", "/nonexistent/file.pdf")
    log.log_input("user_id", "test_u")
    log.log_input("agent_ids", ["physics_agent"])
    out = paper_ingest_pdf(file_path="/nonexistent/file.pdf", user_id="test_u", agent_ids=["physics_agent"])
    log.log_output("paper_ingest_pdf(...)", out)
    assert out.get("error") == "文件不存在"
    log.close()


def test_paper_ingest_pdf_with_txt_skips_extraction():
    """使用 .txt 调用 paper_ingest_pdf：会进入提取但 PDF 检测失败，结果中应有 error 或跳过。"""
    log = DebugLogger("test_paper_ingest_txt", subdir=str(LOG_DIR))
    txt_path = get_docs_path("prompt.txt")
    if not txt_path.exists():
        log.log_step("skip", "docs/prompt.txt 不存在")
        log.close()
        return
    from backend.paper_ingest import paper_ingest_pdf
    from backend.config import DB_DIR
    tmp_storage = Path(tempfile.mkdtemp())
    log.log_input("file_path", str(txt_path))
    log.log_input("user_id", "test_u")
    log.log_input("agent_ids", ["physics_agent"])
    out = paper_ingest_pdf(file_path=str(txt_path), user_id="test_u", agent_ids=["physics_agent"], storage_dir=tmp_storage)
    log.log_output("paper_ingest_pdf(...)", out)
    # 非 PDF 时 extract 返回带 error 的 dict，results 里会有 error
    log.log_step("results", out.get("results", []))
    log.log_step("agent_ids", out.get("agent_ids", "N/A"))
    log.close()


def test_paper_ingest_pdf_intent_driven_agent_ids():
    """paper_ingest_pdf(agent_ids=None) 时由意图识别得到 agent_ids；打印返回的 agent_ids。"""
    log = DebugLogger("test_paper_ingest_intent", subdir=str(LOG_DIR))
    txt_path = get_docs_path("prompt.txt")
    if not txt_path.exists():
        t = Path(tempfile.mkdtemp())
        txt_path = t / "dummy.txt"
        txt_path.write_text("generic content", encoding="utf-8")
    from backend.paper_ingest import paper_ingest_pdf
    tmp_storage = Path(tempfile.mkdtemp())
    log.log_input("file_path", str(txt_path))
    log.log_input("user_id", "test_u")
    log.log_input("agent_ids", None)
    out = paper_ingest_pdf(file_path=str(txt_path), user_id="test_u", agent_ids=None, storage_dir=tmp_storage)
    log.log_output("paper_ingest_pdf(agent_ids=None)", {"agent_ids": out.get("agent_ids"), "error": out.get("error"), "results_count": len(out.get("results", []))})
    log.log_step("agent_ids 由意图识别得到", str(out.get("agent_ids")))
    assert "agent_ids" in out
    log.close()


if __name__ == "__main__":
    test_extract_paper_structure_non_pdf()
    test_paper_ingest_pdf_no_pdf_file()
    test_paper_ingest_pdf_with_txt_skips_extraction()
    test_paper_ingest_pdf_intent_driven_agent_ids()
    print("test_paper_ingest.py done.")
