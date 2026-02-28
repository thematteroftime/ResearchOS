# 配置说明 (Config)

本目录与 **DESIGN_ARCHITECTURE.md** 附录 A 对齐，作�?merge_project 的配置约定摘要�?

## 目录结构

- **prompts/**  
  - `intent_classification_system.txt`：意图识别系统提示词，输�?JSON `{"agent_ids": [...]}`�? 
  - `formula_verification.txt`：PyMuPDF 提取文本的公式校验提示词（前处理，与 intent 同级）�? 
  - `<agent_id>/`：各领域 agent �?prompt 文件�? 
    - 论文分析：`paper_extraction_s1.txt`、`paper_extraction_s2.txt`、`paper_figure_caption.txt`、`user_input_memory_fusion.txt`、`paper_final_summary.txt`�? 
    - 写作：`writing_user_fusion.txt`、`writing_hint.txt`（可选）；query 规范化由 agent_config.invoke_model(agent_id, "writing", "query_normalize", ...) �?writer.normalize_query 完成�? 
    - 参数推荐：`parameter_recommendation.txt`、`parameter_recommendation_system.txt`�? 
    - 项目提议：`project_proposal.txt`�? 
  - 未配置的 agent 使用 `_default` 下同名文件兜底�?

- **tasks/**  
  - `paper_ingest.json`：各 agent �?extraction_s1、extraction_s2、figure_caption 等键名�? 
  - `parameter_recommendation.json`、`project_proposal.json`、`writing.json`：对应任务的 prompt 键名（prompt / hint）�?

- **agents/**（可选）  
  - `<agent_id>.json`：各场景步骤�?provider、model 配置；供 agent_config.get_model_for_step、invoke_model 使用�?

- **memu_scenarios.json**  
  - 每个 agent_id：`memory_types`、`memory_categories`、`tasks`（paper_ingest、project_proposal、parameter_recommendation、writing）、`retrieve`（method、item/category/resource �?top_k、enabled）�? 
  - memorize 时通过 `get_memorize_override_config(agent_id, task_name)` �?override_config�?

## 环境变量

完整列表与说明见项目根目�?**.env.example** �?**ENV_CONFIG.md**�? 
关键变量：`ANTHROPIC_API_KEY`（写作必填）、`DASHSCOPE_API_KEY`（入�?参数推荐）、`MEMU_BACKEND`、`MEMU_*`、`INTENT_MODEL`、`CONTEXT_MODEL`、`OPENROUTER_*` 等�?
