# tests/test_backend_integration.py
"""
全流程集成测试：env、query 规范化、论文生成（可选）、任务状态、容错。
运行：在 merge_project 根目录下
  python -m pytest tests/test_backend_integration.py -v
  或
  python tests/test_backend_integration.py
"""

import asyncio
import os
import sys
from pathlib import Path

# 保证能 import backend
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend import AppBackend, get_env


def test_env_check():
    """检查 .env 与 ensure_env 返回结构。"""
    app = AppBackend()
    out = app.ensure_env()
    assert "anthropic_configured" in out
    assert "openrouter_configured" in out
    print("[OK] ensure_env:", out)


def test_venue_and_project_options():
    """格式与类型选项可被前端使用。"""
    app = AppBackend()
    venues = app.get_venue_formats()
    types = app.get_project_types()
    assert len(venues) >= 1 and "id" in venues[0]
    assert len(types) >= 1 and "id" in types[0]
    print("[OK] venues:", len(venues), "types:", len(types))


def test_normalize_query_no_qwen():
    """无 Qwen 时仍可返回模板 query。"""
    app = AppBackend()
    # 临时去掉 DASHSCOPE 会走 template 分支
    old = os.environ.pop("DASHSCOPE_API_KEY", None)
    try:
        out = app.normalize_query(
            raw_input="量子计算基础",
            venue_id="nature",
            project_type_id="paper",
            data_file_names=["data.csv", "fig1.png"],
        )
        assert "query" in out and len(out["query"]) > 0
        print("[OK] normalize_query (template):", out["query"][:80], "...")
    finally:
        if old is not None:
            os.environ["DASHSCOPE_API_KEY"] = old


async def _run_paper_once():
    """跑一次论文生成（需要 ANTHROPIC_API_KEY）；若无 key 则只测到 normalize 为止。"""
    app = AppBackend()
    steps = []

    def log(stage: str, msg: str):
        steps.append((stage, msg))
        print(f"  [{stage}] {msg}")

    if not get_env("ANTHROPIC_API_KEY"):
        print("[SKIP] 未设置 ANTHROPIC_API_KEY，跳过实际 generate_paper")
        return

    count = 0
    async for update in app.run_paper_generation(
        raw_input="short 2-page LaTeX paper on quantum computing basics",
        venue_id="nature",
        project_type_id="paper",
        data_file_names=[],
        log_step=log,
    ):
        if update.get("type") == "progress":
            count += 1
        elif update.get("type") == "result":
            status = update.get("status")
            print("[OK] result status:", status)
            if status == "success":
                job_id = None
                for j in app.list_jobs(limit=1):
                    job_id = j.get("job_id")
                    break
                if job_id:
                    st = app.get_job_status(job_id)
                    assert st is not None
                    print("[OK] job_status:", st.get("status"), st.get("pdf_final", "")[:60])
            break
    print("[OK] progress updates received:", count)


def test_run_paper_generation():
    """异步论文生成（有 key 时真正调用）。"""
    asyncio.run(_run_paper_once())


def test_list_jobs():
    """任务列表可读。"""
    app = AppBackend()
    jobs = app.list_jobs(limit=5)
    assert isinstance(jobs, list)
    print("[OK] list_jobs len:", len(jobs))


if __name__ == "__main__":
    test_env_check()
    test_venue_and_project_options()
    test_normalize_query_no_qwen()
    test_list_jobs()
    test_run_paper_generation()
    print("\n全流程测试结束。")
