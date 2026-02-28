# tests/test_scientific_writer_client.py
"""
backend/scientific_writer_client.py 的测试：ensure_env、normalize_query、list_jobs、get_job_status。
每步打印并写入 tests/logs/test_scientific_writer_client_*.log
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


def test_scientific_writer_ensure_env():
    """测试 ensure_env 返回结构。"""
    log = DebugLogger("test_writer_ensure_env", subdir=str(LOG_DIR))
    from backend.scientific_writer_client import ScientificWriterClient
    from backend.config import PROJECT_ROOT
    client = ScientificWriterClient(cwd=PROJECT_ROOT, output_dir=PROJECT_ROOT / "writing_outputs", env_path=PROJECT_ROOT / ".env")
    log.log_input("调用", "ensure_env()")
    out = client.ensure_env()
    log.log_output("ensure_env()", out)
    assert "anthropic_configured" in out and "openrouter_configured" in out
    log.close()


def test_scientific_writer_normalize_query():
    """测试 normalize_query（无 Qwen 时走模板）。"""
    log = DebugLogger("test_writer_normalize", subdir=str(LOG_DIR))
    from backend.scientific_writer_client import ScientificWriterClient
    from backend.config import PROJECT_ROOT
    client = ScientificWriterClient(cwd=PROJECT_ROOT, output_dir=PROJECT_ROOT / "writing_outputs", env_path=PROJECT_ROOT / ".env")
    log.log_input("raw_input", "量子计算")
    log.log_input("venue_id", "nature")
    log.log_input("project_type_id", "paper")
    log.log_input("data_file_names", ["data.csv"])
    out = client.normalize_query(raw_input="量子计算", venue_id="nature", project_type_id="paper", data_file_names=["data.csv"], memory_md="")
    log.log_output("normalize_query(...)", out)
    assert "query" in out and len(out.get("query", "")) >= 0
    log.close()


def test_scientific_writer_list_jobs():
    """测试 list_jobs。"""
    log = DebugLogger("test_writer_list_jobs", subdir=str(LOG_DIR))
    from backend.scientific_writer_client import ScientificWriterClient
    from backend.config import PROJECT_ROOT
    client = ScientificWriterClient(cwd=PROJECT_ROOT, output_dir=PROJECT_ROOT / "writing_outputs", env_path=PROJECT_ROOT / ".env")
    log.log_input("limit", 5)
    jobs = client.list_jobs(limit=5)
    log.log_output("list_jobs(5)", {"count": len(jobs), "sample": jobs[0] if jobs else None})
    assert isinstance(jobs, list)
    log.close()


def test_scientific_writer_get_job_status():
    """测试 get_job_status 对不存在 job_id。"""
    log = DebugLogger("test_writer_job_status", subdir=str(LOG_DIR))
    from backend.scientific_writer_client import ScientificWriterClient
    from backend.config import PROJECT_ROOT
    client = ScientificWriterClient(cwd=PROJECT_ROOT, output_dir=PROJECT_ROOT / "writing_outputs", env_path=PROJECT_ROOT / ".env")
    log.log_input("job_id", "__nonexistent__")
    st = client.get_job_status("__nonexistent__")
    log.log_output("get_job_status(...)", st)
    log.close()


if __name__ == "__main__":
    test_scientific_writer_ensure_env()
    test_scientific_writer_normalize_query()
    test_scientific_writer_list_jobs()
    test_scientific_writer_get_job_status()
    print("test_scientific_writer_client.py done.")
