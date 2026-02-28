# main.py 前后端整合设计方案

> **已实施**。详见 [README.md](README.md)。

---

## 一、目标概述

在 `merge_project` 下新增 `main.py` 作为统一入口，将 `front/app.py`（Gradio 前端）与 `backend/app_backend.py`（AppBackend）打通，实现四场景的完整前后端对接。

核心要求：
1. **场景一**：论文上传、用户输入正确传入；论文正确展示；不同 agent_id 对应不同展示格式
2. **场景二**：数据和用户 query 正确传入；最终结果正确展示
3. **场景三**：用户 query 和模拟参数正确传入；支持按 agent_id 的展示格式
4. **场景四**：搜索到记录后，根据记录的 scene 调用对应场景的阅读器展示
5. **agent_id**：每条工作记录均有 `agent_id`，便于后续配置管理（DB 已满足）

---

## 二、main.py 结构

```
merge_project/
├── main.py                    # 统一入口
├── front/
│   └── app.py                 # UI 与渲染函数，由 main 调用并注入后端
├── backend/
│   └── app_backend.py         # API
├── config/
│   └── display_formats/       # 按 agent_id 的展示配置
│       ├── _default/
│       │   ├── paper.json
│       │   └── parameter_recommendation.json
│       ├── physics_agent/
│       └── ...
```

**main.py 职责**：
- 初始化 `AppBackend`（含 user_id、agent_id 默认值）
- 调用 `front.app.build_ui()` 获取 Gradio demo
- 将后端 API 绑定到前端事件
- `if __name__ == "__main__"`: 直接 `demo.launch(...)`

---

## 三、场景一：论文分析

| 前端组件 | 后端 API | 说明 |
|----------|----------|------|
| `upload` (gr.File) | `paper_ingest_pdf(file_path, user_input, agent_ids)` | 取上传文件 path |
| `parse_btn.click` | `app.paper_ingest_pdf(...)` | 同步调用；返回 `{agent_ids, results}` |

## 四、场景二：科研写作

| 前端组件 | 后端 API | 说明 |
|----------|----------|------|
| `write_btn.click` | `app.run_paper_generation(...)` 异步 | 流式进度 → 最终 PDF/SUMMARY |
| `data_files` | `data_file_names` | 附件路径列表 |

## 五、场景三：参数推荐

| 前端组件 | 后端 API |
|----------|----------|
| `recom_btn.click` | `app.parameter_recommendation(...)` |

## 六、场景四：记忆查询

| 前端组件 | 后端 API |
|----------|----------|
| `search_btn` | `memu_match_and_resolve` |
| `view_btn` | 按 record.scene 加载对应阅读器 |

---

**完整设计** 见 [DESIGN_ARCHITECTURE.md](DESIGN_ARCHITECTURE.md)、[FRONTEND_DESIGN.md](FRONTEND_DESIGN.md)。
