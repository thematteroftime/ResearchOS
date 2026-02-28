# 变更说明：意图优先、默认 _default、cs_agent 与测试完善

## 一、配置与模板

### 1. 默认模板（_default）
- **config/prompts/_default/paper_extraction_s1.txt**：重写为通用字段（metadata.title, authors, journal, year, abstract, innovation, methodology, keywords, figures），无物理专属字段。
- **config/prompts/_default/paper_extraction_s2.txt**：通用 JSON 结构（metadata, methodology, keywords, figures）。
- **config/prompts/_default/parameter_recommendation.txt**：通用「关键量 + 方法/模型推荐」话术。
- **config/prompts/_default/parameter_recommendation_system.txt**：通用系统提示词。

### 2. cs_agent 模板（新增）
- **config/prompts/cs_agent/**：paper_extraction_s1.txt, paper_extraction_s2.txt（通用 + algorithm, system.architecture, implementation, dataset_or_evaluation）, parameter_recommendation.txt, parameter_recommendation_system.txt, project_proposal.txt。
- **config/tasks/paper_ingest.json、parameter_recommendation.json、project_proposal.json**：增加 cs_agent 条目。

### 3. 意图分类
- **config/prompts/intent_classification_system.txt**：小模型意图分类的 system prompt（输出 JSON agent_ids）。

### 4. 环境与常量
- **backend/config.py**：INTENT_MODEL_DEFAULT="qwen-turbo", CONTEXT_MODEL_DEFAULT="qwen-long", OPENROUTER_HIGH_TIER_MODEL。
- **.env.example**：INTENT_MODEL、可选 OPENROUTER 高阶模型说明。

---

## 二、后端逻辑

### 1. agent_config.py
- **intent_to_agent_ids**：移除全部关键词规则，改为仅调用小模型 API（DashScope qwen）。输入整合为「用户输入 + 文件名」后请求模型，解析 JSON `{"agent_ids": [...]}`，校验为 scenarios 中允许的 agent_id，否则返回 `["_default"]`。空输入或 API 不可用/解析失败时返回 `["_default"]`。
- **get_parameter_recommendation_system_prompt(agent_id)**：按 agent 读取 parameter_recommendation_system.txt，无则 _default，再无则硬编码通用文案。
- **list_agent_ids()**：仍不包含 _default（仅领域 agent）。

### 2. paper_ingest.py
- **agent_ids**：若为 None 则调用 intent_to_agent_ids(file_path=..., file_name=...)；若为空则用 `["_default"]`。
- **extract_paper_structure**：兜底 extraction_s1/s2 为通用话术（无「力场」「物理参数」）；default_structure 改为仅通用字段（metadata, methodology, keywords, figures），领域字段由模型/模板返回后合并。
- **conversation/summary**：由 structured 实际字段驱动；通用部分（文件、创新点、摘要、方法、关键词）+ 若有则现象/模拟描述；assistant 回复改为「我已阅读并理解该论文的核心内容。」

### 3. parameter_recommendation.py
- **agent 决定**：未传 agent_ids/agent_id 时，用 structured_paper + user_params 拼 context 调用 intent_to_agent_ids，得到 agent_ids；否则用传入或 `["_default"]`。aid = agent_ids[0]。
- **_default 不拉记忆**：当 aid == "_default" 时 memory_context = ""，不调用 get_memory_context_for_agents；否则照常多 agent 记忆检索。
- **系统提示词**：使用 get_parameter_recommendation_system_prompt(aid)，不再写死物理话术。
- **返回**：增加 `agent_id_used` 便于测试与日志。

### 4. app_backend.py
- **project_proposal_optimize**：agent_ids 为 None 时调用 intent_to_agent_ids(user_idea)；空则 `["_default"]`；hint 用 agent_ids[0]。

### 5. memu_client.py
- **默认 agent_id**：由 "merge_agent" 改为 "_default"（当未传且无 MEMU_AGENT_ID 时）。

---

## 三、测试

### 1. 任务调用中打印 agent_id
- **test_parameter_recommendation**：log.log_step("agent_id_used", out.get("agent_id_used"))。
- **test_app_backend_parameter_recommendation**：同上。
- **test_paper_ingest**：test_paper_ingest_pdf_with_txt 与 test_paper_ingest_pdf_intent_driven_agent_ids 中打印/断言 agent_ids。

### 2. 意图与 cs_agent
- **test_agent_config**：test_intent_to_agent_ids 改为接受 API 返回或 _default；空输入断言 `["_default"]`。新增 test_get_parameter_recommendation_system_prompt、test_cs_agent_prompts。
- **test_parameter_recommendation**：新增 test_run_parameter_recommendation_default_agent（_default、agent_id_used）、test_get_memory_context_multi_agent（physics_agent + cs_agent）。

### 3. retrieve 与全流程
- **test_app_backend_api**：新增 test_app_backend_memu_retrieve，按 physics_agent / cs_agent / _default 调用 memu_retrieve 并打印 agent_id。
- **test_memu_client_api**：新增 test_memu_retrieve_by_agent_id，对三档 agent_id 调用 retrieve 并打印。
- **test_paper_ingest**：新增 test_paper_ingest_pdf_intent_driven_agent_ids（agent_ids=None 时意图识别得到 agent_ids 并打印）。
- **test_full_flow_integration**：上述新用例全部纳入 run_all_module_tests。

---

## 四、如何跑测试

在项目根目录（merge_project）执行：

```bash
python tests/test_full_flow_integration.py
```

或按模块：

```bash
python tests/test_agent_config.py
python tests/test_parameter_recommendation.py
python tests/test_app_backend_api.py
python tests/test_memu_client_api.py
python tests/test_paper_ingest.py
```

意图识别依赖 DASHSCOPE_API_KEY；未配置时 intent_to_agent_ids 会直接返回 `["_default"]`，相关测试仍可通过。
