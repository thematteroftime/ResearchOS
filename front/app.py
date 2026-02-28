"""
多 Agent 联合分析科研学习平台 — 前端应用

参照 FRONTEND_DESIGN.md（Perplexity 风格）与 final_project 功能文档实现。
- 独立运行（python -m front.app）：使用演示数据与占位逻辑
- 整合运行（python main.py）：backend 注入后对接真实 API
"""
import asyncio
import json
import re
import html as html_escape
from pathlib import Path

import gradio as gr
import pandas as pd


def _log(tag: str, step: str, **kwargs) -> None:
    """前端调试日志，便于根据命令行输出定位四场景 bug。tag 为场景标签如 SCENE1，避免 kwargs 含 scene 时冲突。"""
    parts = [f"[FRONT][{tag}] {step}"]
    if kwargs:
        try:
            brief = json.dumps(kwargs, ensure_ascii=False)[:500]
            parts.append(brief)
        except Exception:
            parts.append(str(kwargs)[:500])
    print(" ".join(parts), flush=True)

__version__ = "1.0.0"
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
EXAMPLES_DIR = BASE_DIR / "examples"

# ---------- 格式/类型选项（与 merge_project 配置一致，前端占位） ----------
VENUE_FORMATS = [
    {"id": "nature", "label": "Nature"},
    {"id": "science", "label": "Science"},
    {"id": "neurips", "label": "NeurIPS"},
    {"id": "ieee", "label": "IEEE"},
    {"id": "acm", "label": "ACM"},
    {"id": "custom", "label": "自定义"},
]
PROJECT_TYPES = [
    {"id": "paper", "label": "论文撰写"},
    {"id": "poster", "label": "论文海报"},
    {"id": "grant_nsf", "label": "基金申报(NSF)"},
    {"id": "grant_nih", "label": "基金申报(NIH)"},
    {"id": "literature_review", "label": "文献综述"},
    {"id": "market_research", "label": "调研报告"},
    {"id": "custom", "label": "自定义"},
]

# ---------- 演示数据 ----------
DEMO_STRUCTURED_DATA = {
    "metadata": {
        "title": "First Observation of Electrorheological Plasmas",
        "journal": "Physical Review Letters",
        "year": "2008",
        "innovation": "首次发现电变流变复杂等离子体，揭示通过外加交流电场调控尘埃粒子间相互作用的新机制。",
    },
    "physics_context": {
        "environment": "微重力环境（国际空间站内），低气压氩气放电等离子体",
        "detailed_background": "复杂等离子体中的尘埃颗粒周围存在德拜球。在外加交流电场作用下，离子漂移导致德拜球变形，形成非对称的离子尾，诱导偶极型相互作用。",
    },
    "observed_phenomena": "随着外加交流电场强度增加，尘埃系统发生从各向同性流体态到链状结构的相变；该相变是可逆的。",
    "parameters": [
        {"name": "粒子直径", "symbol": "$ d $", "value": "1.55, 4.9, 6.8", "unit": "μm", "meaning": "实验所用微粒的几何直径"},
        {"name": "气体压力", "symbol": "$ p $", "value": "8–15", "unit": "Pa", "meaning": "氩气工作气压"},
        {"name": "热马赫数平方", "symbol": "$ M_T^2 $", "value": "0.22–1.45", "unit": "无量纲", "meaning": "核心控制参数"},
    ],
    "force_fields": [
        {
            "name": "时间平均后的有效对势",
            "formula": "$ W(r,\\theta) = \\frac{Q^2}{r} e^{-r/\\lambda} \\left[ 1 + 0.43 M_T^2 \\frac{\\lambda^2}{r^2} (3\\cos^2\\theta - 1) \\right] $",
            "physical_significance": "包含德拜-休克尔核心项与电场诱导的四极修正项",
            "computational_hint": "可作为静态有效势用于分子动力学模拟",
        }
    ],
    "figures": [],
}

DEMO_RECOMMENDATION_JSON = {
    "parameter_recommendations": {
        "target_particle_charge": {"range": [10000.0, 15000.0], "step": 500.0, "unit": "e", "reason": "参考文献中粒子电荷量约为 ~−10⁴ e，链状结构形成趋势随 |Q| 增大而增强。"},
        "time_scale": {"range": [150.0, 250.0], "step": 10.0, "unit": "ms", "reason": "微重力下尘埃等离子体动力学时间尺度由离子响应主导；总模拟时长 200 ms 足以捕捉链形成与弛豫。"},
        "debye_length_target": {"range": [0.4, 0.8], "step": 0.05, "unit": "mm", "reason": "文献中 λ ≈ 0.05 mm；区间 [0.4, 0.8] mm 覆盖弱至强屏效过渡。"},
    },
    "force_field_recommendation": {
        "name": "场致电变流体对势（Electrorheological Pair Potential）",
        "reason": "该力场显式包含各向异性项，直接编码了外加交变电场下离子尾流诱导的偶极类相互作用，可直接用于分子动力学模拟。",
    },
}

DEMO_RECORDS = [
    ["✓", "demo_001", "论文：First Observation...", "structured.json", "physics_agent", "paper"],
    ["✓", "demo_002", "参数推荐：复杂等离子体", "recommendations.json", "physics_agent", "parameter_recommendation"],
    ["✓", "demo_003", "写作：Nature 量子计算", "quantum_summary_paper.pdf", "_default", "writing_event"],
]


