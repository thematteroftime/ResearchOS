# backend/agent_config.py
"""
Agent 与任务配置加载：memu_scenarios、tasks、prompts。
- 按 agent_id 与 task_name 返回 memory override_config 与 prompt 内容
- 意图识别 intent_to_agent_ids：小模型 API（qwen 系列），无关键词规则，兜底 _default
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import (
    CONFIG_AGENTS_DIR,
    CONFIG_PROMPTS_DIR,
    CONFIG_TASKS_DIR,
    MEMU_SCENARIOS_PATH,
    get_env,
    INTENT_MODEL_DEFAULT,
)


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_scenarios() -> Dict[str, Any]:
    """加载 memu_scenarios.json。"""
    return _load_json(MEMU_SCENARIOS_PATH)


# provider -> (api_key_env, base_url_env, default_base_url)
_PROVIDER_ENV: Dict[str, tuple] = {
    "qwen": ("DASHSCOPE_API_KEY", "DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
    "dashscope": ("DASHSCOPE_API_KEY", "DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
    "openrouter": ("OPENROUTER_API_KEY", "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
    "anthropic": ("ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
    "openai": ("OPENAI_API_KEY", "OPENAI_BASE_URL", "https://api.openai.com/v1"),
}


def _load_agents_config(agent_id: str) -> Dict[str, Any]:
    """从 config/agents/<agent_id>.json 加载；缺失时回退 _default.json。"""
    for aid in (agent_id, "_default"):
        path = CONFIG_AGENTS_DIR / f"{aid}.json"
        if path.exists():
            data = _load_json(path)
            if isinstance(data, dict):
                return data
    return {}


def get_model_for_step(agent_id: str, task_name: str, step: str) -> Dict[str, str]:
    """
    从 config/agents/<agent_id>.json 读取 (task_name, step) 对应的 provider、model。
    缺失时回退 _default.json；再缺失则使用 qwen 兜底。
    返回：{"provider": "qwen", "model": "qwen-long"}
    """
    cfg = _load_agents_config(agent_id)
    task_cfg = cfg.get(task_name)
    if isinstance(task_cfg, dict):
        step_cfg = task_cfg.get(step)
        if isinstance(step_cfg, dict):
            provider = (step_cfg.get("provider") or "qwen").lower()
            model = step_cfg.get("model") or "qwen-long"
            return {"provider": provider, "model": model}
    return {"provider": "qwen", "model": "qwen-long"}


def get_client_for_step(agent_id: str, task_name: str, step: str):
    """
    返回按 config/agents 配置的 OpenAI 兼容 client。
    供 file-extract（files.create + chat）等需直接调 API 的场景。
    """
    m = get_model_for_step(agent_id, task_name, step)
    provider = m.get("provider") or "qwen"
    model = m.get("model") or "qwen-long"
    tup = _PROVIDER_ENV.get(provider) or _PROVIDER_ENV.get("qwen")
    key_env, url_env, default_url = tup
    api_key = get_env(key_env)
    base_url = get_env(url_env) or default_url
    if not api_key:
        return None
    try:
        from openai import OpenAI
        return OpenAI(api_key=api_key, base_url=base_url)
    except Exception:
        return None


# LLM 调用超时（秒），长文本如公式校验、论文提取需较高值，避免卡壳
LLM_CALL_TIMEOUT = 180.0


def _do_llm_call(
    api_key: str,
    base_url: str,
    model: str,
    messages: List[Dict[str, str]],
    temperature: float,
    timeout: float = LLM_CALL_TIMEOUT,
) -> str:
    """发起 chat.completions.create，返回 content 或空字符串。"""
    if not api_key:
        return ""
    try:
        from openai import OpenAI
        c = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
        r = c.chat.completions.create(model=model, messages=messages, temperature=temperature)
        return (r.choices[0].message.content or "").strip()
    except Exception:
        return ""


def invoke_model(
    agent_id: str,
    task_name: str,
    step: str,
    messages: List[Dict[str, str]],
    *,
    temperature: float = 0.2,
) -> str:
    """
    根据 agent_id + task_name + step 获取 provider/model，从 .env 取 api_key/base_url，
    发起 chat.completions.create；失败时回退 qwen 系列。
    返回：assistant 消息的 content 字符串。
    """
    m = get_model_for_step(agent_id, task_name, step)
    provider = m.get("provider") or "qwen"
    model = m.get("model") or "qwen-long"
    tup = _PROVIDER_ENV.get(provider) or _PROVIDER_ENV.get("qwen")
    key_env, url_env, default_url = tup
    api_key = get_env(key_env)
    base_url = get_env(url_env) or default_url

    result = _do_llm_call(api_key, base_url, model, messages, temperature, timeout=LLM_CALL_TIMEOUT)
    if result:
        return result
    # 回退 qwen
    qwen_key, qwen_url_env, qwen_default = _PROVIDER_ENV["qwen"]
    qwen_api_key = get_env(qwen_key)
    qwen_base = get_env(qwen_url_env) or qwen_default
    for fm in ["qwen-long", "qwen-plus", "qwen-turbo"]:
        r = _do_llm_call(qwen_api_key, qwen_base, fm, messages, temperature, timeout=LLM_CALL_TIMEOUT)
        if r:
            return r
    return ""


def get_task_config(agent_id: str, task_name: str) -> Dict[str, Any]:
    """
    获取 (agent_id, task_name) 对应的任务配置（prompt 文件名等）。
    task_name: paper_ingest | parameter_recommendation | project_proposal | writing
    """
    tasks_file = CONFIG_TASKS_DIR / f"{task_name}.json"
    data = _load_json(tasks_file)
    cfg = data.get(agent_id) or data.get("_default") or {}
    return dict(cfg)


def _read_prompt_file(agent_id: str, file_name: str, format_vars: Dict[str, Any]) -> str:
    """读取指定 agent 下的 prompt 文件并应用 format_vars。"""
    name = file_name if file_name.endswith(".txt") else f"{file_name}.txt"
    path = CONFIG_PROMPTS_DIR / agent_id / name
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8")
    if format_vars:
        try:
            text = text.format(**format_vars)
        except KeyError:
            pass
    return text.strip()


def get_prompt(agent_id: str, prompt_key: str, task_name: Optional[str] = None, **format_vars: Any) -> str:
    """
    加载 prompt 模板内容，统一采用 agent_specific + default_base 拼接策略。

    若 task_name 给定，则从 tasks/<task_name>.json 解析 prompt_key 对应的文件名。
    prompt_key: 如 extraction_s1, extraction_s2, figure_caption, prompt, hint
    format_vars: 用于 str.format() 的变量，如 page_index, param_summary_text

    拼接规则：当 agent_id != "_default" 且 agent 与 _default 均存在时，
    返回 agent_specific + "\\n\\n" + default_base；否则返回存在的优先内容。
    """
    if task_name:
        task_cfg = get_task_config(agent_id, task_name)
        file_name = task_cfg.get(prompt_key) or task_cfg.get("prompt") or task_cfg.get("hint")
    else:
        file_name = prompt_key if prompt_key.endswith(".txt") else f"{prompt_key}.txt"

    if not file_name:
        return ""

    default_content = _read_prompt_file("_default", file_name, format_vars)
    if agent_id == "_default":
        return default_content

    agent_content = _read_prompt_file(agent_id, file_name, format_vars)
    if agent_content and default_content:
        return agent_content + "\n\n" + default_content
    if agent_content:
        return agent_content
    return default_content


def get_parameter_recommendation_system_prompt(agent_id: str) -> str:
    """
    获取参数推荐任务使用的系统提示词。通过 get_prompt 统一拼接 agent_specific + default_base。
    若无模板则返回兜底文案。
    """
    out = get_prompt(agent_id, "parameter_recommendation_system")
    if out:
        return out
    return "你是通用学术参数与方法推荐专家。请根据文献与用户需求给出关键量推荐及方法推荐。请直接输出JSON，不要解释。"


def get_memorize_override_config(agent_id: str, task_name: str) -> Dict[str, Any]:
    """
    获取某任务在 memU memorize 时使用的 override_config（memory_types + memory_categories）。
    从 memu_scenarios[agent_id].tasks[task_name] 读取 memory_types，categories 用 agent 顶层或 _default。
    """
    scenarios = load_scenarios()
    agent_cfg = scenarios.get(agent_id) or scenarios.get("_default") or {}
    tasks = agent_cfg.get("tasks") or {}
    task_cfg = tasks.get(task_name) or {}
    memory_types = task_cfg.get("memory_types") or agent_cfg.get("memory_types") or ["knowledge"]
    memory_categories = agent_cfg.get("memory_categories") or (scenarios.get("_default") or {}).get("memory_categories") or []
    return {
        "memory_types": memory_types,
        "memory_categories": memory_categories,
    }


def _get_intent_client():
    """意图识别使用 DashScope（qwen 系列）；可选后续扩展 OpenRouter。"""
    key = get_env("DASHSCOPE_API_KEY")
    if not key:
        return None
    try:
        from openai import OpenAI
        return OpenAI(api_key=key, base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")
    except Exception:
        return None


def intent_to_agent_ids(
    input_text: str = "",
    file_path: Optional[str] = None,
    file_name: Optional[str] = None,
) -> List[str]:
    """
    根据用户输入或文件名做意图识别，返回应使用的 agent_id 列表。
    全面采用小模型 API（qwen 系列），无关键词规则。模型不可用或解析失败时返回 ["_default"]。
    """
    scenarios = load_scenarios()
    allowed = {k for k in scenarios if k != "_comment" and not k.startswith("_")}
    allowed.add("_default")

    # 优先使用真实内容做意图识别；仅当 input_text 为空且 file_path 提供时，
    # 尝试从文件中截取一小段。PDF 为二进制，read_text 会失败或得乱码，故跳过，仅用文件名。
    text = (input_text or "").strip()
    if not text and file_path:
        p = Path(file_path)
        if p.suffix.lower() != ".pdf":
            try:
                raw = p.read_text(encoding="utf-8", errors="ignore")
                lines = raw.splitlines()
                text_snippet = "\n".join(lines[:80])[:2000].strip()
                if text_snippet:
                    text = text_snippet
            except Exception:
                pass

    name = (file_name or (Path(file_path).name if file_path else "") or "").strip()
    user_input_parts: List[str] = []
    if text:
        user_input_parts.append(f"用户输入/摘要片段: {text}")
    if name:
        user_input_parts.append(f"文件名: {name}")
    user_input = "\n".join(user_input_parts).strip()
    if not user_input:
        return ["_default"]

    system_path = CONFIG_PROMPTS_DIR / "intent_classification_system.txt"
    system_prompt = system_path.read_text(encoding="utf-8") if system_path.exists() else (
        "你是一个学术任务意图分类器。根据用户输入或文件名，判断应使用的领域 agent。"
        "可选 agent_id：physics_agent、cs_agent、chemistry_agent、biology_agent、math_agent、_default。"
        "只输出一个 JSON：{\"agent_ids\": [\"agent_id1\"]}，不要其他文字。"
    )
    model = get_env("INTENT_MODEL", INTENT_MODEL_DEFAULT)

    client = _get_intent_client()
    if not client:
        return ["_default"]

    try:
        r = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input},
            ],
            temperature=0.1,
        )
        raw = (r.choices[0].message.content or "").strip()
    except Exception:
        return ["_default"]

    # 解析 JSON：允许 {"agent_ids": ["physics_agent"]} 或 代码块内 JSON
    if "```" in raw:
        raw = re.sub(r"^.*?```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```.*$", "", raw)
    raw = raw.strip()
    m = re.search(r"\{[^{}]*\"agent_ids\"[^{}]*\}", raw)
    if m:
        raw = m.group(0)
    try:
        data = json.loads(raw)
        ids = data.get("agent_ids") or []
        if not isinstance(ids, list):
            ids = [ids] if ids else []
        ids = [str(x).strip() for x in ids if x]
        # 去重且校验为允许的 agent_id
        seen = set()
        out = []
        for aid in ids:
            if aid not in allowed:
                continue
            if aid not in seen:
                seen.add(aid)
                out.append(aid)
        if out:
            return out
    except (json.JSONDecodeError, TypeError):
        pass
    return ["_default"]


def list_agent_ids() -> List[str]:
    """从 memu_scenarios.json 的 agent_ids 字段读取；若无则回退到遍历排除 _comment 等。"""
    scenarios = load_scenarios()
    ids = scenarios.get("agent_ids")
    if isinstance(ids, list):
        return [str(x) for x in ids if x and str(x) != "_comment"]
    return [k for k in scenarios if k != "_comment" and not str(k).startswith("_")]
