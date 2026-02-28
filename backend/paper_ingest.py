# backend/paper_ingest.py
"""
论文入库：按 agent_id 加载模板 → 双阶段提取 → 存储 scene/record_id。
不调用 memorize、insert_record；由 app_backend 执行 memorize + DB 落库。
支持单 agent 或多 agent 并行（先实现单 agent 串行，多 agent 可扩展）。
"""

import json
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import MEMU_STORAGE_DIR
from .memu_client import build_storage_path
from .agent_config import (
    get_client_for_step,
    get_model_for_step,
    get_prompt,
    intent_to_agent_ids,
)


def extract_paper_structure(
    file_path: str,
    agent_id: str,
    storage_dir: Optional[Path] = None,
    raw_text_input: Optional[str] = None,
) -> Dict[str, Any]:
    """
    使用 agent 对应模板对 PDF 做双阶段提取，返回结构化 JSON。
    若提供 raw_text_input（如 PyMuPDF 提取 + LLM 校验后的文本），则 S1 直接基于该文本，不再用 file-extract。
    若未提供且 DashScope 不可用，返回兜底结构。
    """
    from .agent_config import invoke_model

    path = Path(file_path)
    print(f"[PAPER_INGEST] extract_paper_structure 入口 | file={file_path} agent_id={agent_id}", flush=True)
    if not path.exists():
        return {"error": f"文件不存在: {file_path}"}
    if path.suffix.lower() != ".pdf":
        return {"error": "仅支持 PDF 论文提取", "metadata": {"title": path.name}}

    m_s1 = get_model_for_step(agent_id, "paper_ingest", "extraction_s1")
    m_s2 = get_model_for_step(agent_id, "paper_ingest", "extraction_s2")
    extraction_s1 = get_prompt(agent_id, "extraction_s1", task_name="paper_ingest")
    if not extraction_s1:
        extraction_s1 = "请按标签格式提取论文核心信息：标题、作者、期刊、年份、摘要、创新点、研究方法、关键词。"

    if raw_text_input and raw_text_input.strip():
        # S1: 基于 PyMuPDF + LLM 校验后的文本做标签提取（无需 file-extract）
        messages = [
            {"role": "system", "content": extraction_s1},
            {"role": "user", "content": f"请按格式从以下文本中提取论文内容：\n\n{raw_text_input[:80000]}"},
        ]
        extracted_text = invoke_model(agent_id, "paper_ingest", "extraction_s1", messages, temperature=0.1)
        if not extracted_text:
            return {"error": "阶段1 提取失败（raw_text 模式）", "metadata": {"title": path.name}}
        extracted_text = extracted_text.strip()
    else:
        # S1: 回退到 file-extract 流程
        client = get_client_for_step(agent_id, "paper_ingest", "extraction_s1")
        if not client:
            return {"error": "DASHSCOPE_API_KEY 未配置", "metadata": {"title": path.name}}
        try:
            file_object = client.files.create(file=path, purpose="file-extract")
        except Exception as e:
            return {"error": f"file-extract 失败: {e}", "metadata": {"title": path.name}}
        try:
            r1 = client.chat.completions.create(
                model=m_s1.get("model", "qwen-long"),
                messages=[
                    {"role": "system", "content": f"fileid://{file_object.id}"},
                    {"role": "system", "content": extraction_s1},
                    {"role": "user", "content": "请按格式提取论文内容。"},
                ],
                temperature=0.1,
            )
            extracted_text = (r1.choices[0].message.content or "").strip()
        except Exception as e:
            return {"error": f"阶段1 提取失败: {e}", "metadata": {"title": path.name}}

    # Stage 2: 格式化为 JSON（统一用 invoke_model，不依赖 client）
    extraction_s2 = get_prompt(agent_id, "extraction_s2", task_name="paper_ingest")
    if not extraction_s2:
        extraction_s2 = "将上述标签内容转为严格 JSON，包含 metadata（title, authors, journal, year, abstract, innovation）, methodology, keywords, figures。"

    s2_messages = [
        {"role": "system", "content": extraction_s2},
        {"role": "user", "content": f"请将以下内容转换为JSON：\n\n{extracted_text}"},
    ]
    raw_json = invoke_model(agent_id, "paper_ingest", "extraction_s2", s2_messages, temperature=0)
    if not raw_json:
        return {"error": "阶段2 格式化失败", "metadata": {"title": path.name}}
    raw_json = raw_json.strip()

    default_structure = {
        "metadata": {"title": path.name, "authors": "", "journal": "Unknown", "year": "", "abstract": "", "innovation": ""},
        "methodology": "", "keywords": [], "figures": [],
    }
    if "```json" in raw_json:
        raw_json = raw_json.split("```json")[1].split("```")[0].strip()
    elif "```" in raw_json:
        raw_json = raw_json.split("```")[1].split("```")[0].strip()
    try:
        data = json.loads(raw_json)
        for k, v in data.items():
            if isinstance(v, dict) and k in default_structure and isinstance(default_structure[k], dict):
                default_structure[k].update(v)
            else:
                default_structure[k] = v
    except json.JSONDecodeError:
        m = re.search(r"\[metadata\.title\]:\s*(.*)", extracted_text)
        if m:
            default_structure["metadata"]["title"] = m.group(1).strip()
    return default_structure