def theme_css():
    """Clean, modern UI: light greys, working paper feel, subtle shadows (Perplexity-inspired).
    Uses solid backgrounds (no backdrop-filter/linear-gradient) for reliability and minimal look.
    !important reserved for overriding Gradio defaults only."""
    return """
    <style>
      /* ===== 全局：纯色浅灰背景（无 gradient/backdrop-filter） ===== */
      html, body, .gradio-container, .main, [data-testid="blocks-container"] {
        background: #f9f9f9 !important;
        background-image: none !important;
        min-height: 100vh;
      }
      .blocks > .overflow-hidden { padding: 20px; }

      /* ===== Gradio 内部容器：去除灰底/边框（仅覆盖 Gradio 默认） ===== */
      [data-testid="block-label"],
      [data-testid="block-wrap"],
      [data-testid="block-inner"],
      [data-testid="form"],
      [data-testid="container"] {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
      }
      [data-testid="block-label"],
      [data-testid="form"],
      [data-testid="container"] {
        padding: 0 !important;
        margin: 0 !important;
      }

      /* ===== 全局字体与排版 ===== */
      .gradio-container {
        font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
        color: var(--text-main);
      }
      .gradio-container p, .gr-markdown p, .paper-workbench p, .paper-card p {
        line-height: 1.6;
      }

      /* ===== 主内容区：透明容器，卡片样式在 .scene-card 上 ===== */
      .main-content {
        background: transparent !important;
        box-shadow: none !important;
        border: none !important;
        padding: 20px;
        min-height: 60vh;
        width: 100%;
        flex: 1;
      }
      .top-placeholder-bar {
        height: 40px;
        background: #f0f0f0;
        border-radius: var(--radius-control);
        margin-bottom: 20px;
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.03);
        display: flex;
        align-items: center;
        justify-content: center;
        color: var(--text-tertiary);
        font-size: 0.9rem;
      }

      /* ===== 左侧导航（覆盖 Gradio 列样式） ===== */
      .nav-sidebar {
        background: #ffffff !important;
        padding: 20px 16px;
        min-width: 200px;
        border-radius: 0 var(--radius-card) var(--radius-card) 0;
        box-shadow: 1px 0 8px rgba(0, 0, 0, 0.03);
      }

      /* ===== 导航栏内搜索框 ===== */
      .nav-sidebar .gr-input, .nav-sidebar .gr-box {
        border-radius: var(--radius-control);
        background-color: #f5f5f5;
        padding: 8px 12px;
      }
      .nav-sidebar input::placeholder { color: var(--text-tertiary); }

      /* ===== 导航按钮（默认，覆盖 Gradio radio 样式） ===== */
      .nav-sidebar label, .nav-sidebar .gr-radios-item, .nav-sidebar [role="radiogroup"] label {
        background: transparent !important;
        border: none !important;
        color: #4a4a4a !important;
        border-radius: 8px;
        padding: 8px 14px;
        margin-bottom: 8px;
        transition: all 0.2s ease;
      }
      .nav-sidebar label:hover, .nav-sidebar .gr-radios-item:hover,
      .nav-sidebar [role="radiogroup"] label:hover {
        background: #f5f5f5 !important;
        border-radius: 8px;
      }
      /* ===== 导航按钮（选中） ===== */
      .nav-sidebar label:has(input:checked), .nav-sidebar .gr-radios-item.selected {
        background: #f0f0f0 !important;
        border: none !important;
        border-left: 3px solid #b8860b !important;
        box-shadow: none !important;
        color: #333333 !important;
        font-weight: 600 !important;
      }

      /* ===== 设计变量（统一引用） ===== */
      :root {
        --text-main: #333333;
        --text-muted: #777777;
        --text-tertiary: #999999;
        --card-border: rgba(0, 0, 0, 0.08);
        --card-shadow: 0 2px 6px rgba(0, 0, 0, 0.04);
        --card-shadow-strong: 0 4px 12px rgba(0, 0, 0, 0.08);
        --radius-card: 12px;
        --radius-inner: 10px;
        --radius-control: 8px;
      }

      /* ===== 主内容容器（paper-workbench 与 scene-card） ===== */
      .paper-workbench, .scene-card {
        background: #ffffff !important;
        border-radius: var(--radius-card);
        box-shadow: var(--card-shadow-strong);
        padding: 24px;
        margin-bottom: 20px;
      }

      /* ===== 场景标题（## 论文分析 等） ===== */
      .main-content .scene-card .gr-markdown h2,
      .main-content .scene-card h2 {
        color: var(--text-main);
        font-size: 1.6rem;
        font-weight: 700;
        margin-bottom: 24px;
      }

      /* ===== 场景内 Row/Column 布局：统一 gap，透明背景 ===== */
      .main-content .scene-card .contain,
      .main-content .scene-card .form,
      .main-content .scene-card [class*="row"],
      .main-content .scene-card [class*="column"] {
        gap: 16px;
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
      }
      .paper-header, .paper-title { font-size: 1.25rem; font-weight: 700; }
      .paper-meta-line { font-size: 0.88rem; }
      .paper-main-grid { display: block; }
      .paper-strip { width: 100%; margin-bottom: 16px; border: 1px solid var(--card-border); border-radius: var(--radius-inner); padding: 16px 20px; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,0.04); }
      .paper-strip h3 { font-size: 0.95rem; margin: 0 0 10px 0; color: var(--text-muted); font-weight: 600; }
      .paper-meta-line.innovation-highlight {
        background: #faf8f5;
        border: 1px solid rgba(184, 134, 11, 0.3);
        border-radius: var(--radius-control);
        padding: 10px 14px;
        margin-top: 12px;
        font-weight: 600;
        color: #4a4a4a;
        display: block;
        line-height: 1.5;
      }

      /* ===== 内部内容卡片 ===== */
      .paper-card {
        background: #ffffff;
        border-radius: var(--radius-inner);
        border: 1px solid var(--card-border);
        padding: 16px;
        margin-bottom: 8px;
        box-shadow: var(--card-shadow);
      }
      .paper-card-physics { border-left: 4px solid #b8860b; padding-left: 16px; }
      .param-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
      .param-box { border: 1px solid var(--card-border); border-radius: var(--radius-inner); padding: 14px; margin-bottom: 16px; background: #fafafa; }
      .param-card {
        border-radius: var(--radius-control);
        border: 1px solid rgba(0, 0, 0, 0.06);
        background: #fdfdfd;
        padding: 10px 12px;
        box-shadow: none;
      }
      .param-card .param-name { font-size: 1rem; font-weight: 600; color: var(--text-main); margin-top: 4px; }
      .param-card .param-symbol { font-size: 0.95rem; color: var(--text-muted); font-style: italic; }
      .param-card .param-value { font-size: 1.2rem; font-weight: 700; color: var(--text-main); }
      .param-card .param-unit { font-size: 0.8rem; font-weight: 500; color: var(--text-muted); }
      .param-card .param-meaning { font-size: 0.75rem; color: var(--text-tertiary); margin-top: 6px; }
      .force-card .formula-box {
        background: #fcfcfc;
        border: 1px solid var(--card-border);
        border-radius: var(--radius-control);
        padding: 8px;
        text-align: center;
        margin: 6px 0;
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.03);
        font-family: Consolas, Monaco, "Courier New", monospace;
        color: var(--text-main);
      }
      /* ===== Observed Phenomena：突出显示 ===== */
      .phenomena-card {
        margin-top: 12px;
        border-radius: var(--radius-inner);
        padding: 16px;
        background: #fcfcfc;
        border: 1px solid rgba(184, 134, 11, 0.25);
        box-shadow: var(--card-shadow);
      }
      .phenomena-title { font-weight: 700; font-size: 0.95rem; color: var(--text-main); margin-bottom: 8px; }
      .phenomena-body { font-size: 0.9rem; color: var(--text-muted); line-height: 1.5; text-decoration: none !important; border-bottom: none !important; }
      .paper-strip p, .paper-strip .phenomena-body, .paper-workbench .param-meaning { text-decoration: none !important; }
      /* 防止 LaTeX/KaTeX 对中文等产生奇怪下划线 */
      .paper-strip, .phenomena-body, .paper-card-physics { --no-underline: 1; }
      .paper-strip *:not(.formula-box):not(.katex) { text-decoration: none !important; }
      .force-card-inline { margin-bottom: 12px; }
      .force-card-inline:last-child { margin-bottom: 0; }
      .force-card {
        border-radius: var(--radius-inner);
        border: 1px solid var(--card-border);
        background: #ffffff;
        padding: 16px;
        margin-bottom: 12px;
        box-shadow: var(--card-shadow);
      }
      .recom-card {
        background: #ffffff;
        border-radius: var(--radius-inner);
        border: 1px solid var(--card-border);
        border-left: 4px solid #b8860b;
        padding: 16px;
        margin-bottom: 16px;
        box-shadow: var(--card-shadow);
      }
      .reason-box {
        margin-top: 8px;
        padding: 12px 14px;
        border-radius: var(--radius-inner);
        background: #fcfcfc;
        border: 1px solid var(--card-border);
        font-size: 0.85rem;
        color: var(--text-muted);
      }
      .recom-force-card {
        padding: 16px;
        border-radius: var(--radius-inner);
        background: #ffffff;
        border: 1px solid var(--card-border);
        box-shadow: var(--card-shadow);
      }
      .dataframe-toolbar {
        margin-bottom: 10px;
        justify-content: flex-end;
        gap: 8px;
      }
      .param-add-btn, .param-remove-btn {
        width: 30px !important;
        height: 30px !important;
        min-width: 30px !important;
        max-width: 30px !important;
        padding: 0 !important;
        border-radius: 6px !important; /* smaller for icon buttons */
        background: #f5f5f5 !important;
        border: 1px solid #e0e0e0 !important;
        color: #4a4a4a !important;
        box-shadow: none !important;
      }
      .param-add-btn:hover, .param-remove-btn:hover {
        background: #ebebeb !important;
      }

      /* ===== 记忆查询：Perplexity 风格搜索 ===== */
      .memory-search-row { margin-bottom: 12px; align-items: center; }
      .memory-search-input input { padding: 12px 16px !important; font-size: 1rem !important; }
      .memory-search-btn { min-width: 44px !important; padding: 10px 14px !important; }
      /* 四配置单行、 compact 布局，顺序：查询范围 Agent 分类 排序 */
      .memory-config-row { display: flex !important; flex-wrap: nowrap !important; gap: 8px; align-items: flex-end; margin-bottom: 12px; overflow: visible !important; }
      .memory-config-row > div { flex: 1 1 0; min-width: 60px; max-width: none; }
      /* 配置下拉：缩小字体与方框，提高 z-index 避免被记录列表覆盖 */
      .memory-config-dd .gr-dropdown, .memory-config-dd select, .memory-config-dd input {
        font-size: 0.83rem !important; padding: 6px 10px !important; min-height: 32px !important;
      }
      .memory-config-dd [data-testid="block-label"] { font-size: 0.8rem !important; color: var(--text-muted); }
      /* 配置区 sticky，高 z-index 确保下拉菜单显示在上层 */
      .scene-memory .memory-config-row { position: sticky; top: 0; z-index: 999; background: #fff; padding: 6px 0; margin: -6px 0 12px 0; overflow: visible !important; }
      /* Gradio 下拉菜单弹出层置于最前（含 body 级 portal） */
      [role="listbox"], .dropdown-options, [data-testid="dropdown-options"],
      .gr-dropdown .wrap.svelte-open, .svelte-dropdown-list, body > [id*="dropdown"] {
        z-index: 99999 !important;
      }

      /* ===== 空状态 ===== */
      .empty-state {
        text-align: center; color: var(--text-muted); padding: 56px 28px;
        font-size: 0.95rem; font-weight: 500;
      }

      /* ===== 按钮（覆盖 Gradio 默认） ===== */
      .gr-button.primary, button.primary {
        border-radius: var(--radius-control) !important;
        background: #b8860b !important;
        color: #ffffff !important;
        box-shadow: 0 4px 12px rgba(184, 134, 11, 0.3) !important;
        transition: all 0.2s ease;
      }
      .gr-button.primary:hover, button.primary:hover {
        background: #a3790a !important;
      }
      .gr-button.secondary, button.secondary {
        border-radius: var(--radius-control) !important;
        background: #f5f5f5 !important;
        border: 1px solid #e0e0e0 !important;
        color: #4a4a4a !important;
        box-shadow: none !important;
        transition: all 0.2s ease;
      }
      .gr-button.secondary:hover, button.secondary:hover {
        background: #ebebeb !important;
      }

      /* ===== 输入框、下拉、文件上传（覆盖 Gradio 默认） ===== */
      .gr-input, .gr-textarea, .gr-dropdown,
      .gr-input input, .gr-textarea textarea, .gr-dropdown select,
      .gr-box input, .gr-box textarea {
        border-radius: var(--radius-control) !important;
        border: 1px solid #e0e0e0 !important;
        box-shadow: none !important;
        font-size: 1rem;
        transition: all 0.2s ease;
      }
      .gr-input:focus-within, .gr-textarea:focus-within, .gr-dropdown:focus-within,
      .gr-input input:focus, .gr-textarea textarea:focus, .gr-dropdown select:focus,
      .gr-box input:focus, .gr-box textarea:focus {
        border: 1px solid #b8860b !important;
        box-shadow: 0 0 0 2px rgba(184, 134, 11, 0.2) !important;
        outline: none;
      }
      .gr-input input::placeholder, .gr-textarea textarea::placeholder { color: var(--text-tertiary) !important; }
      .gr-file {
        border-radius: var(--radius-control) !important;
        border: 1px dashed #cccccc !important;
        background: #ffffff !important;
        box-shadow: none !important;
      }
      .gr-file .gr-box, .gr-file .gr-form, .gr-file span, .gr-file p {
        color: var(--text-muted) !important;
      }
      .gr-file:focus-within {
        border: 1px dashed #b8860b !important;
        box-shadow: 0 0 0 2px rgba(184, 134, 11, 0.2) !important;
      }
      .gr-box, .gr-form { border-radius: var(--radius-control); }

      /* ===== 输入块 / 输出块分离 ===== */
      .input-block { margin-bottom: 20px; }
      .output-block { margin-top: 24px; }

      /* ===== 提取模式：低调次要 ===== */
      .mode-dropdown-subtle, .mode-dropdown-subtle .gr-dropdown,
      .mode-dropdown-subtle .gr-form, .mode-dropdown-subtle select {
        min-width: 100px !important;
        font-size: 0.88rem !important;
      }
      .mode-dropdown-subtle [data-testid="block-label"] {
        font-size: 0.82rem !important;
        color: var(--text-tertiary) !important;
      }

      /* ===== 论文分析：更多分析选项（紧凑、低调） ===== */
      .advanced-analysis-dropdown, .advanced-analysis-dropdown .gr-dropdown,
      .advanced-analysis-dropdown select, .advanced-analysis-dropdown .gr-form {
        border-radius: var(--radius-control) !important;
        border: 1px solid #e0e0e0 !important;
        background: #ffffff !important;
        font-size: 0.9rem !important;
        color: var(--text-muted) !important;
        min-width: 140px;
      }
      .advanced-analysis-dropdown .wrap, .advanced-analysis-dropdown [data-testid="block-label"] {
        font-size: 0.85rem !important;
        color: var(--text-tertiary) !important;
      }

      /* ===== 记忆查询场景：Radio 无灰底/白底，选中项高亮（覆盖 Gradio） ===== */
      .scene-memory .gr-radios,
      .scene-memory .gr-radios-item,
      .scene-memory [role="radiogroup"] {
        background: transparent !important;
        border: none !important;
      }
      .scene-memory .gr-radios-item label,
      .scene-memory [role="radiogroup"] label {
        background: transparent !important;
        border: none !important;
        color: var(--text-main);
      }
      .scene-memory .gr-radios-item.selected label,
      .scene-memory .gr-radios-item.selected,
      .scene-memory .gr-radios-item:has(input:checked),
      .scene-memory [role="radiogroup"] label:has(input:checked) {
        background: #f0f0f0 !important;
        border: 1px solid #e0e0e0 !important;
        border-radius: var(--radius-control);
        color: var(--text-main);
      }
      .scene-memory .gr-dropdown,
      .scene-memory .gr-dropdown select {
        background: #ffffff !important;
        border: 1px solid #e0e0e0 !important;
        border-radius: var(--radius-control) !important;
      }
      /* 记忆查询区不裁剪下拉弹层 */
      .scene-memory { overflow: visible !important; }

      /* ===== Dataframe / 表格：卡片化（覆盖 Gradio 默认） ===== */
      .gr-dataframe {
        background: #ffffff !important;
        border-radius: var(--radius-inner);
        box-shadow: var(--card-shadow);
        overflow: hidden;
      }
      .gr-dataframe th,
      .gr-dataframe thead th {
        background: #fcfcfc;
        color: var(--text-main);
        font-weight: 700;
        padding: 12px 16px;
      }
      .gr-dataframe td,
      .gr-dataframe tbody td {
        padding: 10px 16px;
        color: var(--text-main);
        background: #ffffff;
      }
      .gr-dataframe tr:nth-child(even) td { background: #fafafa; }
      .gr-dataframe td:first-child {
        text-align: center;
        color: #b8860b;
        font-size: 0.95rem;
      }
      .download-links { margin-bottom: 12px; padding: 8px 12px; background: #f9f9f9; border-radius: var(--radius-control); font-size: 0.9rem; }
      .download-links a { color: #b8860b; text-decoration: none; margin-right: 12px; }
      .download-links a:hover { text-decoration: underline; }

      /* ===== 文字颜色（覆盖 Gradio 默认） ===== */
      .gr-markdown, .gr-markdown p, .gr-markdown span,
      .paper-header, .paper-title, .paper-card h3,
      .param-value, .param-name, .gr-label, label {
        color: var(--text-main) !important;
      }
      .gr-markdown h2, .prose h2 { color: var(--text-main) !important; }
      .paper-meta-line, .reason-box, .empty-state, #recent-section, #nav-footer { color: var(--text-muted); }
      .progress-steps span { color: var(--text-main); }
      .output-block { margin-top: 24px; }
      /* ===== 嵌入图表（paper_body 内） ===== */
      .figure-container {
        margin: 20px 0;
        text-align: center;
        background: #fdfdfd;
        border: 1px solid #e0e0e0;
        border-radius: var(--radius-control);
        padding: 15px;
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.03);
      }
      .paper-embedded-figure {
        max-width: 90%;
        height: auto;
        border-radius: 5px;
        margin-bottom: 10px;
      }
      .figure-caption { font-size: 0.85rem; color: var(--text-muted); line-height: 1.4; }
      /* ===== 来源引用占位 ===== */
      .source-ref-badge {
        display: inline-block;
        background: #e0e0e0;
        color: var(--text-muted);
        font-size: 0.75rem;
        padding: 2px 6px;
        border-radius: 4px;
        margin-left: 5px;
        cursor: pointer;
        user-select: none;
        transition: background 0.15s ease;
      }
      .source-ref-badge:hover {
        background: #d0d0d0;
      }
      /* ===== 阅读视图选择器 ===== */
      .reading-view-selector .gr-radios,
      .reading-view-selector .gr-radios-item,
      .reading-view-selector [role="radiogroup"] {
        background: transparent !important;
        border: none !important;
      }
      .reading-view-selector label,
      .reading-view-selector .gr-radios-item label {
        background: #ffffff !important;
        border: 1px solid #e0e0e0 !important;
        border-radius: var(--radius-control) !important;
        padding: 8px 16px !important;
        color: var(--text-main) !important;
        transition: all 0.2s ease;
      }
      .reading-view-selector label:hover,
      .reading-view-selector .gr-radios-item:hover label {
        background: #f5f5f5 !important;
      }
      .reading-view-selector label:has(input:checked),
      .reading-view-selector .gr-radios-item.selected label {
        background: #f0f0f0 !important;
        border-color: #b8860b !important;
        font-weight: 600 !important;
      }
      /* ===== 参数推荐：专家模式开关（小、右对齐） ===== */
      .expert-toggle-row { margin-bottom: 8px; justify-content: flex-end; }
      .expert-toggle-cb, .expert-toggle-cb .wrap, .expert-toggle-cb label {
        font-size: 0.82rem !important;
        color: var(--text-muted) !important;
        padding: 4px 0 !important;
      }
      .expert-toggle-cb label {
        cursor: pointer;
        font-weight: 400 !important;
      }
      /* ===== 科研写作：示例展示区（可滚动长方块） ===== */
      .scrollable-output-block {
        max-height: 55vh;
        min-height: 200px;
        overflow-y: auto;
        overflow-x: hidden;
        border: 1px solid #e0e0e0;
        border-radius: var(--radius-control);
        padding: 16px;
        background: #fcfcfc;
        box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.04);
      }
      .scrollable-output-block::-webkit-scrollbar { width: 8px; }
      .scrollable-output-block::-webkit-scrollbar-track { background: #f0f0f0; border-radius: 4px; }
      .scrollable-output-block::-webkit-scrollbar-thumb { background: #c0c0c0; border-radius: 4px; }
      .scrollable-output-block::-webkit-scrollbar-thumb:hover { background: #a0a0a0; }
      /* ===== 科研写作：示例文件选择器 ===== */
      .example-file-selector .gr-radios { gap: 12px; }
      .example-file-selector [data-testid="block-label"] { font-size: 0.9rem; font-weight: 500; }
    </style>
    """


