# tests/test_agent_config.py
"""
backend/agent_config.py 的测试：load_scenarios、get_task_config、get_prompt、get_memorize_override_config、intent_to_agent_ids、list_agent_ids。
每一步打印并写入 tests/logs/test_agent_config_*.log
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.test_utils import DebugLogger, LOG_DIR, get_docs_path


def test_load_scenarios():
    """测试 load_scenarios 返回 dict 且含 physics_agent 或 _default。"""
    log = DebugLogger("test_agent_load_scenarios", subdir=str(LOG_DIR))
    from backend import agent_config as ac
    log.log_input("调用", "load_scenarios()")
    data = ac.load_scenarios()
    log.log_output("load_scenarios()", list(data.keys()) if isinstance(data, dict) else data)
    assert isinstance(data, dict)
    assert "physics_agent" in data or "_default" in data
    log.log_step("assert", "ok")
    log.close()


def test_get_task_config():
    """测试 get_task_config(agent_id, task_name)。"""
    log = DebugLogger("test_agent_get_task_config", subdir=str(LOG_DIR))
    from backend import agent_config as ac
    log.log_input("agent_id", "physics_agent")
    log.log_input("task_name", "paper_ingest")
    cfg = ac.get_task_config("physics_agent", "paper_ingest")
    log.log_output("get_task_config(...)", cfg)
    assert isinstance(cfg, dict)
    log.log_input("task_name", "parameter_recommendation")
    cfg2 = ac.get_task_config("physics_agent", "parameter_recommendation")
    log.log_output("get_task_config(..., parameter_recommendation)", cfg2)
    log.close()


def test_get_prompt():
    """测试 get_prompt：加载 physics_agent 的 paper_extraction_s1。"""
    log = DebugLogger("test_agent_get_prompt", subdir=str(LOG_DIR))
    from backend import agent_config as ac
    log.log_input("agent_id", "physics_agent")
    log.log_input("prompt_key", "extraction_s1")
    log.log_input("task_name", "paper_ingest")
    text = ac.get_prompt("physics_agent", "extraction_s1", task_name="paper_ingest")
    log.log_output("get_prompt(...) 长度", len(text))
    log.log_prompt("paper_extraction_s1", text, max_chars=300)
    assert isinstance(text, str)
    log.close()


def test_get_memorize_override_config():
    """测试 get_memorize_override_config(agent_id, task_name)。"""
    log = DebugLogger("test_agent_memorize_config", subdir=str(LOG_DIR))
    from backend import agent_config as ac
    log.log_input("agent_id", "physics_agent")
    log.log_input("task_name", "paper_ingest")
    override = ac.get_memorize_override_config("physics_agent", "paper_ingest")
    log.log_output("get_memorize_override_config(...)", override)
    assert "memory_types" in override
    log.close()


def test_intent_to_agent_ids():
    """测试 intent_to_agent_ids：小模型 API，无关键词；无 API 或解析失败时返回 _default。"""
    log = DebugLogger("test_agent_intent", subdir=str(LOG_DIR))
    from backend import agent_config as ac
    log.log_input("input_text", "复杂等离子体模拟")
    ids = ac.intent_to_agent_ids(input_text="复杂等离子体模拟")
    log.log_output("intent_to_agent_ids(物理)", ids)
    assert isinstance(ids, list) and len(ids) >= 1
    assert ids[0] in ("physics_agent", "_default") or "physics_agent" in ids
    log.log_input("input_text", "算法实现与物理仿真")
    ids2 = ac.intent_to_agent_ids(input_text="算法实现与物理仿真")
    log.log_output("intent_to_agent_ids(物理+CS)", ids2)
    log.log_input("input_text", "")
    ids3 = ac.intent_to_agent_ids(input_text="")
    log.log_output("intent_to_agent_ids(空输入)", ids3)
    assert ids3 == ["_default"]
    log.close()


def test_get_parameter_recommendation_system_prompt():
    """测试 get_parameter_recommendation_system_prompt：physics_agent、_default、cs_agent。"""
    log = DebugLogger("test_agent_param_system", subdir=str(LOG_DIR))
    from backend import agent_config as ac
    for aid in ("physics_agent", "_default", "cs_agent"):
        prompt = ac.get_parameter_recommendation_system_prompt(aid)
        log.log_output("get_parameter_recommendation_system_prompt(%s)" % aid, prompt[:120] + "..." if len(prompt) > 120 else prompt)
        assert isinstance(prompt, str)
    log.close()


def test_cs_agent_prompts():
    """测试 cs_agent 的 get_task_config、get_prompt（paper_ingest、parameter_recommendation）。"""
    log = DebugLogger("test_agent_cs", subdir=str(LOG_DIR))
    from backend import agent_config as ac
    cfg = ac.get_task_config("cs_agent", "paper_ingest")
    log.log_output("get_task_config(cs_agent, paper_ingest)", cfg)
    assert isinstance(cfg, dict)
    s1 = ac.get_prompt("cs_agent", "extraction_s1", task_name="paper_ingest")
    log.log_output("get_prompt(cs_agent, extraction_s1)", len(s1))
    assert isinstance(s1, str)
    pr = ac.get_prompt("cs_agent", "prompt", task_name="parameter_recommendation")
    log.log_output("get_prompt(cs_agent, parameter_recommendation)", len(pr))
    log.close()


def test_list_agent_ids():
    """测试 list_agent_ids()。"""
    log = DebugLogger("test_agent_list", subdir=str(LOG_DIR))
    from backend import agent_config as ac
    log.log_input("调用", "list_agent_ids()")
    ids = ac.list_agent_ids()
    log.log_output("list_agent_ids()", ids)
    assert isinstance(ids, list)
    log.close()


if __name__ == "__main__":
    test_load_scenarios()
    test_get_task_config()
    test_get_prompt()
    test_get_memorize_override_config()
    test_intent_to_agent_ids()
    test_get_parameter_recommendation_system_prompt()
    test_cs_agent_prompts()
    test_list_agent_ids()
    print("test_agent_config.py done.")
