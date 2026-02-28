# 科研学习平台 (merge_project)

多 Agent 联合分析的科研学习平台，支持论文阅读入库、科研写作、参数推荐与记忆查询。整合 **paper_web**、**claude-scientific-writer** 与 **memU**，提供四场景统一 API。

## 功能概览

| 场景 | 功能 |
|------|------|
| **论文分析** | PDF 上传 → 意图识别 → 结构化提取 → memU 记忆与本地 DB |
| **科研写作** | 用户意图 + 数据文件 → 记忆增强 → query 规范化 → PDF 生成 → writing_event 落库 |
| **参数推荐** | 结构化论文 + 期望现象 → memU 检索 → 推荐区间与力场 |
| **记忆查询** | 自然语言问题 → memU 检索 → 记录列表与源文件下载 |

## 快速开始

### 安装依赖

```bash
cd merge_project
pip install -r requirements.txt
```

### 配置环境

```bash
cp .env.example .env
# 在 .env 中按需填写 API 密钥（详见 md/SETUP_AND_SECURITY.md）
# 必填：ANTHROPIC_API_KEY（写作）、DASHSCOPE_API_KEY（论文提取/参数推荐）
# 可选：MEMU_*（记忆）、OPENROUTER_*（代理/改写）
```

### 启动应用

```bash
python main.py
# 浏览器打开 http://127.0.0.1:7860
```

## 目录结构

```
merge_project/
├── main.py                    # 统一入口
├── front/                     # Gradio 前端
│   └── app.py
├── backend/                   # 后端模块
│   ├── app_backend.py         # 统一 API 入口
│   ├── memu_client.py         # memU 记忆 + 本地 DB
│   ├── scientific_writer_client.py
│   ├── paper_ingest.py
│   ├── parameter_recommendation.py
│   └── ...
├── config/                    # prompts、tasks、display_formats
├── md/                        # 📚 文档中心（架构、配置、测试说明）
├── database/                  # memu_records.db、memu_storage
├── writing_outputs/           # 写作输出（PDF、SUMMARY、PEER_REVIEW）
├── job_records/               # 写作任务记录
├── data/                      # 数据文件
├── docs/                      # 测试用 PDF、CSV 等
├── tests/                     # 测试与日志
├── .env.example
└── requirements.txt
```

## 架构概览

```
前端 (Gradio)
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  AppBackend（唯一入口）                               │
│  意图识别、memU 检索、DB 落库、agent_id 传递           │
└─────────────────────────────────────────────────────┘
    │                │                    │
    ▼                ▼                    ▼
MemUClient    ScientificWriterClient   paper_ingest /
(cloud|oss)   (generate_paper)         parameter_recommendation
```

## 环境变量

| 变量 | 用途 | 必填 |
|------|------|------|
| `ANTHROPIC_API_KEY` | 论文生成（Claude） | 写作时必填 |
| `DASHSCOPE_API_KEY` | 论文提取、意图识别、参数推荐（Qwen） | 入库/参数推荐时必填 |
| `MEMU_API_KEY` / `MEMU_BASE_URL` | memU 云端记忆 | 记忆功能可选 |
| `MEMU_BACKEND` | `cloud`（默认）或 `oss` | 可选 |
| `OPENROUTER_API_KEY` | research-lookup、高阶模型 | 可选 |

完整说明见 [md/ENV_CONFIG.md](md/ENV_CONFIG.md)。

## 测试

```bash
# 一键全量测试（含四场景）
pip install -r requirements.txt
python tests/test_full_flow_integration.py

# 写作调用链验证
python tests/run_writing_verification.py

# 量子物理三篇论文四场景（需将 PDF 置于 data/ 或 docs/）
python tests/test_quantum_physics_three_papers.py
```

详见 [md/README_TESTS.md](md/README_TESTS.md)。

## 文档

**文档已统一迁移至 [md/](md/) 目录**：

| 文档 | 说明 |
|------|------|
| [md/README.md](md/README.md) | 文档索引 |
| [md/DESIGN_ARCHITECTURE.md](md/DESIGN_ARCHITECTURE.md) | 四场景详细设计 |
| [md/MAIN_INTEGRATION_DESIGN.md](md/MAIN_INTEGRATION_DESIGN.md) | 前后端整合方案 |
| [md/BACKEND_MODULE_DESIGN.md](md/BACKEND_MODULE_DESIGN.md) | 后端模块职责 |
| [md/FRONTEND_DESIGN.md](md/FRONTEND_DESIGN.md) | 前端设计（Perplexity 风格） |
| [md/ENV_CONFIG.md](md/ENV_CONFIG.md) | 环境变量说明 |
| [md/README_CONFIG.md](md/README_CONFIG.md) | 配置目录说明 |
| [md/README_TESTS.md](md/README_TESTS.md) | 测试说明 |

## 常见问题

- **"Error in hook callback" / "Stream closed"**：claude-agent-sdk 内部钩子报错，非本项目代码；写作任务通常已完成，可忽略。
- **ModuleNotFoundError**：执行 `pip install -r requirements.txt`。
- **写作无 PDF**：确认 `ANTHROPIC_API_KEY` 已配置。
- **memU 不可用**：未填 `MEMU_API_KEY` 时，记忆功能受限；入库、写作、参数推荐仍可运行。

## License

见项目根目录 LICENSE 文件。