def render_progress_html(steps_done):
    labels = ["Upload", "Parsing", "Physics Extraction", "Embedding", "Indexed"]
    html = '<div class="progress-steps" style="font-weight:500;">'
    for i, lab in enumerate(labels):
        ok = steps_done[i]
        # Perplexity-style: solid circle in accent color for done, outline for pending
        sym = '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#b8860b;margin-right:10px;vertical-align:middle;"></span>' if ok else '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;border:1.5px solid #d1d5db;margin-right:10px;vertical-align:middle;"></span>'
        text_color = "#333333" if ok else "#777777"
        html += f'<div style="margin:8px 0;font-weight:500;">{sym}<span style="color:{text_color};vertical-align:middle">{lab}</span></div>'
    html += "</div>"
    return html


def render_header_html(data):
    if not data or "metadata" not in data:
        return "<div class='paper-workbench'><div class='paper-title'>⚠️ 未能提取到有效数据</div></div>"
    meta = data.get("metadata", {})
    title = meta.get("title", "未知标题")
    journal = meta.get("journal", "")
    year = meta.get("year", "")
    innovation = meta.get("innovation", "")
    html = f"<div class='paper-workbench'><div class='paper-header'><div class='paper-title'>{title}</div>"
    if journal or year:
        html += f"<div class='paper-meta-line'>{(journal or '') + (' · ' if journal and year else '') + str(year or '')}</div>"
    if innovation:
        html += f"<div class='paper-meta-line innovation-highlight'>创新：{innovation}</div>"
    html += "</div></div>"
    return html