def _build_summary_markdown(structured: Dict[str, Any], file_name: str) -> str:
    """根据 structured 生成基础 Markdown 摘要，与 structured.json 同存。"""
    md = structured.get("metadata") or {}
    lines = [
        f"# {md.get('title', file_name)}",
        "",
        f"**期刊** {md.get('journal', '')} | **年份** {md.get('year', '')}",
        "",
        "## 摘要",
        (md.get("abstract") or "")[:1500],
        "",
        "## 创新点",
        (md.get("innovation") or "")[:1500],
        "",
        "## 方法",
        (structured.get("methodology") or "")[:1500],
        "",
        "## 关键词",
        ", ".join(str(k) for k in (structured.get("keywords") or [])[:20]),
        "",
    ]
    obs = structured.get("observed_phenomena") or ""
    if obs:
        lines.extend(["## 现象/结果", obs[:1000], ""])
    sim = structured.get("simulation_results_description") or ""
    if sim:
        lines.extend(["## 模拟/结果描述", sim[:1000], ""])
    return "\n".join(lines)


def extract_figures(
    file_path: str,
    structured: Dict[str, Any],
    storage_folder: Path,
    agent_id: str = "_default",
    record_id: str = "",
    *,
    image_policy: str = "full_page",
) -> List[Dict[str, Any]]:
    """
    提取论文图像，按 paper_web 格式返回 figures。
    首版使用整页截图；预留 image_policy 扩展：后续可支持 "pymupdf_per_figure" 用 PyMuPDF 精确提取图片并与文字/参数对应。
    图像存于 storage_folder/figures/，image_path 含 record_id 便于回溯。
    """
    try:
        import fitz
    except ImportError:
        return []

    path = Path(file_path)
    if not path.exists():
        return []

    figures_dir = storage_folder / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)
    max_pages = 6

    params = structured.get("parameters", []) or []
    param_summaries = []
    for p in params:
        name = p.get("name", "")
        symbol = p.get("symbol", "")
        unit = p.get("unit", "")
        meaning = p.get("meaning", "")
        param_summaries.append(f"名称: {name}, 符号: {symbol}, 单位: {unit}, 含义: {meaning}")
    param_summary_text = "\n".join(param_summaries) if param_summaries else "（当前未提取到任何参数）"

    figures: List[Dict[str, Any]] = []
    doc = fitz.open(str(path))

    for page_index in range(min(len(doc), max_pages)):
        page = doc[page_index]
        img_name = f"page_{page_index + 1}.png"
        if record_id:
            img_name = f"{record_id}_{img_name}"
        img_path = figures_dir / img_name
        pix = page.get_pixmap(dpi=160)
        pix.save(str(img_path))

        rel_path = f"figures/{img_name}"
        default_caption = f"第 {page_index + 1} 页整页快照"

        # 扩展：image_policy=="pymupdf_per_figure" 时用 param_summary_text 调用 VLM 生成 caption/linked_parameters

        figures.append({
            "id": f"page-{page_index + 1}",
            "caption": default_caption,
            "page": page_index + 1,
            "linked_parameters": [],
            "image_path": rel_path,
        })

    doc.close()
    return figures


