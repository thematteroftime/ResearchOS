# backend/scientific_writer_client.py
"""
Scientific Writer 能力封装：query 规范化、论文生成、输入/输出记录与进度查询。
- 初始化时维护 .env（API key）
- 将用户粗糙输入 + 格式/类型/数据文件 + 记忆上下文 → Qwen 规范化 → 符合官方案例语法的 query
- 调用 generate_paper，逐步打印便于后端调试，并保存输入记录与最终输出，支持容错与进程状态查询
- 预留格式/ skill 扩展接口
"""

import asyncio
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Callable

from dotenv import load_dotenv

from .config import (
    PROJECT_ROOT,
    WRITING_OUTPUTS,
    JOB_RECORDS_DIR,
    get_env,
    VENUE_FORMATS,
    PROJECT_TYPES,
    PROJECT_TYPE_PROMPT_HINTS,
)

# Load .env from merge_project root so scientific_writer sees ANTHROPIC_* / OPENROUTER_*
_ENV_FILE = PROJECT_ROOT / ".env"
if _ENV_FILE.exists():
    load_dotenv(_ENV_FILE, override=True)


# Optional: Qwen for query normalization (DashScope)
def _get_qwen_client():
    try:
        from openai import OpenAI
        key = get_env("DASHSCOPE_API_KEY")
        if not key:
            return None
        return OpenAI(
            api_key=key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
    except Exception:
        return None


# Scientific Writer API (pip install scientific-writer)
def _import_generate_paper():
    try:
        from scientific_writer import generate_paper as _gp
        return _gp
    except ImportError:
        return None


# ---------- Query normalization prompt (README/example style) ----------
QUERY_NORMALIZE_SYSTEM = """你是一个科研写作助手。用户会提供：
1) 写作意图的简短描述
2) 选择的出版格式（如 Nature、IEEE）
3) 项目类型（论文、海报、基金等）
4) 要引用的数据/图表文件名（如 results.csv, figure1.png）
5) 来自记忆系统的上下文（.md 格式）

请输出【一句完整的英文 query】，用于调用 Scientific Writer。要求：
- 仿照以下示例的句式和用词，使用 "Create a Nature paper on ..."、"Include ..."、"Present ... from xxx.csv" 等；
- 明确写出所有要引用的文件名，用 "Include ... (file1.png), ... (data.csv)" 或 "Present ... from results.csv" 这样的句式；
- 若有记忆上下文中的关键信息（如用户领域、既往项目），可简要融入主题描述；
- 只输出这一句 query，不要解释或换行。"""


class ScientificWriterClient:
    """封装 scientific-writer 的论文生成与 query 规范化，带记录与进度查询。"""

    def __init__(
        self,
        cwd: Optional[Path] = None,
        output_dir: Optional[Path] = None,
        env_path: Optional[Path] = None,
    ):
        self.cwd = Path(cwd or PROJECT_ROOT)
        self.output_dir = Path(output_dir or WRITING_OUTPUTS)
        if env_path and Path(env_path).exists():
            load_dotenv(env_path, override=True)
        self._generate_paper_fn = _import_generate_paper()
        self._job_storage: Dict[str, Dict[str, Any]] = {}
        self._load_job_storage()

    def _load_job_storage(self) -> None:
        index_file = JOB_RECORDS_DIR / "job_index.json"
        if index_file.exists():
            try:
                self._job_storage = json.loads(index_file.read_text(encoding="utf-8"))
            except Exception:
                self._job_storage = {}

    def _save_job_storage(self) -> None:
        index_file = JOB_RECORDS_DIR / "job_index.json"
        index_file.parent.mkdir(parents=True, exist_ok=True)
        index_file.write_text(json.dumps(self._job_storage, ensure_ascii=False, indent=2), encoding="utf-8")

    def ensure_env(self) -> Dict[str, Any]:
        """检查 .env 中 Scientific Writer 所需变量，返回状态供前端展示。"""
        anthropic_key = get_env("ANTHROPIC_API_KEY")
        openrouter_key = get_env("OPENROUTER_API_KEY")
        return {
            "anthropic_configured": bool(anthropic_key),
            "openrouter_configured": bool(openrouter_key),
            "message": "OK" if anthropic_key else "请配置 ANTHROPIC_API_KEY（.env）",
        }

    def normalize_query(
        self,
        raw_input: str,
        venue_id: str = "nature",
        project_type_id: str = "paper",
        data_file_names: Optional[List[str]] = None,
        memory_md: str = "",
        qwen_model: str = "qwen-plus",
    ) -> Dict[str, Any]:
        """
        将用户粗糙输入 + 选项 + 数据文件名 + 记忆上下文 → 规范化的一条 query。
        若未配置 Qwen，则用模板拼接返回（仍可调用 generate_paper）。
        """
        data_file_names = data_file_names or []
        venue = next((v for v in VENUE_FORMATS if v["id"] == venue_id), VENUE_FORMATS[0])
        ptype = next((t for t in PROJECT_TYPES if t["id"] == project_type_id), PROJECT_TYPES[0])
        prompt_hint = PROJECT_TYPE_PROMPT_HINTS.get(project_type_id, "document")

        # 若没有 Qwen，做简单模板拼接
        client = _get_qwen_client()
        if not client:
            # Fallback: build query from template
            prefix = venue.get("query_prefix", "Create a paper on")
            topic = raw_input.strip() or "the given topic"
            query = f"{prefix} {topic}. "
            if data_file_names:
                query += f"Include data and figures from: {', '.join(data_file_names)}."
            return {"query": query.strip(), "source": "template", "error": None}

        user_content = f"""
【用户描述】{raw_input}

【出版/格式】{venue['label']} ({venue_id})
【项目类型】{ptype['label']} - {prompt_hint}
【要引用的文件】{', '.join(data_file_names) if data_file_names else '无'}

【记忆上下文】(可选)
{memory_md[:3000] if memory_md else '无'}
"""
        try:
            resp = client.chat.completions.create(
                model=qwen_model,
                messages=[
                    {"role": "system", "content": QUERY_NORMALIZE_SYSTEM},
                    {"role": "user", "content": user_content.strip()},
                ],
                temperature=0.3,
            )
            text = resp.choices[0].message.content.strip()
            # 去掉可能的引号
            if text.startswith('"') and text.endswith('"'):
                text = text[1:-1]
            return {"query": text, "source": "qwen", "error": None}
        except Exception as e:
            # 再次回退到模板
            prefix = venue.get("query_prefix", "Create a paper on")
            topic = raw_input.strip() or "the given topic"
            query = f"{prefix} {topic}. "
            if data_file_names:
                query += f"Include data and figures from: {', '.join(data_file_names)}."
            return {"query": query.strip(), "source": "template_fallback", "error": str(e)}

    async def generate_paper(
        self,
        query: str,
        data_files: Optional[List[str]] = None,
        output_dir: Optional[Path] = None,
        job_id: Optional[str] = None,
        log_step: Optional[Callable[[str, str], None]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        调用 scientific_writer.generate_paper，逐步 yield 进度与结果；
        同时写入 job 记录（输入 query + 输出路径），便于追溯与状态查询。
        """
        if not self._generate_paper_fn:
            yield {"type": "result", "status": "failed", "errors": ["scientific_writer 未安装"]}
            return

        job_id = job_id or str(uuid.uuid4())[:8]
        out_dir = Path(output_dir or self.output_dir)
        data_files = data_files or []
        # 将 data_files 转为相对于 cwd 的绝对路径（若为相对路径）
        resolved_data = []
        for f in data_files:
            p = Path(f)
            if not p.is_absolute():
                p = (self.cwd / p).resolve()
            if p.exists():
                resolved_data.append(str(p))

        def log(stage: str, msg: str) -> None:
            if log_step:
                log_step(stage, msg)
            else:
                print(f"[{stage}] {msg}")

        log("init", f"job_id={job_id} query_len={len(query)} data_files={len(resolved_data)}")
        input_record = {
            "job_id": job_id,
            "query": query,
            "data_files": data_files,
            "resolved_data_files": resolved_data,
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
            "status": "running",
            "output_directory": "",
            "pdf_final": "",
            "errors": [],
        }
        self._job_storage[job_id] = input_record
        self._save_job_storage()

        try:
            async for update in self._generate_paper_fn(
                query=query,
                output_dir=str(out_dir),
                data_files=resolved_data if resolved_data else None,
                cwd=str(self.cwd),
                track_token_usage=True,
            ):
                if update.get("type") == "progress":
                    log("progress", f"{update.get('stage','')} {update.get('message','')}")
                    yield update
                elif update.get("type") == "text":
                    yield update
                elif update.get("type") == "result":
                    status = update.get("status", "unknown")
                    files = update.get("files") or {}
                    input_record["status"] = status
                    input_record["output_directory"] = update.get("paper_directory", "")
                    input_record["pdf_final"] = files.get("pdf_final") or ""
                    input_record["tex_final"] = files.get("tex_final") or ""
                    input_record["errors"] = update.get("errors") or []
                    input_record["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
                    if "token_usage" in update:
                        input_record["token_usage"] = update["token_usage"]
                    self._job_storage[job_id] = input_record
                    self._save_job_storage()
                    # 持久化单次 job 详情到文件，便于追溯
                    job_file = JOB_RECORDS_DIR / f"job_{job_id}.json"
                    job_file.write_text(
                        json.dumps({**input_record, "full_result": update}, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                    log("complete", f"status={status} pdf={input_record['pdf_final']}")
                    yield {
                        **update,
                        "job_id": job_id,
                        "paper_directory": input_record.get("output_directory") or update.get("paper_directory", ""),
                    }
        except Exception as e:
            input_record["status"] = "failed"
            input_record["errors"] = [str(e)]
            input_record["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
            self._job_storage[job_id] = input_record
            self._save_job_storage()
            log("error", str(e))
            yield {"type": "result", "status": "failed", "errors": [str(e)]}

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """查询单次任务状态（输入 + 输出路径 + status）。"""
        return self._job_storage.get(job_id)

    def list_jobs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """列出最近任务，便于前端展示与追溯。"""
        items = list(self._job_storage.values())
        items.sort(key=lambda x: x.get("started_at", ""), reverse=True)
        return items[:limit]

    # ---------- 扩展接口：前端可注册自定义格式/类型 ----------
    def get_venue_formats(self) -> List[Dict[str, str]]:
        return list(VENUE_FORMATS)

    def get_project_types(self) -> List[Dict[str, str]]:
        return list(PROJECT_TYPES)