def _figure_src_from_path(raw_path):
    """Resolve figure path for img src. Returns path Gradio can serve (relative to BASE_DIR)."""
    if not raw_path:
        return None
    p = (BASE_DIR / raw_path).resolve()
    if not p.is_file():
        return None
    try:
        return str(p.relative_to(BASE_DIR)).replace("\\", "/")
    except ValueError:
        return str(p).replace("\\", "/")


def render_body_html(data):
    """
    论文分析展示：参数 3/行 单框 + 三长条模块（物理背景、Observed Phenomena、相互作用力场）。
    """
    if not data or "metadata" not in data:
        return "<div class='paper-workbench'>⚠️ 未能提取到有效数据</div>"
    ctx = data.get("physics_context", {})
    params = data.get("parameters", [])
    forces = data.get("force_fields", [])
    phenomena = data.get("observed_phenomena", "")
    figures = data.get("figures", []) or []

    def esc(s):
        return html_escape.escape(str(s) if s is not None else "")

    html = "<div class='paper-workbench'>"
    # 1) 提取的关键物理参数：单框圈定，每行三个
    html += "<div class='param-box'><h3>提取的关键物理参数</h3><div class='param-grid'>"
    for p in params:
        html += f"<div class='param-card'><div class='param-symbol'>{p.get('symbol','')}</div><div class='param-value'>{p.get('value','')}</div><div class='param-unit'>{p.get('unit','')}</div><div class='param-name'>{p.get('name','')}</div><div class='param-meaning'>{p.get('meaning','')}</div></div>"
    html += "</div></div>"

    # 2) 物理背景与环境：长条
    html += "<div class='paper-strip'><h3>物理背景与环境</h3>"
    env = ctx.get("environment", "N/A")
    bg = ctx.get("detailed_background", "")
    html += f"<p><strong>环境：</strong>{esc(env)}</p>"
    if bg:
        html += f"<p>{esc(bg)}</p>"
    html += "</div>"

    # 3) Observed Phenomena：长条
    if phenomena:
        html += f"<div class='paper-strip'><h3>Observed Phenomena</h3><div class='phenomena-body'>{esc(phenomena)}</div></div>"

    # 4) 相互作用力场：长条（多个力场依次排列）
    if forces:
        html += "<div class='paper-strip'><h3>相互作用力场</h3>"
        for f in forces:
            html += f"<div class='force-card force-card-inline'><div style='font-weight:600;'>{f.get('name','')}</div><div class='formula-box'>{f.get('formula','')}</div><div style='font-size:0.8rem;color:#4b5563'>{f.get('physical_significance','')}</div></div>"
        html += "</div>"

    # 5) 图表（若有）
    for i, fig in enumerate(figures):
        raw = fig.get("image_path", "")
        src = _figure_src_from_path(raw)
        if not src:
            continue
        caption = fig.get("caption", "") or f"Figure {i + 1}"
        img_url = f"/gradio_api/file={src}" if not src.startswith(("/", "http")) else src
        html += f"<div class='figure-container'><img src='{img_url}' alt='{esc(caption)}' class='paper-embedded-figure' loading='lazy'><p class='figure-caption'>Figure {i + 1}: {esc(caption)}</p></div>"

    html += "</div>"
    return html


def format_recommendation_panel_v2(res_json, expert_mode=False):
    def to_latex_number(num):
        if not isinstance(num, (int, float)):
            return html_escape.escape(str(num))
        if abs(num) >= 1e3 or (abs(num) < 1e-2 and num != 0):
            s = f"{num:.4e}"
            base, exp = float(s.split("e")[0]), int(s.split("e")[1])
            return f"10^{{{exp}}}" if abs(base - 1.0) < 1e-8 else f"{base:.2f} \\times 10^{{{exp}}}"
        return html_escape.escape(f"{num:.4f}".rstrip("0").rstrip("."))

    def format_range_latex(rl):
        if not rl or len(rl) < 2:
            return "N/A"
        return f"$[{to_latex_number(rl[0])},\\ {to_latex_number(rl[1])}]$"

    def format_reason(t):
        if not t:
            return ""
        s = str(t)
        for ch, cmd in [("λ", "\\lambda"), ("θ", "\\theta"), ("κ", "\\kappa"), ("Δ", "\\Delta")]:
            s = s.replace(ch, f"${cmd}$")
        s = html_escape.escape(s)
        return s

    html = "<div class='recom-wrapper'>"
    for p_name, info in res_json.get("parameter_recommendations", {}).items():
        unit = html_escape.escape(str(info.get("unit", "")))
        rl = info.get("range", [])
        step = info.get("step", "N/A")
        reason = format_reason(info.get("reason", ""))
        html += f"<div class='recom-card'><div style='display:flex;justify-content:space-between;'><div style='font-weight:600;color:#333'>{html_escape.escape(str(p_name))}</div><div style='font-size:0.78rem;padding:2px 8px;border-radius:999px;background:#f5f5f5;color:#777;border:1px solid rgba(0,0,0,0.08)'>{unit}</div></div>"
        html += f"<div style='font-size:0.9rem;color:#777;margin:4px 0'>推荐区间：{format_range_latex(rl)}</div>"
        html += f"<div style='font-size:0.85rem;margin-top:4px'>步长：{to_latex_number(step) if isinstance(step,(int,float)) else html_escape.escape(str(step))}</div>"
        html += f"<div class='reason-box'>{reason}</div></div>"
    ff = res_json.get("force_field_recommendation", {})
    html += f"<div class='recom-force-card'><div style='font-size:1rem;font-weight:600;margin-bottom:6px;color:#333'>🧪 推荐力场</div>"
    html += f"<div style='font-weight:600;color:#4a4a4a;margin-bottom:6px'>{html_escape.escape(str(ff.get('name','N/A')))}</div>"
    html += f"<div style='font-size:0.86rem'>{format_reason(ff.get('reason',''))}</div></div>"
    if expert_mode:
        html += f"<pre style='font-size:0.8rem;background:#0f172a;color:#e5e7eb;padding:12px;border-radius:8px;overflow:auto'>{html_escape.escape(json.dumps(res_json, indent=2, ensure_ascii=False))}</pre>"
    html += "</div>"
    return html


