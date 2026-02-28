# Display Formats 配置

按 `agent_id` 配置各场景的展示模板，**不可写死**。各 agent 的 prompt 输出结构决定展示字段，本目录的 JSON 控制展示顺序、折叠策略等。

## 目录结构

```
display_formats/
├── _default/          # 兜底配置
├── physics_agent/
├── biology_agent/
├── chemistry_agent/
├── cs_agent/
└── math_agent/
```

每个 agent 目录下：
- `paper.json`：场景一论文展示（对应 `prompts/<agent>/paper_extraction_s1.txt` 输出）
- `parameter_recommendation.json`：场景三参数推荐展示（对应 `parameter_recommendation.txt`）

## 配置与 Prompt 对应

| agent_id | paper 字段来源 | 说明 |
|----------|----------------|------|
| _default | metadata, methodology, keywords, figures | 通用论文 |
| physics_agent | physics_context, observed_phenomena, parameters, force_fields | 物理 |
| biology_agent | experimental_subject, biomolecules, assay_methods, results_summary | 生命科学 |
| chemistry_agent | reaction_scheme, reagents, conditions, analytical_methods | 化学/材料 |
| cs_agent | algorithm_description, system_architecture, dataset_or_evaluation | 计算机科学 |
| math_agent | core_definitions, main_theorems, important_formulas | 数学 |

若无对应 agent 配置，则回退到 `_default`。
