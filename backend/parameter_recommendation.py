# backend/parameter_recommendation.py
"""
参数推荐：多 agent 记忆检索 → 按 agent 模板组装 prompt → 调用大模型 → 返回推荐区间与力场。
不依赖本地 FAISS；relevant_forces 可传空或由调用方从本地 RAG 传入。
支持将推荐结果写入 summary.md 和 recommendations.json。
"""

import json
from typing import Any, Dict, List, Optional

from .agent_config import (
    get_prompt,
    get_parameter_recommendation_system_prompt,
    intent_to_agent_ids,
    invoke_model,
)


def run_parameter_recommendation(
    structured_paper: Dict[str, Any],
    user_params: Dict[str, Any],
    user_id: str,
    agent_id: Optional[str] = None,
    agent_ids: Optional[List[str]] = None,
    memory_context: str = "",
    relevant_forces: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    根据结构化论文与用户参数需求，结合多 agent 记忆与模板，返回参数推荐与力场推荐。
    user_params 应包含 expected_phenomena 及若干参数名 -> 描述/单位 等。
    """
    print(f"[PARAM_REC] run_parameter_recommendation 入口 | user_id={user_id} agent_id={agent_id} agent_ids={agent_ids}", flush=True)
    if agent_ids is None and agent_id is None:
        md = structured_paper.get("metadata") or {}
        ctx_parts = [
            md.get("title", ""),
            structured_paper.get("observed_phenomena", ""),
            structured_paper.get("simulation_results_description", ""),
            structured_paper.get("methodology", ""),
            user_params.get("expected_phenomena", ""),
        ]
        memory_query = " ".join(str(x) for x in ctx_parts if x)[:500]
        agent_ids = intent_to_agent_ids(input_text=memory_query)
        print(f"[PARAM_REC] 意图识别 | agent_ids={agent_ids}", flush=True)
    if agent_ids is None:
        agent_ids = [agent_id] if agent_id else ["_default"]
    if not agent_ids:
        agent_ids = ["_default"]
    aid = agent_ids[0]

    # memory_context 由 app_backend 传入（从 memU 检索得到）

    relevant_forces = relevant_forces or []
    # 空字段用占位符，避免 LLM 误判为「均未提供」而返回信息缺失
    observed_phenomena = (structured_paper.get("observed_phenomena") or "").strip() or "（无）"
    simulation_results_description = (structured_paper.get("simulation_results_description") or "").strip() or "（无）"
    user_params_clean = {k: v for k, v in user_params.items() if k != "expected_phenomena"}
    expected_phenomena = (user_params.get("expected_phenomena") or "").strip() or "（无）"

    # get_prompt 已统一实现 agent_specific + default_base 拼接，此处直接调用即可
    prompt_template = get_prompt(aid, "prompt", task_name="parameter_recommendation") or ""
    if not prompt_template:
        return {
            "error": "未找到 parameter_recommendation 模板",
            "agent_id_used": aid,
            "parameter_recommendations": {},
            "force_field_recommendation": {},
        }

    try:
        filled = prompt_template.format(
            structured_paper_json=json.dumps(structured_paper, ensure_ascii=False, indent=2),
            relevant_forces_json=json.dumps(relevant_forces, ensure_ascii=False, indent=2),
            observed_phenomena=observed_phenomena,
            simulation_results_description=simulation_results_description,
            user_params_json=json.dumps(user_params_clean, ensure_ascii=False, indent=2),
            expected_phenomena=expected_phenomena,
            memory_context=memory_context,
        )
    except KeyError:
        filled = prompt_template.replace("{memory_context}", memory_context)

    system_prompt = get_parameter_recommendation_system_prompt(aid)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": filled},
    ]
    print(f"[PARAM_REC] 调用模型 | agent_id={aid}", flush=True)
    raw = invoke_model(aid, "parameter_recommendation", "main", messages, temperature=0.2)
    if not raw:
        print(f"[PARAM_REC] 失败 | 模型返回空", flush=True)
        return {"error": "模型调用失败", "agent_id_used": aid, "parameter_recommendations": {}, "force_field_recommendation": {}}

    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0].strip()
    try:
        data = json.loads(raw)
        rec_count = len(data.get("parameter_recommendations") or {})
        print(f"[PARAM_REC] 完成 | agent_id={aid} parameter_recommendations_count={rec_count}", flush=True)
        return {
            "agent_id_used": aid,
            "parameter_recommendations": data.get("parameter_recommendations", {}),
            "force_field_recommendation": data.get("force_field_recommendation", {}),
            "raw_response": raw,
            "memory_context_used": len(memory_context),
        }
    except json.JSONDecodeError:
        print(f"[PARAM_REC] 失败 | JSON 解析错误 raw_preview={raw[:200] if raw else ''}", flush=True)
        return {"error": "模型返回非合法 JSON", "agent_id_used": aid, "raw_response": raw[:500], "parameter_recommendations": {}, "force_field_recommendation": {}}
