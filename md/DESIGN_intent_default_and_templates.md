# 设计规划：意图优先、默认模板与多领域通用化

## 一、现状与问题

### 1.1 默认配置偏向物理

- **parameter_recommendation.py**：`agent_ids` 默认 `["physics_agent"]`，`aid = "physics_agent"`；系统提示词写死「精通复杂等离子体物理和数值算法」。
- **agent_config.intent_to_agent_ids**：无匹配时返回 `["physics_agent"]`，应为 `["_default"]`。
- **paper_ingest**：提取失败或未指定 agent 时依赖的兜底 prompt 仍含 `physics_context`、`parameters`、`force_fields` 等物理字段。

### 1.2 意图识别过于狭隘

- 当前为**关键词匹配**（等离子、算法、代码等），精确但覆盖有限。
- 需要**小模型 API**（如 qwen 系列）对用户输入/文件名做意图分类，输出 `agent_id` 列表，便于多领域与联合检索。

### 1.3 论文提取与入库的领域绑定

- **paper_ingest** 中 conversation/summary 写死「观察现象」「模拟结果」「物理参数」等，仅适合物理域。
- 通用场景应使用**所有论文共有字段**（题目、作者、摘要、创新点、方法等）；领域 agent（如 physics_agent、cs_agent）在共有字段之上**扩展**领域字段（如物理：物理背景、力场；CS：计算架构、数学方法）。

### 1.4 参数推荐与记忆使用策略未区分

- 未区分「意图明确」与「意图不明确」：
  - **意图明确**：应用意图识别得到的 `agent_id`，拉取 MemU 多 agent 记忆，用长上下文模型（如 qwen-max / OpenRouter Gemini）整合后做推荐。
  - **意图不明确**：使用 **_default** 模板，**不依赖 MemU 记忆**，仅凭云端模型训练数据做推荐；但仍为本次任务在 MemU 上开辟 `_default` 空间做**工作记录与查询**。

---

## 二、目标架构原则

1. **意图优先**：任何任务（论文入库、参数推荐、写作提示等）都先做意图识别 → 得到 `agent_id` 列表 → 再选模板与后续逻辑。
2. **默认通用**：默认使用 `_default` 模板与 agent，不假定物理或任何单一领域。
3. **模板分层**：
   - **_default**：所有论文/任务共有的最小结构（题目、作者、摘要、创新点、方法等）；参数推荐为「关键量 + 方法/模型推荐」的通用表述。
   - **领域 agent**（physics_agent、cs_agent 等）：在 _default 基础上增加领域字段与领域话术。
4. **记忆使用策略**：
   - 意图明确 → 用 MemU 多 agent 记忆 + 长上下文模型整合推荐。
   - 意图不明确 → 不用 MemU 记忆做推荐，仅用 _default 模板 + 云端模型；但仍写入 MemU（_default）做记录与检索。

---

## 三、模块设计

### 3.1 意图识别（agent_config.intent_to_agent_ids）

| 项目 | 设计 |
|------|------|
| **输入** | `input_text`、可选 `file_path` / `file_name` |
| **方式** | 内置**小模型 API**（qwen 系列，如 qwen-turbo / qwen-plus），将输入整合成一段描述后请求模型做多标签分类或结构化输出。 |
| **输出** | `List[str]`：`agent_id` 列表，如 `["physics_agent"]`、`["physics_agent","cs_agent"]`、`["_default"]`。 |
| **兜底** | 模型不可用或解析失败时返回 `["_default"]`，**不再**返回 `["physics_agent"]`。 |
| **实现要点** | 调用 DashScope/OpenAI 兼容接口；prompt 要求输出固定格式（如 JSON `{"agent_ids": ["physics_agent"]}`），解析后去重、校验为 config 中已存在的 agent_id，非法则替换为 `_default`。 |

可选：保留**关键词规则**作为快速路径（命中则直接返回，不调模型），未命中再调小模型；或完全由模型负责，便于扩展更多领域。

### 3.2 配置与模板结构（config）

