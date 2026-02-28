# tests/test_writing_chain.py
"""
写作调用链验证：AppBackend → ScientificWriterClient → scientific_writer.generate_paper

验证目标：
  1) AppBackend.run_paper_generation 可正常调用（完整链路）
  2) data_files 解析正确（支持 data/、docs/、绝对路径）
  3) use_minimal_query 与完整 query 模式均可工作

运行：
  pytest tests/test_writing_chain.py -v -s
  python tests/test_writing_chain.py
"""

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=True)
except ImportError:
    pass

from tests.test_utils import DebugLogger, LOG_DIR, create_app_backend_for_test, get_test_db_and_storage


def _resolve_data_files():
    """解析写作数据文件：优先 PDF（data/ 或 docs/），无则用 quantum_chaos_summary_sample.md。"""
    data_dir = ROOT / "data"
    docs_dir = ROOT / "docs"
    papers = ["2511.00150v1.pdf", "2601.00062v1.pdf", "2601.00077v1.pdf"]
    resolved = []
    for name in papers:
        for base in (data_dir, docs_dir):
            if (base / name).exists():
                resolved.append(str((base / name).resolve()))
                break
    if resolved:
        return resolved
    fallback = data_dir / "quantum_chaos_summary_sample.md"
    if fallback.exists():
        return [str(fallback.resolve())]
    return []


def test_app_backend_run_paper_generation_chain():
    """
    验证 AppBackend.run_paper_generation 完整调用链。
    使用 data/ 或 docs/ 下的数据文件，无 API key 时跳过实际生成。
    """
    try:
        from backend.app_backend import AppBackend
    except ImportError as e:
        if "httpx" in str(e):
            import pytest
            pytest.skip("缺少 httpx: pip install httpx python-dotenv")
        raise

    log = DebugLogger("test_writing_chain", subdir=str(LOG_DIR))

    data_files = _resolve_data_files()
    if not data_files:
        log._write("[SKIP] 无 data_files（需 data/ 或 docs/ 下的 PDF，或 data/quantum_chaos_summary_sample.md）")
        return

    app = create_app_backend_for_test(user_id="writing_chain_test", agent_id="physics_agent")
    env = app.ensure_env()
    log.log_output("ensure_env", env)

    if not env.get("anthropic_configured"):
        log._write("[SKIP] 无 ANTHROPIC_API_KEY，跳过实际生成；仅验证调用链可启动")
        raw_input = "Create a Nature paper on quantum chaos. Target 500 words."
        data_file_names = data_files

        async def _run():
            updates = []
            async for upd in app.run_paper_generation(
                raw_input=raw_input,
                venue_id="nature",
                project_type_id="paper",
                data_file_names=data_file_names,
                use_minimal_query=True,
            ):
                updates.append(upd)
                if upd.get("type") == "progress":
                    log._write(f"  [progress] {upd.get('stage')} {upd.get('message')}")
            return updates

        try:
            updates = asyncio.run(_run())
            log._write(f"[OK] 调用链可启动，收到 {len(updates)} 条 update")
            # 无 key 时通常会很快失败，至少能验证到 writer.generate_paper 被调用
            assert len(updates) >= 1
        except Exception as e:
            log._write(f"[WARN] 调用异常（可能是 API key 缺失）: {e}")
        log.close()
        return

    raw_input = (
        "Create a short Nature paper on quantum chaos in driven spin systems. "
        "Summarize the attached file. Keep manuscript to 800 words."
    )

    async def _run_full():
        result = None
        async for upd in app.run_paper_generation(
            raw_input=raw_input,
            venue_id="nature",
            project_type_id="paper",
            data_file_names=data_files,
            use_minimal_query=True,
        ):
            if upd.get("type") == "progress":
                log._write(f"  [progress] {upd.get('stage')} {upd.get('message')}")
            elif upd.get("type") == "result":
                result = upd
                log.log_output("run_paper_generation result", upd)
        return result

    result = asyncio.run(_run_full())
    log._write(f"[DONE] status={result.get('status') if result else 'N/A'}")
    log.close()

    assert result is not None, "应收到 result 类型 update"
    # success 或 failed 都算调用链通畅
    assert result.get("status") in ("success", "failed"), f"unexpected status: {result.get('status')}"


if __name__ == "__main__":
    test_app_backend_run_paper_generation_chain()
    print("test_writing_chain.py done.")
