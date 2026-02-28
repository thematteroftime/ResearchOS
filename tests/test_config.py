# tests/test_config.py
"""
backend/config.py 的测试：路径、环境变量、格式选项。
每一步打印并写入 tests/logs/test_config_*.log
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.test_utils import DebugLogger, LOG_DIR, get_docs_path


def test_project_paths():
    """测试 PROJECT_ROOT、DATA_DIR、CONFIG_DIR 等路径存在且可访问。"""
    log = DebugLogger("test_config_paths", subdir=str(LOG_DIR))
    log.log_input("ROOT", str(ROOT))
    from backend import config as cfg
    log.log_step("import config", "ok")
    log.log_input("PROJECT_ROOT", str(cfg.PROJECT_ROOT))
    log.log_input("DATA_DIR", str(cfg.DATA_DIR))
    log.log_input("CONFIG_DIR", str(cfg.CONFIG_DIR))
    log.log_input("MEMU_SCENARIOS_PATH", str(cfg.MEMU_SCENARIOS_PATH))
    log.log_input("CONFIG_TASKS_DIR", str(cfg.CONFIG_TASKS_DIR))
    log.log_input("CONFIG_PROMPTS_DIR", str(cfg.CONFIG_PROMPTS_DIR))
    log.log_input("DB_DIR", str(cfg.DB_DIR))
    log.log_input("MEMU_STORAGE_DIR", str(cfg.MEMU_STORAGE_DIR))
    assert cfg.PROJECT_ROOT.exists(), "PROJECT_ROOT 应存在"
    assert cfg.CONFIG_DIR.exists(), "CONFIG_DIR 应存在"
    assert cfg.DB_DIR.exists(), "DB_DIR 应存在"
    log.log_output("result", "all paths ok")
    log.close()


def test_get_env():
    """测试 get_env 读取与默认值。"""
    log = DebugLogger("test_config_get_env", subdir=str(LOG_DIR))
    from backend.config import get_env
    log.log_step("get_env", "测试不存在的 key")
    v = get_env("__NONEXISTENT_KEY_123__", default="default_val")
    log.log_input("key", "__NONEXISTENT_KEY_123__")
    log.log_input("default", "default_val")
    log.log_output("get_env(...)", v)
    assert v == "default_val"
    log.log_step("get_env 存在 key 时", "若 .env 有 MEMU_AGENT_ID 则可能非空")
    v2 = get_env("MEMU_AGENT_ID", default="physics_agent")
    log.log_output("get_env(MEMU_AGENT_ID,...)", v2)
    log.close()


def test_venue_formats_and_project_types():
    """测试 VENUE_FORMATS、PROJECT_TYPES 结构。"""
    log = DebugLogger("test_config_venue", subdir=str(LOG_DIR))
    from backend.config import VENUE_FORMATS, PROJECT_TYPES
    log.log_input("VENUE_FORMATS 条数", len(VENUE_FORMATS))
    log.log_input("VENUE_FORMATS[0]", VENUE_FORMATS[0] if VENUE_FORMATS else None)
    log.log_input("PROJECT_TYPES 条数", len(PROJECT_TYPES))
    log.log_input("PROJECT_TYPES[0]", PROJECT_TYPES[0] if PROJECT_TYPES else None)
    assert len(VENUE_FORMATS) >= 1 and "id" in VENUE_FORMATS[0]
    assert len(PROJECT_TYPES) >= 1 and "id" in PROJECT_TYPES[0]
    log.log_output("result", "venue and project types ok")
    log.close()


if __name__ == "__main__":
    test_project_paths()
    test_get_env()
    test_venue_formats_and_project_types()
    print("test_config.py done.")