def add_param_row(df):
    try:
        if df is None:
            return [["", "", "", ""]]
        if isinstance(df, pd.DataFrame):
            return pd.concat([df, pd.DataFrame([["", "", "", ""]], columns=df.columns)], ignore_index=True)
        if isinstance(df, list):
            return df + [["", "", "", ""]]
    except Exception:
        pass
    return df


def remove_param_row(df):
    try:
        if df is None:
            return [["", "", "", ""]]
        if isinstance(df, pd.DataFrame) and len(df) > 1:
            return df.iloc[:-1]
        if isinstance(df, list) and len(df) > 1:
            return df[:-1]
    except Exception:
        pass
    return df


LATEX_OPTS = {"latex_delimiters": [{"left": "$", "right": "$", "display": False}, {"left": "$$", "right": "$$", "display": True}, {"left": r"\[", "right": r"\]", "display": True}]}

TOP_PLACEHOLDER_HTML = '<div class="top-placeholder-bar">全局搜索或 Agent 配置（未来功能）</div>'


def build_ui(backend=None):
    """
    构建 Gradio 界面。
    backend: AppBackend 实例；为 None 时使用演示数据与占位逻辑（独立运行）。
    """
    from pathlib import Path
    proj_root = Path(__file__).resolve().parent.parent
    gr.set_static_paths(paths=[str(BASE_DIR), str(proj_root)])
    with gr.Blocks(title="科研学习平台") as demo:
        gr.HTML(theme_css())

        raw_structured_state = gr.State({})
        lib_selected_id = gr.State(None)

        with gr.Row():
            # ---------- 左侧导航栏 ----------
            with gr.Column(scale=1, elem_classes=["nav-sidebar"]):
                gr.Textbox(placeholder="🔍 搜索...", show_label=False, scale=0)
                nav = gr.Radio(
                    ["论文分析", "科研写作", "参数推荐", "记忆查询"],
                    value="论文分析",
                    label="",
                    show_label=False,
                    elem_id="nav-radio",
                )
                gr.Markdown("---")
                recent_md = gr.Markdown("*最近和活跃的任务将显示在这里*", elem_id="recent-section")
                gr.Markdown("<br>")
                gr.Markdown("👤 账户与设置", elem_id="nav-footer")

            # ---------- 主工作区 ----------
            with gr.Column(scale=4, elem_classes=["main-content"]):
                gr.HTML(TOP_PLACEHOLDER_HTML)
                # ----- 场景一：论文分析 -----
                with gr.Column(visible=True, elem_classes=["scene-card"]) as scene1:
                    gr.Markdown("## 论文分析")
                    with gr.Row():
                        upload = gr.File(label="上传 PDF", file_types=[".pdf"], scale=3, elem_classes=["input-block"])
                        # mode_dd: 占位，当前 paper_ingest 无此参数；预留扩展为 extraction 模式（快速/详细）
                        mode_dd = gr.Dropdown(["默认", "快速", "详细"], value="默认", label="提取模式", scale=0, elem_classes=["mode-dropdown-subtle"])
                    user_input = gr.Textbox(placeholder="对论文的理解或关注点（选填）...", lines=3, label="", elem_classes=["input-block"])
                    with gr.Row():
                        parse_btn = gr.Button("🚀 分析并入库", variant="primary")
                        demo_btn = gr.Button("🧪 加载示例", variant="secondary")
                        advanced_options_dd = gr.Dropdown(
                            choices=["提取参数", "提取图表", "全文摘要"],
                            label="⋮ 更多分析选项",
                            value=None,
                            elem_classes=["advanced-analysis-dropdown"],
                            scale=0,
                        )
                    progress_html = gr.HTML(render_progress_html([False] * 5))
                    parse_status = gr.Markdown("*等待上传...*")
                    paper_header = gr.Markdown("<div class='empty-state'>上传 PDF 开始分析</div>", **LATEX_OPTS, elem_classes=["output-block"])
                    paper_body = gr.Markdown("", **LATEX_OPTS, elem_classes=["output-block"])
                    gr.Markdown("### 阅读视图")
                    view_mode_radio = gr.Radio(
                        ["快速浏览", "细读", "项目导向"],
                        value="细读",
                        label="",
                        show_label=False,
                        elem_classes=["reading-view-selector"],
                    )

                # ----- 场景二：科研写作 -----
                with gr.Column(visible=False, elem_classes=["scene-card"]) as scene2:
                    gr.Markdown("## 科研写作")
                    write_input = gr.Textbox(placeholder="描述您的写作意图，例如：Create a Nature paper on quantum chaos...", lines=4, label="写作意图", elem_classes=["input-block"])
                    with gr.Row():
                        venue_dd = gr.Dropdown(choices=[(v["label"], v["id"]) for v in VENUE_FORMATS], value="nature", label="格式")
                        project_dd = gr.Dropdown(choices=[(t["label"], t["id"]) for t in PROJECT_TYPES], value="paper", label="场景类型")
                    data_files = gr.File(file_count="multiple", file_types=[".pdf", ".md", ".png", ".csv"], label="附件", elem_classes=["input-block"])
                    with gr.Row():
                        write_btn = gr.Button("📝 生成论文", variant="primary")
                        demo_write_btn = gr.Button("🧪 加载示例", variant="secondary")
                    job_status = gr.Markdown("<div class='empty-state'>输入写作意图并选择格式开始</div>", elem_classes=["output-block"])
                    example_file_radio = gr.Radio(
                        choices=["quantum_summary_paper.pdf", "SUMMARY.md", "PEER_REVIEW.md"],
                        value="quantum_summary_paper.pdf",
                        label="选择查看示例",
                        show_label=True,
                        elem_classes=["example-file-selector"],
                    )
                    writing_output_state = gr.State(
                        {"mode": "demo", "output_dir": None, "choice_to_rel": None}
                    )
                    with gr.Column(elem_classes=["output-block", "scrollable-output-block"]):
                        write_result_md = gr.Markdown(
                            "<div class='empty-state'>点击「加载示例」后，在此选择查看 PDF、SUMMARY 或 PEER_REVIEW</div>",
                            **LATEX_OPTS,
                            visible=True,
                        )
                        write_result_pdf = gr.HTML("", visible=False)

                # ----- 场景三：参数推荐 -----
                with gr.Column(visible=False, elem_classes=["scene-card"]) as scene3:
                    gr.Markdown("## 参数推荐")
                    phenomena_input = gr.Textbox(placeholder="期望观察到的物理现象，例如：观察到微粒在微重力流场中形成的链状结构", lines=4, label="期望现象", elem_classes=["input-block"])
                    default_params = [["target_particle_charge", "1.2e4", "e", "目标微粒电荷"], ["time_scale", "200", "ms", "总演化时长"], ["debye_length_target", "0.6", "mm", "德拜屏蔽长度"]]
                    with gr.Row(elem_classes=["dataframe-toolbar"]):
                        add_btn = gr.Button("➕", variant="secondary", elem_classes=["param-add-btn"])
                        remove_btn = gr.Button("➖", variant="secondary", elem_classes=["param-remove-btn"])
                    with gr.Row():
                        param_df = gr.Dataframe(headers=["参数名称", "目标数值", "单位", "物理意义"], value=default_params, row_count="dynamic", column_count=(4, "fixed"), datatype=["str", "str", "str", "str"], label="用户参数表")
                    with gr.Row():
                        recom_btn = gr.Button("💡 生成对标推荐", variant="primary")
                        demo_recom_btn = gr.Button("🧪 加载示例", variant="secondary")
                    with gr.Row(elem_classes=["expert-toggle-row"]):
                        expert_cb = gr.Checkbox(label="显示原始 JSON", value=False, elem_classes=["expert-toggle-cb"])
                    recom_panel = gr.Markdown("<div class='empty-state'>请先在「论文分析」中上传并解析论文，或点击「加载示例」</div>", **LATEX_OPTS, elem_classes=["output-block"])

                # ----- 场景四：记忆查询（Perplexity 风格：搜索框一行 + 配置下拉在下方）-----
                with gr.Column(visible=False, elem_classes=["scene-card", "scene-memory"]) as scene4:
                    gr.Markdown("## 记忆查询")
                    # 统一搜索框：直接根据用户输入进行 memU 记忆系统查询和记录查询
                    with gr.Row(elem_classes=["memory-search-row"]):
                        query_tb = gr.Textbox(
                            placeholder="Q 搜索你的记录… 例如：最近关于复杂等离子体的论文",
                            show_label=False,
                            scale=4,
                            elem_classes=["memory-search-input"],
                        )
                        search_btn = gr.Button("🔍", variant="primary", scale=0, elem_classes=["memory-search-btn"])
                    # 四个配置并排一行，顺序：查询范围、Agent、分类、排序；含义用 label 展示，下拉中不显示占位
                    with gr.Row(elem_classes=["memory-config-row"]):
                        scope_dd = gr.Dropdown(
                            choices=[("按 agent 检索", "by_agent"), ("全部 agent", "all")],
                            value="by_agent",
                            allow_custom_value=False,
                            label="查询范围",
                            scale=1,
                            elem_classes=["memory-config-dd"],
                        )
                        agent_dd = gr.Dropdown(
                            choices=[("_default", "_default")],
                            value="_default",
                            allow_custom_value=False,
                            label="Agent",
                            scale=1,
                            elem_classes=["memory-config-dd"],
                        )
                        cat_dd = gr.Dropdown(
                            choices=[("全部", "all"), ("论文", "paper"), ("写作", "writing_event"), ("推荐", "parameter_recommendation")],
                            value="all",
                            allow_custom_value=False,
                            label="分类",
                            scale=1,
                            elem_classes=["memory-config-dd"],
                        )
                        sort_dd = gr.Dropdown(
                            choices=[("最新", "latest"), ("最早", "earliest")],
                            value="latest",
                            allow_custom_value=False,
                            label="排序",
                            scale=1,
                            elem_classes=["memory-config-dd"],
                        )
                    lib_status = gr.Markdown("")
                    records_df = gr.Dataframe(
                        value=DEMO_RECORDS,
                        headers=["状态", "record_id", "任务", "文件", "agent_id", "scene"],
                        interactive=False,
                        label="记录列表",
                        elem_classes=["records-table-readonly"],
                    )
                    records_state = gr.State([])  # 存储完整 record 列表
                    with gr.Row():
                        record_selector = gr.Dropdown(
                            choices=[],
                            value=None,
                            label="选择记录",
                            show_label=True,
                            scale=3,
                            elem_classes=["record-selector-dd"],
                        )
                        view_btn = gr.Button("📖 查看选中", scale=0)
                    details_html = gr.Markdown("<div class='empty-state'>点击检索或选择记录查看详情。当前为示例数据。</div>", **LATEX_OPTS, elem_classes=["output-block"])

        # ---------- 事件：论文分析 -----
        def on_load_demo():
            steps = [True] * 5
            h = render_header_html(DEMO_STRUCTURED_DATA)
            b = render_body_html(DEMO_STRUCTURED_DATA)
            return (
                "✅ 已加载示例论文",
                render_progress_html(steps),
                h,
                b,
                DEMO_STRUCTURED_DATA,
            )

        def _file_path_from_upload(file):
            """从 Gradio File 组件解析文件路径。"""
            if file is None:
                return None
            if isinstance(file, str):
                return file if file.strip() else None
            if isinstance(file, list):
                return file[0] if file else None
            if hasattr(file, "name"):
                return getattr(file, "name") or None
            return str(file) if file else None

        def on_parse(file, user_txt):
            path = _file_path_from_upload(file)
            _log("SCENE1", "on_parse 入口", has_file=bool(path), user_input_len=len(user_txt or ""), backend=bool(backend))
            if not path:
                _log("SCENE1", "on_parse 跳过", reason="无文件")
                return (
                    "请先上传 PDF",
                    render_progress_html([False] * 5),
                    "<div class='paper-workbench'><div class='paper-title'>请先上传 PDF 文件</div></div>",
                    "<div class='paper-workbench'></div>",
                    {},
                )
            if backend:
                try:
                    _log("SCENE1", "调用 paper_ingest_pdf", path=path[:80] if path else "")
                    out = backend.paper_ingest_pdf(path, user_id=backend.memu.user_id, user_input=user_txt or "")
                    _log("SCENE1", "paper_ingest_pdf 返回", error=out.get("error"), results_count=len(out.get("results") or []))
                    if out.get("error"):
                        return (
                            f"❌ {out.get('error', '分析失败')}",
                            render_progress_html([True, True, False, False, False]),
                            "",
                            "",
                            {},
                        )
                    results = out.get("results", [])
                    if not results:
                        return (
                            "未识别到可处理的 agent，请尝试添加备注",
                            render_progress_html([True, True, False, False, False]),
                            "",
                            "",
                            {},
                        )
                    first = results[0]
                    structured = first.get("structured") or {}
                    agent_id = first.get("agent_id", "_default")
                    _log("SCENE1", "取首结果", agent_id=agent_id, has_structured=bool(structured), structured_keys=list(structured.keys())[:8] if structured else [])
                    if structured:
                        h = render_header_html(structured)
                        b = render_body_html(structured)
                        return (
                            f"✅ 已分析并入库（agent: {agent_id}）",
                            render_progress_html([True] * 5),
                            h,
                            b,
                            structured,
                        )
                except Exception as e:
                    _log("SCENE1", "on_parse 异常", error=str(e))
                    return (
                        f"❌ 分析出错：{e}",
                        render_progress_html([True, True, False, False, False]),
                        "",
                        "",
                        {},
                    )
            _log("SCENE1", "演示模式", msg="无 backend")
            return (
                "🔗 前端演示：暂未对接后端，请点击「加载示例」查看效果",
                render_progress_html([True, True, False, False, False]),
                "",
                "",
                {},
            )

        demo_btn.click(fn=on_load_demo, outputs=[parse_status, progress_html, paper_header, paper_body, raw_structured_state])
        parse_btn.click(fn=on_parse, inputs=[upload, user_input], outputs=[parse_status, progress_html, paper_header, paper_body, raw_structured_state])

        # ---------- 事件：参数推荐 -----
        def on_demo_recom(expert):
            return format_recommendation_panel_v2(DEMO_RECOMMENDATION_JSON, expert)

        def _param_df_to_user_params(phenomena, df):
            """将 param_df 转为 parameter_recommendation 所需的 user_params。"""
            params = {"expected_phenomena": (phenomena or "").strip()}
            if df is not None:
                for row in (df if isinstance(df, list) else df.values.tolist() if hasattr(df, "values") else []):
                    if len(row) >= 4 and row[0]:
                        name, value, unit, meaning = str(row[0]), str(row[1]), str(row[2]), str(row[3])
                        params[name] = f"{meaning}，单位{unit}，目标值{value}".strip("，")
            return params

        def on_recom(structured, phenomena, df, expert):
            _log("SCENE3", "on_recom 入口", has_structured=bool(structured), phenomena_len=len(phenomena or ""), backend=bool(backend))
            if not structured:
                _log("SCENE3", "on_recom 跳过", reason="无 structured")
                return "请先在「论文分析」中加载示例或解析论文"
            if backend:
                try:
                    user_params = _param_df_to_user_params(phenomena, df)
                    _log("SCENE3", "调用 parameter_recommendation", user_params_keys=list(user_params.keys()))
                    out = backend.parameter_recommendation(
                        structured_paper=structured,
                        user_params=user_params,
                        user_id=backend.memu.user_id,
                    )
                    _log("SCENE3", "parameter_recommendation 返回", error=out.get("error"), rec_count=len(out.get("parameter_recommendations") or {}))
                    if out.get("error"):
                        return f"❌ {out.get('error', '参数推荐失败')}"
                    res = {
                        "parameter_recommendations": out.get("parameter_recommendations", {}),
                        "force_field_recommendation": out.get("force_field_recommendation", {}),
                    }
                    return format_recommendation_panel_v2(res, expert)
                except Exception as e:
                    _log("SCENE3", "on_recom 异常", error=str(e))
                    return f"❌ 参数推荐出错：{e}"
            _log("SCENE3", "演示模式")
            return format_recommendation_panel_v2(DEMO_RECOMMENDATION_JSON, expert)

        demo_recom_btn.click(fn=on_demo_recom, inputs=[expert_cb], outputs=[recom_panel])
        recom_btn.click(fn=on_recom, inputs=[raw_structured_state, phenomena_input, param_df, expert_cb], outputs=[recom_panel])
        add_btn.click(fn=add_param_row, inputs=[param_df], outputs=[param_df])
        remove_btn.click(fn=remove_param_row, inputs=[param_df], outputs=[param_df])

        # ---------- 事件：导航切换 -----

        # ---------- 事件：科研写作示例文件选择与加载 -----
        DEMO_CHOICE_TO_REL = {
            "quantum_summary_paper.pdf": ("front/examples/quantum_summary_paper.pdf", "pdf"),
            "SUMMARY.md": ("front/examples/SUMMARY.md", "md"),
            "PEER_REVIEW.md": ("front/examples/PEER_REVIEW.md", "md"),
        }

        def _collect_output_files(output_dir: Path):
            """扫描写作输出目录，返回 (choices, choice_to_rel)。"""
            choices = []
            choice_to_rel = {}
            try:
                rel = output_dir.relative_to(PROJECT_ROOT)
                base_rel = str(rel).replace("\\", "/")
                final_dir = output_dir / "final"
                if final_dir.exists():
                    for p in final_dir.glob("*.pdf"):
                        r = f"{base_rel}/final/{p.name}"
                        choices.append(p.name)
                        choice_to_rel[p.name] = (r, "pdf")
                for name in ["SUMMARY.md", "PEER_REVIEW.md"]:
                    fp = output_dir / name
                    if fp.exists():
                        r = f"{base_rel}/{name}"
                        choices.append(name)
                        choice_to_rel[name] = (r, "md")
            except (ValueError, OSError):
                pass
            return choices, choice_to_rel

        def _render_example_file(choice, state):
            """根据选择渲染对应文件内容。支持 demo 与 job 两种上下文。"""
            if not choice:
                return gr.update(value="", visible=True), gr.update(value="", visible=False)
            choice_to_rel = None
            if state and isinstance(state, dict) and state.get("choice_to_rel"):
                choice_to_rel = state["choice_to_rel"]
            if not choice_to_rel and choice in DEMO_CHOICE_TO_REL:
                choice_to_rel = {choice: DEMO_CHOICE_TO_REL[choice]}
            if not choice_to_rel or choice not in choice_to_rel:
                return gr.update(value="*请先加载示例或完成写作任务*", visible=True), gr.update(value="", visible=False)
            rel_path, ftype = choice_to_rel[choice]
            abs_path = (PROJECT_ROOT / rel_path).resolve()
            if not abs_path.is_file():
                err = f"*文件未找到：`{rel_path}`*"
                return gr.update(value=err, visible=True), gr.update(value="", visible=False)
            if ftype == "pdf":
                url_rel = rel_path.replace("\\", "/")
                url = f"/gradio_api/file={url_rel}"
                iframe_html = f'<iframe src="{url}" style="width:100%;height:55vh;min-height:400px;border:1px solid #e0e0e0;border-radius:8px;" title="PDF"></iframe>'
                return gr.update(value="", visible=False), gr.update(value=iframe_html, visible=True)
            content = abs_path.read_text(encoding="utf-8", errors="replace")
            return gr.update(value=content, visible=True), gr.update(value="", visible=False)

        def _load_writing_demo():
            """从 examples 加载 Nature 量子计算综述案例。"""
            intent = (
                "Create a Nature-style summary of three quantum computing papers: "
                "quantum reverse annealing (D-Wave), quantum chaos in macrospin dynamics, "
                "and Bell nonlocality advances. Synthesize around quantum-classical boundaries theme."
            )
            demo_state = {"mode": "demo", "output_dir": None, "choice_to_rel": DEMO_CHOICE_TO_REL}
            first_choice = "quantum_summary_paper.pdf"
            if not (PROJECT_ROOT / "front/examples/quantum_summary_paper.pdf").exists():
                first_choice = "SUMMARY.md" if (PROJECT_ROOT / "front/examples/SUMMARY.md").exists() else "PEER_REVIEW.md"
            md_up, pdf_up = _render_example_file(first_choice, demo_state)
            status = "✅ 已加载示例：Nature 量子计算综述（可切换查看 PDF、SUMMARY、PEER_REVIEW）"
            return (
                status,
                md_up,
                pdf_up,
                intent,
                "nature",
                "paper",
                first_choice,
                demo_state,
            )

        def on_load_demo_write():
            return _load_writing_demo()

        # ---------- 写作 -----
        def _data_files_to_paths(files):
            """从 Gradio File 解析附件路径列表。"""
            if files is None:
                return []
            if isinstance(files, str):
                return [files] if files.strip() else []
            if isinstance(files, list):
                out = []
                for f in files:
                    if isinstance(f, str):
                        out.append(f)
                    elif hasattr(f, "name"):
                        out.append(getattr(f, "name", "") or "")
                    else:
                        out.append(str(f))
                return [p for p in out if p]
            return []

        def on_write(raw_input, venue_id, project_id, files):
            _log("SCENE2", "on_write 入口", input_len=len(raw_input or ""), venue_id=venue_id, project_id=project_id, files_count=len(_data_files_to_paths(files)), backend=bool(backend))
            empty_out = ("请输入写作意图", gr.update(), gr.update(), gr.update(), {"mode": "demo", "output_dir": None, "choice_to_rel": None})
            if not raw_input or not (raw_input or "").strip():
                _log("SCENE2", "on_write 跳过", reason="无输入")
                return empty_out
            if backend:
                paths = _data_files_to_paths(files)
                _log("SCENE2", "调用 run_paper_generation", data_files=paths[:3] if paths else [])
                try:
                    async def _run():
                        final = None
                        async for upd in backend.run_paper_generation(
                            raw_input=raw_input.strip(),
                            venue_id=venue_id or "nature",
                            project_type_id=project_id or "paper",
                            data_file_names=paths if paths else None,
                            user_id=backend.memu.user_id,
                        ):
                            final = upd
                        return final

                    result = asyncio.run(_run())
                    _log("SCENE2", "run_paper_generation 完成", result_type=result.get("type"), status=result.get("status"), errors=result.get("errors"))
                    if result.get("type") == "result" and result.get("status") == "success":
                        out_dir = result.get("paper_directory", "") or result.get("output_directory", "")
                        if out_dir:
                            out_path = Path(out_dir)
                        elif result.get("files", {}).get("pdf_final"):
                            out_path = Path(result["files"]["pdf_final"]).resolve().parent.parent
                        else:
                            out_path = None
                        if out_path and out_path.exists():
                            choices, choice_to_rel = _collect_output_files(out_path)
                            if choices:
                                first = choices[0]
                                job_state = {"mode": "job", "output_dir": str(out_path), "choice_to_rel": choice_to_rel}
                                md_up, pdf_up = _render_example_file(first, job_state)
                                radio_upd = gr.update(choices=choices, value=first)
                                _log("SCENE2", "写作完成，刷新示例选项", choices=choices, first=first)
                                return ("✅ 写作完成", md_up, pdf_up, radio_upd, job_state)
                        return ("✅ 写作完成，请查看输出目录", gr.update(value="", visible=True), gr.update(visible=False), gr.update(), {"mode": "demo", "output_dir": None, "choice_to_rel": None})
                    errs = result.get("errors", []) or [result.get("status", "失败")]
                    return (f"❌ {'; '.join(str(e) for e in errs)}", gr.update(), gr.update(), gr.update(), {"mode": "demo", "output_dir": None, "choice_to_rel": None})
                except Exception as e:
                    _log("SCENE2", "on_write 异常", error=str(e))
                    return (f"❌ 写作出错：{e}", gr.update(), gr.update(), gr.update(), {"mode": "demo", "output_dir": None, "choice_to_rel": None})
            _log("SCENE2", "演示模式")
            return ("🔗 前端演示：写作暂未对接后端", gr.update(value="", visible=True), gr.update(value="", visible=False), gr.update(), {"mode": "demo", "output_dir": None, "choice_to_rel": None})

        # ---------- 记忆检索 -----
        def _cat_to_scene(cat):
            if not cat or cat == "all":
                return None
            return cat if cat in ("paper", "writing_event", "parameter_recommendation") else None

        def on_search(query, scope, agent_id, cat, sort_val):
            scope = (scope or "by_agent").strip()
            cat = (cat or "all").strip()
            agent_id = (agent_id or "").strip() or None
            _log("SCENE4", "on_search 入口", query=query[:60] if query else "", scope=scope, agent_id=agent_id, cat=cat, backend=bool(backend))
            if not backend:
                _log("SCENE4", "演示模式")
                return "🔗 前端演示：记忆检索暂未对接后端。", DEMO_RECORDS, [], gr.update(choices=[], value=None)
            scene = _cat_to_scene(cat)
            uid = backend.memu.user_id
            _log("SCENE4", "检索参数", scene=scene, user_id=uid)
            all_records = []
            agent_ids = []
            if scope == "all":
                agent_ids = backend.list_agent_ids() or ["_default"]
            else:
                aid = agent_id or (backend.list_agent_ids() or ["_default"])[0]
                agent_ids = [aid] if aid else ["_default"]
            _log("SCENE4", "遍历 agent", agent_ids=agent_ids)
            for aid in agent_ids:
                _log("SCENE4", "memu_match_and_resolve", agent_id=aid)
                out = backend.memu_match_and_resolve(
                    query=query or "",
                    user_id=uid,
                    agent_id=aid,
                    limit=20,
                )
                _log("SCENE4", "match_and_resolve 返回", agent_id=aid, error=out.get("error"), records_count=len(out.get("records") or []))
                if out.get("error") and not out.get("records"):
                    continue
                for r in (out.get("records") or []):
                    r["agent_id"] = r.get("agent_id") or aid
                    all_records.append(r)
            if scene:
                all_records = [r for r in all_records if r.get("scene") == scene]
            if not all_records and query:
                status = "未找到匹配记录"
            else:
                status = f"找到 {len(all_records)} 条记录"
            _log("SCENE4", "on_search 完成", total_records=len(all_records), status=status)
            rows = []
            choices = []
            for i, r in enumerate(all_records):
                rid = r.get("record_id", "") or f"r{i}"
                desc = (r.get("description") or "")[:50] or r.get("file_name", "") or ""
                fn = r.get("file_name", "")
                aid = r.get("agent_id", "")
                sc = r.get("scene", "")
                rows.append(["✓", rid, desc, fn, aid, sc])
                choices.append((f"{rid} ({sc})", str(i)))
            sel_upd = gr.update(choices=choices, value="0" if choices else None)
            return status, rows, all_records, sel_upd

        def _build_download_links_html(info: dict) -> str:
            """根据 get_download_info 结果构建下载链接 HTML。"""
            if not info:
                return ""
            folder = Path(info.get("resolved_storage_folder", ""))
            if not folder.exists():
                return ""
            try:
                rel_base = folder.relative_to(PROJECT_ROOT)
                base = str(rel_base).replace("\\", "/")
            except ValueError:
                return ""
            links = []
            sc = info.get("scene")
            if sc == "paper":
                for name, label in [("structured.json", "结构化 JSON"), ("summary.md", "摘要 Markdown")]:
                    fp = folder / name
                    if fp.exists():
                        r = f"{base}/{name}"
                        links.append(f'<a href="/gradio_api/file={r}" download target="_blank">{label}</a>')
                fig_dir = folder / "figures"
                if fig_dir.exists():
                    for f in list(fig_dir.glob("*"))[:5]:
                        if f.is_file():
                            r = f"{base}/figures/{f.name}"
                            links.append(f'<a href="/gradio_api/file={r}" download target="_blank">{f.name}</a>')
            elif sc == "parameter_recommendation":
                for name, label in [("summary.md", "摘要"), ("recommendations.json", "推荐 JSON")]:
                    fp = folder / name
                    if fp.exists():
                        r = f"{base}/{name}"
                        links.append(f'<a href="/gradio_api/file={r}" download target="_blank">{label}</a>')
            elif sc == "writing_event":
                pdfs = list(folder.glob("*.pdf"))
                for p in pdfs:
                    r = f"{base}/{p.name}"
                    links.append(f'<a href="/gradio_api/file={r}" download target="_blank">📄 {p.name}</a>')
                for name, label in [("SUMMARY.md", "SUMMARY"), ("PEER_REVIEW.md", "PEER_REVIEW")]:
                    fp = folder / name
                    if fp.exists():
                        r = f"{base}/{name}"
                        links.append(f'<a href="/gradio_api/file={r}" download target="_blank">{label}</a>')
            if not links:
                return ""
            return '<div class="download-links"><strong>下载：</strong>' + " | ".join(links) + "</div>"

        def on_view(records_data, selected_idx):
            """根据选中记录索引展示详情，按 scene 加载对应渲染器，并附加下载链接。"""
            _log("SCENE4", "on_view 入口", has_backend=bool(backend), records_count=len(records_data) if records_data else 0, selected_idx=selected_idx)
            if not backend or not records_data:
                _log("SCENE4", "on_view 跳过", reason="无 backend 或 无记录")
                return "<div class='empty-state'>请先检索，再点击查看</div>"
            try:
                idx = int(selected_idx) if selected_idx not in (None, "") else 0
            except (ValueError, TypeError):
                idx = 0
            idx = max(0, min(idx, len(records_data) - 1))
            rec = records_data[idx] if isinstance(records_data, list) else {}
            rid = rec.get("record_id")
            aid = rec.get("agent_id")
            sc = rec.get("scene")
            uid = backend.memu.user_id
            _log("SCENE4", "on_view 解析记录", record_id=rid, agent_id=aid, scene=sc)
            if not rid or not aid:
                _log("SCENE4", "on_view 跳过", reason="无法解析 record_id/agent_id")
                return "<div class='empty-state'>无法解析记录</div>"
            info = backend.memu_get_download_info(record_id=rid, user_id=uid, agent_id=aid)
            _log("SCENE4", "get_download_info", record_id=rid, has_info=bool(info), folder=info.get("resolved_storage_folder") if info else None)
            if not info:
                _log("SCENE4", "on_view 跳过", reason="get_download_info 返回空")
                return "<div class='empty-state'>记录路径未找到</div>"
            folder = Path(info.get("resolved_storage_folder", ""))
            if not folder.exists():
                return f"<div class='empty-state'>存储路径不存在：{folder}</div>"
            dl_html = _build_download_links_html(info)
            try:
                _log("SCENE4", "on_view 渲染", scene=sc)
                content = ""
                if sc == "paper":
                    sj = info.get("structured_json_path") or str(folder / "structured.json")
                    if Path(sj).exists():
                        data = json.loads(Path(sj).read_text(encoding="utf-8", errors="replace"))
                        content = render_header_html(data) + render_body_html(data)
                elif sc == "parameter_recommendation":
                    rj = info.get("recommendations_json_path") or str(folder / "recommendations.json")
                    if Path(rj).exists():
                        data = json.loads(Path(rj).read_text(encoding="utf-8", errors="replace"))
                        content = format_recommendation_panel_v2(data, expert_mode=False)
                elif sc == "writing_event":
                    sm = info.get("summary_md_path") or str(folder / "SUMMARY.md")
                    if Path(sm).exists():
                        content = Path(sm).read_text(encoding="utf-8", errors="replace")
                if content:
                    return (dl_html + "<hr/>" if dl_html else "") + content
            except Exception as e:
                _log("SCENE4", "on_view 渲染异常", error=str(e))
                return f"<div class='empty-state'>渲染出错：{e}</div>"
            _log("SCENE4", "on_view 无匹配阅读器", scene=sc)
            return (dl_html + "<hr/>" if dl_html else "") + "<div class='empty-state'>暂不支持该场景的阅读器</div>"

        def on_load_agents():
            """加载 agent 列表到 agent_dd，默认选中第一项避免空白。"""
            if backend:
                ids = backend.list_agent_ids() or ["_default"]
                choices = [(i, i) for i in ids]
                default_val = ids[0] if ids else None
                return gr.update(choices=choices, value=default_val)
            return gr.update()

        demo_write_btn.click(
            fn=on_load_demo_write,
            outputs=[
                job_status,
                write_result_md,
                write_result_pdf,
                write_input,
                venue_dd,
                project_dd,
                example_file_radio,
                writing_output_state,
            ],
        )
        write_btn.click(
            fn=on_write,
            inputs=[write_input, venue_dd, project_dd, data_files],
            outputs=[job_status, write_result_md, write_result_pdf, example_file_radio, writing_output_state],
        )
        example_file_radio.change(
            fn=_render_example_file,
            inputs=[example_file_radio, writing_output_state],
            outputs=[write_result_md, write_result_pdf],
        )
        search_btn.click(
            fn=on_search,
            inputs=[query_tb, scope_dd, agent_dd, cat_dd, sort_dd],
            outputs=[lib_status, records_df, records_state, record_selector],
        )
        record_selector.change(
            fn=on_view,
            inputs=[records_state, record_selector],
            outputs=[details_html],
        )
        view_btn.click(
            fn=on_view,
            inputs=[records_state, record_selector],
            outputs=[details_html],
        )
        # 切换场景（先仅更新可见性，避免首次点击未生效）
        def _on_switch(choice):
            return (
                gr.update(visible=(choice == "论文分析")),
                gr.update(visible=(choice == "科研写作")),
                gr.update(visible=(choice == "参数推荐")),
                gr.update(visible=(choice == "记忆查询")),
            )

        # 记忆查询时加载 agent 列表（与切换分离，减少首击失效）
        def _on_switch_with_agents(choice):
            out = _on_switch(choice)
            agent_upd = on_load_agents() if (choice == "记忆查询" and backend) else gr.update()
            return list(out) + [agent_upd]

        nav.change(
            fn=_on_switch_with_agents,
            inputs=[nav],
            outputs=[scene1, scene2, scene3, scene4, agent_dd],
        )

    return demo


if __name__ == "__main__":
    import os
    os.environ.setdefault("no_proxy", "localhost,127.0.0.1")
    demo = build_ui()
    demo.queue()
    demo.launch(
        debug=True,
        share=False,
        theme=gr.themes.Soft(primary_hue="amber", neutral_hue="stone", radius_size="xxl"),
    )
