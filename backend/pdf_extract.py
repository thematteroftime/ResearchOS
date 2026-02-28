# backend/pdf_extract.py
"""
基于 PyMuPDF 的 PDF 原始提取 + LLM 公式校验。
- 文本提取：页级纯文本（公式易出错，文字较稳）
- 图像提取：保存图片并记录页码与位置
- 公式校验：将提取文字交给大模型评估，重点修正公式部分
参考：ex.py、pdf_code.py
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False


def extract_raw_with_pymupdf(
    file_path: str,
    output_image_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    使用 PyMuPDF 提取 PDF 的原始文本与图像。
    返回：
    - raw_text: 全文（按页拼接）
    - pages: [{"page_num": int, "text": str}]
    - images: [{"page": int, "path": str, "filename": str, "index": int}]
    """
    if not PYMUPDF_AVAILABLE:
        return {"error": "PyMuPDF 未安装", "raw_text": "", "pages": [], "images": []}

    path = Path(file_path)
    if not path.exists():
        return {"error": f"文件不存在: {file_path}", "raw_text": "", "pages": [], "images": []}
    if path.suffix.lower() != ".pdf":
        return {"error": "仅支持 PDF", "raw_text": "", "pages": [], "images": []}

    base_dir = output_image_dir or (path.parent / "extracted_images")
    base_dir = Path(base_dir)
    base_dir.mkdir(parents=True, exist_ok=True)

    pages: List[Dict[str, Any]] = []
    images: List[Dict[str, Any]] = []
    full_parts: List[str] = []

    try:
        doc = fitz.open(str(path))
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            pages.append({"page_num": page_num + 1, "text": text})
            full_parts.append(f"--- 第 {page_num + 1} 页 ---\n{text}")

            # 提取图片
            image_list = page.get_images(full=True)
            for img_index, img_info in enumerate(image_list):
                xref = img_info[0]
                try:
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    image_ext = base_image.get("ext", "png")
                    filename = f"page_{page_num + 1}_img_{img_index + 1}.{image_ext}"
                    img_path = base_dir / filename
                    img_path.write_bytes(image_bytes)
                    try:
                        rel_path = img_path.resolve().relative_to(Path.cwd())
                        image_path_str = str(rel_path).replace("\\", "/")
                    except ValueError:
                        image_path_str = str(img_path)
                    images.append({
                        "page": page_num + 1,
                        "path": str(img_path),
                        "image_path": image_path_str,
                        "filename": filename,
                        "index": img_index + 1,
                    })
                except Exception:
                    pass
        doc.close()
    except Exception as e:
        return {"error": str(e), "raw_text": "", "pages": [], "images": []}

    raw_text = "\n\n".join(full_parts)
    return {"raw_text": raw_text, "pages": pages, "images": images}


def verify_formulas_with_llm(
    raw_text: str,
    agent_id: str = "_default",
    max_chars: int = 15000,
) -> Dict[str, Any]:
    """
    将 PyMuPDF 提取的文本交给大模型做公式部分校验与修正。
    文字不易出错，公式易出错；模型评估后仅修正公式部分，返回修正后的全文。
    """
    from .agent_config import invoke_model

    if not raw_text or not raw_text.strip():
        return {"corrected_text": "", "error": None}

    text_to_verify = raw_text[:max_chars]
    if len(raw_text) > max_chars:
        text_to_verify += "\n\n[以下内容已截断，未参与校验]"

    from .config import CONFIG_PROMPTS_DIR
    prompt_path = CONFIG_PROMPTS_DIR / "formula_verification.txt"
    system = prompt_path.read_text(encoding="utf-8").strip() if prompt_path.exists() else (
        "你是学术文档解析专家。评估并修正 PDF 提取文本中的公式部分，只输出修正后的完整文本。"
    )

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"请评估并修正以下从 PDF 提取的文本中的公式部分：\n\n{text_to_verify}"},
    ]

    out = invoke_model(agent_id, "paper_ingest", "formula_verification", messages, temperature=0.1)
    if not out:
        return {"corrected_text": raw_text, "error": "模型调用失败，保留原文"}
    return {"corrected_text": out.strip(), "error": None}
