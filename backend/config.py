# backend/config.py
"""Configuration: env, paths, and default options for formats/skills."""

import os
from pathlib import Path
from typing import List, Dict, Any

try:
    from dotenv import load_dotenv
    _has_dotenv = True
except ImportError:
    _has_dotenv = False

# Load .env from merge_project root (parent of backend/)
_ROOT = Path(__file__).resolve().parent.parent
_ENV_FILE = _ROOT / ".env"
if _has_dotenv and _ENV_FILE.exists():
    load_dotenv(_ENV_FILE, override=True)
elif _has_dotenv:
    load_dotenv(override=False)

# Project paths
PROJECT_ROOT = _ROOT
DATA_DIR = PROJECT_ROOT / "data"
WRITING_OUTPUTS = PROJECT_ROOT / "writing_outputs"
RECORDS_DB = PROJECT_ROOT / "merge_records.db"
JOB_RECORDS_DIR = PROJECT_ROOT / "job_records"

# 统一数据库目录：存放各模块 SQLite 等，便于备份与迁移
DB_DIR = PROJECT_ROOT / "database"
MEMU_DB = DB_DIR / "memu_records.db"
# memU 资源存储：上传时文件复制到此目录，DB 只存该路径；下载时从此目录复制到用户目录（memU 仅做索引，不存原始文件）
MEMU_STORAGE_DIR = DB_DIR / "memu_storage"
# 测试专用：统一单库，减少混乱
MEMU_TEST_DB = DB_DIR / "memu_test.db"
MEMU_TEST_STORAGE = DB_DIR / "memu_storage_test"
# 默认下载目录（用户选择“下载”时，可指定或使用此目录）
MEMU_DOWNLOADS_DIR = DB_DIR / "downloads"

# 场景与 agent 格式配置（JSON，按 agent_id 区分领域）
CONFIG_DIR = PROJECT_ROOT / "config"
CONFIG_AGENTS_DIR = CONFIG_DIR / "agents"
MEMU_SCENARIOS_PATH = CONFIG_DIR / "memu_scenarios.json"
CONFIG_TASKS_DIR = CONFIG_DIR / "tasks"
CONFIG_PROMPTS_DIR = CONFIG_DIR / "prompts"

# Ensure dirs
WRITING_OUTPUTS.mkdir(parents=True, exist_ok=True)
JOB_RECORDS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_DIR.mkdir(parents=True, exist_ok=True)
MEMU_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
MEMU_DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_AGENTS_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_TASKS_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_PROMPTS_DIR.mkdir(parents=True, exist_ok=True)


# ---------- Format / project type options (extensible) ----------
# Frontend can map dropdowns to these keys; custom formats can be appended.
VENUE_FORMATS: List[Dict[str, str]] = [
    {"id": "nature", "label": "Nature", "query_prefix": "Create a Nature paper on"},
    {"id": "science", "label": "Science", "query_prefix": "Create a Science paper on"},
    {"id": "neurips", "label": "NeurIPS", "query_prefix": "Create a NeurIPS paper on"},
    {"id": "ieee", "label": "IEEE", "query_prefix": "Generate an IEEE paper on"},
    {"id": "acm", "label": "ACM", "query_prefix": "Generate an ACM paper on"},
    {"id": "custom", "label": "Custom", "query_prefix": "Create a paper on"},
]

PROJECT_TYPES: List[Dict[str, str]] = [
    {"id": "paper", "label": "论文撰写", "hint": "Scientific paper (IMRaD)"},
    {"id": "poster", "label": "论文海报", "hint": "Conference poster (A0/LaTeX)"},
    {"id": "grant_nsf", "label": "基金申报(NSF)", "hint": "NSF grant proposal"},
    {"id": "grant_nih", "label": "基金申报(NIH)", "hint": "NIH grant proposal"},
    {"id": "literature_review", "label": "文献综述", "hint": "Literature review"},
    {"id": "market_research", "label": "调研报告", "hint": "Market research report"},
    {"id": "custom", "label": "自定义", "hint": "Custom document"},
]

# Mapping project_type id -> scientific-writer style prompt hint
PROJECT_TYPE_PROMPT_HINTS: Dict[str, str] = {
    "paper": "scientific paper with IMRaD structure",
    "poster": "conference poster (A0, LaTeX beamerposter)",
    "grant_nsf": "NSF grant proposal with Intellectual Merit and Broader Impacts",
    "grant_nih": "NIH R01 grant proposal with Specific Aims",
    "literature_review": "systematic literature review with citation management",
    "market_research": "market research report with data and visuals",
    "custom": "document",
}


def get_env(key: str, default: str = "") -> str:
    """读取环境变量；.env 由本模块顶部 load_dotenv 加载。详见 .env.example。"""
    return os.getenv(key, default).strip()


# 意图识别与上下文模型：默认 qwen 系列；可选 OpenRouter 调用 Google 等大模型
INTENT_MODEL_DEFAULT = "qwen-turbo"
CONTEXT_MODEL_DEFAULT = "qwen-long"
OPENROUTER_HIGH_TIER_MODEL = "google/gemini-2.0-flash-exp"


def add_venue_format(uid: str, label: str, query_prefix: str) -> None:
    """Extend venue formats at runtime (for user-defined formats)."""
    VENUE_FORMATS.append({"id": uid, "label": label, "query_prefix": query_prefix})


def add_project_type(uid: str, label: str, hint: str, prompt_hint: str) -> None:
    """Extend project types at runtime (for user-defined skills)."""
    PROJECT_TYPES.append({"id": uid, "label": label, "hint": hint})
    PROJECT_TYPE_PROMPT_HINTS[uid] = prompt_hint
