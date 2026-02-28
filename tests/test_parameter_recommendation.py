# tests/test_parameter_recommendation.py
"""
backend/parameter_recommendation.py 的测试：run_parameter_recommendation（memory_context 由 app_backend 传入）。
app_backend._get_memory_context_for_agents 多 agent 联合检索的测试。
使用假定的 structured_paper 与 user_params；每步打印并写入 tests/logs/test_parameter_recommendation_*.log
"""

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


# 测试用结构化论文（最小可用的 physics 结构）
FAKE_STRUCTURED_PAPER = {
    "metadata": {"title": "Test paper", "journal": "J", "year": "2024", "innovation": "test"},
    "physics_context": {"environment": "PK-4", "detailed_background": "complex plasma"},
    "observed_phenomena": "链状结构形成",
    "simulation_results_description": "MD 模拟",
    "keywords": ["plasma", "dust"],
    "parameters": [{"name": "kappa", "symbol": "κ", "value": "2", "unit": "1", "meaning": " screening"}],
    "force_fields": [{"name": "Yukawa", "formula": "U(r)", "physical_significance": "screened", "computational_hint": ""}],
}

FAKE_USER_PARAMS = {
    "expected_phenomena": "链状结构",
    "kappa": "屏蔽参数，单位 1",
}


def test_get_memory_context_for_agents():
    """测试 app_backend._get_memory_context_for_agents 多 agent 记忆检索合并（memU 未配置时为空或 error）。"""
    log = DebugLogger("test_param_rec_memory", subdir=str(LOG_DIR))
    from backend.app_backend import AppBackend
    tmp = Path(tempfile.mkdtemp())
    app = AppBackend(memu_user_id="test_u", memu_agent_id="physics_agent", memu_db_path=tmp / "m.db", memu_storage_dir=tmp / "s")
    log.log_input("query", "等离子体 参数")
    log.log_input("user_id", "test_u")
    log.log_input("agent_ids", ["physics_agent"])
    ctx = app._get_memory_context_for_agents("等离子体 参数", "test_u", ["physics_agent"], max_chars_per_agent=500)
    log.log_output("_get_memory_context_for_agents(...)", {"len": len(ctx), "preview": ctx[:200] if ctx else ""})
    assert isinstance(ctx, str)
    log.close()


def test_run_parameter_recommendation():
    """测试 run_parameter_recommendation：使用假 structured_paper 与 user_params；无 DASHSCOPE 时返回 error。"""
    log = DebugLogger("test_param_rec_run", subdir=str(LOG_DIR))
    from backend.parameter_recommendation import run_parameter_recommendation
    log.log_input("structured_paper", FAKE_STRUCTURED_PAPER)
    log.log_input("user_params", FAKE_USER_PARAMS)
    log.log_input("user_id", "test_u")
    log.log_input("agent_ids", ["physics_agent"])
    out = run_parameter_recommendation(
        structured_paper=FAKE_STRUCTURED_PAPER,
        user_params=FAKE_USER_PARAMS,
        user_id="test_u",
        agent_ids=["physics_agent"],
        memory_context="",
        relevant_forces=[],
    )
    log.log_output("run_parameter_recommendation(...)", out)
    log.log_step("agent_id_used", out.get("agent_id_used", "N/A"))
    assert "parameter_recommendations" in out or "error" in out
    if out.get("error"):
        log.log_step("说明", "DASHSCOPE_API_KEY 未配置时返回 error，属预期")
    log.close()


def test_run_parameter_recommendation_default_agent():
    """测试 run_parameter_recommendation 使用 _default agent（不拉 MemU 记忆）。"""
    log = DebugLogger("test_param_rec_default", subdir=str(LOG_DIR))
    from backend.parameter_recommendation import run_parameter_recommendation
    structured = {"metadata": {"title": "Generic"}, "methodology": "实验", "keywords": []}
    params = {"expected_phenomena": "效果", "x": "关键量"}
    out = run_parameter_recommendation(
        structured_paper=structured,
        user_params=params,
        user_id="test_u",
        agent_ids=["_default"],
        memory_context="",
    )
    log.log_output("run_parameter_recommendation(agent_ids=[_default])", out)
    log.log_step("agent_id_used", out.get("agent_id_used", "N/A"))
    assert out.get("agent_id_used") == "_default"
    assert "parameter_recommendations" in out or "error" in out
    log.close()


def test_get_memory_context_multi_agent():
    """测试 app_backend._get_memory_context_for_agents 多 agent 联合检索：physics_agent + cs_agent。"""
    log = DebugLogger("test_param_rec_multi_agent", subdir=str(LOG_DIR))
    from backend.app_backend import AppBackend
    tmp = Path(tempfile.mkdtemp())
    app = AppBackend(memu_user_id="test_u", memu_agent_id="physics_agent", memu_db_path=tmp / "m.db", memu_storage_dir=tmp / "s")
    ctx = app._get_memory_context_for_agents("算法 物理", "test_u", ["physics_agent", "cs_agent"], max_chars_per_agent=300)
    log.log_output("_get_memory_context_for_agents(physics_agent+cs_agent)", {"len": len(ctx), "preview": ctx[:200] if ctx else ""})
    assert isinstance(ctx, str)
    log.close()


if __name__ == "__main__":
    test_get_memory_context_for_agents()
    test_run_parameter_recommendation()
    test_run_parameter_recommendation_default_agent()
    test_get_memory_context_multi_agent()
    print("test_parameter_recommendation.py done.")