def paper_ingest_pdf(
    file_path: str,
    user_id: str,
    agent_ids: Optional[List[str]] = None,
    user_input: str = "",
    storage_dir: Optional[Path] = None,
    pre_extracted: Optional[Dict[str, Any]] = None,
    pre_extracted_for_agent: Optional[str] = None,
) -> Dict[str, Any]:
    """
    论文 PDF 入库：按 agent 提取 → 写入存储 → 构建 record、conversation。
    不调用 memorize、insert_record；由 app_backend 执行。
    若调用方已通过 extract_paper_structure 得到 structured，可传 pre_extracted 与 pre_extracted_for_agent 避免重复提取。
    返回：{"agent_ids": [...], "results": [{"agent_id", "record_id", "record", "conversation", "structured", "resolved_storage_folder"}]}
    """
    path = Path(file_path)
    print(f"[PAPER_INGEST] paper_ingest_pdf 入口 | file={file_path} user_id={user_id} agent_ids={agent_ids}", flush=True)
    if not path.exists():
        print(f"[PAPER_INGEST] paper_ingest_pdf 失败 | 文件不存在", flush=True)
        return {"error": "文件不存在", "results": []}

    storage_dir = Path(storage_dir or MEMU_STORAGE_DIR)

    if agent_ids is None:
        agent_ids = intent_to_agent_ids(file_path=str(path), file_name=path.name)
        print(f"[PAPER_INGEST] 意图识别 | agent_ids={agent_ids}", flush=True)
    if not agent_ids:
        agent_ids = ["_default"]

    results: List[Dict[str, Any]] = []
    for aid in agent_ids:
        print(f"[PAPER_INGEST] 处理 agent | agent_id={aid}", flush=True)
        record_id = str(uuid.uuid4())[:12]
        relative_path = f"paper/{record_id}"
        folder = build_storage_path(storage_dir, user_id, aid, "paper", record_id)
        folder.mkdir(parents=True, exist_ok=True)

        # 1) 提取（若调用方已提供 pre_extracted 且 agent 匹配，则复用）
        if pre_extracted is not None and pre_extracted_for_agent == aid and not pre_extracted.get("error"):
            structured = dict(pre_extracted)
        else:
            structured = extract_paper_structure(str(path), agent_id=aid, storage_dir=storage_dir)
        if structured.get("error"):
            print(f"[PAPER_INGEST] 提取失败 | agent_id={aid} error={structured.get('error')}", flush=True)
            results.append({"agent_id": aid, "record_id": record_id, "error": structured["error"], "structured": structured})
            continue

        # 1b) 图像理解：提取整页截图，合并 figures（预留 pymupdf_per_figure 扩展）
        figs = extract_figures(str(path), structured, folder, agent_id=aid, record_id=record_id)
        if figs:
            structured["figures"] = figs

        # 2) 写入存储：PDF 副本 + structured.json + summary.md（与 JSON 同存，供前端展示）
        import shutil
        dest_pdf = folder / path.name
        shutil.copy2(path, dest_pdf)
        (folder / "structured.json").write_text(json.dumps(structured, ensure_ascii=False, indent=2), encoding="utf-8")
        summary_md = _build_summary_markdown(structured, path.name)
        (folder / "summary.md").write_text(summary_md, encoding="utf-8")

        # 3) 构建 conversation 用于 memU（通用 summary，由 structured 实际字段驱动）
        md = structured.get("metadata") or {}
        summary_pieces = [f"文件: {md.get('title', path.name)}", f"类型: pdf"]
        if md.get("innovation"):
            summary_pieces.append(f"创新点: {md['innovation']}")
        if md.get("abstract"):
            summary_pieces.append(f"摘要: {(md['abstract'] or '')[:500]}")
        methodology = structured.get("methodology") or ""
        if methodology:
            summary_pieces.append(f"方法: {methodology[:500]}")
        keywords = structured.get("keywords")
        if isinstance(keywords, list) and keywords:
            summary_pieces.append(f"关键词: {', '.join(str(k) for k in keywords[:20])}")
        elif isinstance(keywords, str) and keywords:
            summary_pieces.append(f"关键词: {keywords[:300]}")
        obs = structured.get("observed_phenomena") or ""
        if obs:
            summary_pieces.append(f"现象/结果描述: {obs[:500]}")
        sim = structured.get("simulation_results_description") or ""
        if sim:
            summary_pieces.append(f"模拟/结果描述: {sim[:500]}")
        if user_input.strip():
            summary_pieces.append(f"用户备注: {user_input.strip()}")
        summary_text = "\n\n".join(summary_pieces)
        ref_line = f"[MEMU_REF record_id={record_id} scene=paper file={path.name}]"
        conversation = [
            {"role": "user", "content": f"{ref_line}\n\n{summary_text}"},
            {"role": "assistant", "content": "我已阅读并理解该论文的核心内容。"},
            {"role": "user", "content": "请将本论文作为长期记忆，用于后续检索与参数推荐。"},
        ]

        # 4) 构建 record（由 app_backend 调用 memorize、insert_record；memu_error 根据 memorize 结果填入）
        record = {
            "record_id": record_id,
            "task_id": "",
            "scene": "paper",
            "original_path": relative_path,
            "file_name": path.name,
            "simplified_path": "",
            "description": summary_text[:2000],
            "user_input": user_input.strip(),
            "user_id": user_id,
            "agent_id": aid,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
            "memu_error": "",
        }

        results.append({
            "agent_id": aid,
            "record_id": record_id,
            "record": record,
            "conversation": conversation,
            "structured": structured,
            "resolved_storage_folder": str(folder),
        })
        print(f"[PAPER_INGEST] agent 完成 | agent_id={aid} record_id={record_id}", flush=True)

    print(f"[PAPER_INGEST] paper_ingest_pdf 完成 | total_results={len(results)} success={sum(1 for r in results if not r.get('error'))}", flush=True)
    return {"agent_ids": agent_ids, "results": results}