| 项目 | 设计 |
|------|------|
| **memu_scenarios.json** | 保持 `_default` 与各领域 agent；确保 `_default` 的 `tasks`、`memory_categories` 等完整，供「意图不明确」时使用。 |
| **tasks/*.json** | 各 task（paper_ingest、parameter_recommendation 等）均提供 `_default` 与各 agent 的 prompt 文件名；优先使用 `agent_id`，缺失时用 `_default`。 |
| **prompts/_default/** | |
| - **论文提取** | **通用字段**：`metadata`（title, authors, journal, year, abstract, innovation）, `methodology`, `keywords`, `figures`（id, caption, page）。**不包含** physics_context、observed_phenomena、force_fields、parameters 等物理专属字段。 |
| - **paper_extraction_s1/s2** | 标签与 JSON schema 仅含上述通用字段；s2 的 JSON 结构为通用结构。 |
| - **parameter_recommendation** | 通用话术：「关键量推荐区间与理由 + 方法/模型推荐」，占位符与 _default 的 JSON 结构一致（可定义如 `key_quantities`、`method_recommendation`），不写死「力场」「物理参数」。 |
| **prompts/physics_agent/** | 在 _default 基础上**扩展**：增加 physics_context、observed_phenomena、simulation_results_description、parameters、force_fields 等；parameter_recommendation 保留「力场」「参数」等物理话术。 |
| **prompts/cs_agent/**（若存在） | 扩展：计算架构、数学方法、算法描述等。 |

这样：**意图不明确 → 使用 _default 模板（仅通用字段）**；**意图明确为某领域 → 使用该 agent 模板（通用 + 领域扩展）**。

### 3.3 论文入库（paper_ingest）

| 项目 | 设计 |
|------|------|
| **入口** | `paper_ingest_pdf(file_path, user_id, agent_ids=None, ...)` |
| **agent_ids 决定** | 若调用方未传 `agent_ids`，则调用 `intent_to_agent_ids(file_path=..., file_name=...)`；若得到 `["_default"]` 或空，则使用 `["_default"]`。 |
| **按 agent 循环** | 对每个 `aid`（含 _default）：用 **get_prompt(aid, extraction_s1/s2, task_name="paper_ingest")** 取模板；若缺失则用 _default 的模板。 |
| **提取阶段** | 使用 `aid` 对应模板做两阶段提取；**不再**在代码里写死「物理参数」「模拟结果」等，全部由模板和 task 配置驱动。 |
| **conversation/summary** | 由**模板 + 提取结果**驱动：summary_pieces 只使用 **structured** 里实际存在的字段做拼接（如 metadata.title, metadata.innovation, methodology, 以及若存在则 physics_context、observed_phenomena 等）；对 _default 仅用通用字段生成 summary，避免出现「模拟结果」「物理参数」等内置词。可设计一档「通用 summary 模板」：仅列出 metadata、methodology、innovation、keywords；领域 agent 可再追加领域字段。 |
| **MemU 与本地 DB** | 不论 _default 还是领域 agent，都正常执行 memorize 与 insert_record，保证工作记录可查。 |

这样：**意图不明确 → agent_ids = ["_default"] → 使用 _default 提取模板与通用 summary**；**意图明确 → agent_ids = [physics_agent] 等 → 使用领域模板与扩展 summary**。

### 3.4 参数推荐（parameter_recommendation）

| 项目 | 设计 |
|------|------|
| **入口** | `run_parameter_recommendation(structured_paper, user_params, user_id, agent_id=None, agent_ids=None, ...)` |
| **agent 决定** | 若调用方未传 `agent_ids`/`agent_id`，先对当前「上下文」做意图识别（例如用 `structured_paper` 的 metadata.title + observed_phenomena + user_params 拼一段 text）调用 `intent_to_agent_ids(input_text=...)`；若得到 `["_default"]` 或空，则 `agent_ids = ["_default"]`。 |
| **记忆策略** | 若 `agent_ids == ["_default"]`：**不使用 MemU 记忆**（memory_context 置空或跳过 get_memory_context_for_agents），仅用 _default 模板 + 云端模型做推荐；若为具体领域 agent，则照常拉取 MemU 多 agent 记忆并拼接。 |
| **模板选择** | `get_prompt(aid, "prompt", task_name="parameter_recommendation")`，其中 aid 为 agent_ids[0]；保证 _default 有对应 parameter_recommendation.txt，且占位符与通用结构一致。 |
| **系统提示词** | **不再写死物理**：按 agent_id 选择系统提示词——_default 为「通用学术参数与方法推荐专家」；physics_agent 为「精通复杂等离子体物理与数值算法」等。可在 config 中为每个 agent 增加可选字段如 `system_prompt_for_parameter_recommendation`，或单独 prompt 文件，由 agent_config 读取。 |
| **模型选择** | 意图明确且需整合多 agent 记忆时，可用**长上下文模型**（如 qwen-max）或 OpenRouter 的 Gemini；意图不明确且无记忆时，用现有 qwen-long 即可。具体模型名可配置（如 config 或 env）。 |

### 3.5 其他调用点统一

- **app_backend** 中所有「未指定 agent 时默认 physics_agent」改为默认 **`_default`**（或先意图识别再定 agent）。
- **list_agent_ids()** 是否包含 `_default`：建议返回给前端的列表**不包含** `_default`（仅展示领域 agent），内部逻辑仍使用 `_default` 作为兜底 agent_id。

---

## 四、数据流小结

1. **论文入库**  
   用户上传 PDF →（可选）意图识别 → 得到 agent_ids（可为 _default）→ 按 agent 使用对应提取模板 → 通用/领域 summary → MemU memorize + 本地 DB。

2. **参数推荐**  
   用户/上游提供 structured_paper + user_params → 若未指定 agent则意图识别 → agent_ids；  
   - 若为 _default：memory_context 为空，用 _default 模板 + 通用系统提示 + 云端模型 → 推荐结果；结果仍可写入 MemU（_default）做记录。  
   - 若为领域 agent：拉取 MemU 多 agent 记忆 → 用领域模板 + 领域系统提示 + 长上下文模型 → 推荐结果。

3. **意图识别**  
   输入（文本/文件名）→ 小模型 API → 解析得到 agent_id 列表 → 校验与兜底（含 _default）→ 供后续模板与记忆策略使用。

---

## 五、配置与文件变更清单（建议）

| 类型 | 路径/内容 |
|------|------------|
| 新增 | `config/prompts/_default/paper_extraction_s1.txt`（通用字段标签，无物理专属） |
| 新增 | `config/prompts/_default/paper_extraction_s2.txt`（通用 JSON schema） |
| 新增 | `config/prompts/_default/parameter_recommendation.txt`（通用关键量+方法推荐，占位符与通用结构一致） |
| 可选 | `config/intent_prompt.txt` 或 agent_config 内嵌：小模型意图分类的 system/user prompt 与输出格式说明 |
| 可选 | `config/tasks/paper_ingest.json` 中为 _default 明确指定通用提取 prompt 文件名 |
| 可选 | 各 agent 的「参数推荐系统提示」可放入 `config/prompts/<agent_id>/parameter_recommendation_system.txt` 或由 tasks 引用 |
| 代码 | agent_config：intent_to_agent_ids 改为小模型 API + 兜底 _default；list_agent_ids 保持不含 _default（或按产品需求） |
| 代码 | paper_ingest：agent_ids 默认由 intent_to_agent_ids 决定；summary/conversation 由 structured 与 agent 类型驱动，无物理内置词 |
| 代码 | parameter_recommendation：默认 agent 为 _default；_default 时不拉 MemU 记忆；系统提示与模板按 agent_id 选择 |
| 代码 | app_backend：所有默认 agent 改为 _default 或意图识别结果 |

---

## 六、实现阶段建议

1. **Phase 1**：配置与模板  
   - 新增/改写 _default 的 paper_extraction_s1/s2、parameter_recommendation（通用字段与话术）。  
   - 确保 tasks 与 memu_scenarios 中 _default 完整。

2. **Phase 2**：意图识别  
   - 实现小模型调用与解析；intent_to_agent_ids 返回 _default 兜底；保留或移除关键词规则二选一。

3. **Phase 3**：paper_ingest 与 parameter_recommendation 逻辑  
   - 默认 agent 与模板选择改为 _default/意图；summary 通用化；参数推荐分支「_default 无记忆 / 领域 agent 有记忆」及系统提示按 agent 选择。

4. **Phase 4**：app_backend 与长上下文/OpenRouter（可选）  
   - 统一默认 agent；可选接入 qwen-max / OpenRouter 用于多 agent 记忆整合。

---

请您确认以上设计与阶段划分是否符合预期，确认后再按此方案进行代码修改。若需要调整（例如意图识别是否保留关键词、_default 是否对前端可见等），可指出具体条目。
