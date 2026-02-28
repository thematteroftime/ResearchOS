# backend/app_backend.py
"""
统一后端：交付前端所需全部能力。
- 子模块：MemUClient（记忆）、ScientificWriterClient（写作/查询/进度）、agent_config（配置/意图）、paper_ingest、parameter_recommendation
- 对外：.env 维护、入库/推荐/写作/检索、任务状态、格式/类型选项（可扩展）
- 场景封装：论文上传分析（三线程 + 文献扩展）、写作、参数推荐、记忆查询。
"""

import asyncio
import json
import time
import uuid
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

from .config import PROJECT_ROOT, DATA_DIR, get_env
from .config import VENUE_FORMATS, PROJECT_TYPES, PROJECT_TYPE_PROMPT_HINTS
from .memu_client import create_memu_client
from .scientific_writer_client import ScientificWriterClient
from . import agent_config as agent_config_module
from . import paper_ingest as paper_ingest_module
from . import parameter_recommendation as param_rec_module


def _step_print(scenario: str, step: str, msg: str = "", **kwargs: Any) -> None:
    """每次场景调用的小步骤统一打印，便于后台知晓进度。"""
    parts = [f"[STEP] {scenario} | {step}"]
    if msg:
        parts.append(str(msg)[:300])
    if kwargs:
        try:
            brief = json.dumps(kwargs, ensure_ascii=False)[:400]
            parts.append(brief)
        except Exception:
            parts.append(str(kwargs)[:400])
    print(" ".join(parts), flush=True)


class AppBackend:
    """
    前端整体功能交付类。
    其下两个子模块：
    - memu: MemUClient（user_id / agent_id 保留，便于多 agent）
    - writer: ScientificWriterClient（论文生成、query 规范化、任务记录）
    """

    def __init__(
        self,
        project_root: Optional[Path] = None,
        memu_user_id: Optional[str] = None,
        memu_agent_id: Optional[str] = None,
        memu_backend: Optional[str] = None,
        memu_db_path: Optional[Path] = None,
        memu_storage_dir: Optional[Path] = None,
    ):
        self.project_root = Path(project_root or PROJECT_ROOT)
        self.data_dir = self.project_root / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        backend = memu_backend or get_env("MEMU_BACKEND") or "cloud"
        memu_kwargs: Dict[str, Any] = {
            "user_id": memu_user_id,
            "agent_id": memu_agent_id,
        }
        if memu_db_path is not None:
            memu_kwargs["db_path"] = memu_db_path
        if memu_storage_dir is not None:
            memu_kwargs["storage_dir"] = memu_storage_dir
        self.memu = create_memu_client(backend=backend, **memu_kwargs)
        self.writer = ScientificWriterClient(
            cwd=self.project_root,
            output_dir=self.project_root / "writing_outputs",
            env_path=self.project_root / ".env",
        )

    # ---------- .env 与配置 ----------
    def ensure_env(self) -> Dict[str, Any]:
        """检查后端所需环境变量（写作、memU、论文提取/参数推荐），供前端展示/提示。"""
        writer_status = self.writer.ensure_env()
        dashscope_key = get_env("DASHSCOPE_API_KEY")
        memu_key = get_env("MEMU_API_KEY")
        memu_base = get_env("MEMU_BASE_URL")
        return {
            **writer_status,
            "dashscope_configured": bool(dashscope_key),
            "memu_configured": bool(memu_key),
            "memu_base_url": memu_base or "https://api.memu.so",
            "message": writer_status.get("message", "OK"),
        }

    def get_venue_formats(self) -> List[Dict[str, str]]:
        """前端下拉：出版/格式选项（可扩展）。"""
        return self.writer.get_venue_formats()

    def get_project_types(self) -> List[Dict[str, str]]:
        """前端下拉：项目类型（论文/海报/基金/综述等，可扩展）。"""
        return self.writer.get_project_types()

    # ---------- Query 规范化（含记忆） ----------
    def _normalize_query_via_agent_config(
        self,
        raw_input: str,
        venue_id: str,
        project_type_id: str,
        data_file_names: List[str],
        memory_md: str,
        agent_id: str,
    ) -> Optional[str]:
        """通过 agent_config.invoke_model 做 query 规范化，返回规范化后的 query 或 None。"""
        venue = next((v for v in VENUE_FORMATS if v["id"] == venue_id), VENUE_FORMATS[0])
        ptype = next((t for t in PROJECT_TYPES if t["id"] == project_type_id), PROJECT_TYPES[0])
        prompt_hint = PROJECT_TYPE_PROMPT_HINTS.get(project_type_id, "document")
        user_content = f"""
【用户描述】{raw_input}

【出版/格式】{venue['label']} ({venue_id})
【项目类型】{ptype['label']} - {prompt_hint}
【要引用的文件】{', '.join(data_file_names) if data_file_names else '无'}

【记忆上下文】(可选)
{memory_md[:3000] if memory_md else '无'}
"""
        from .scientific_writer_client import QUERY_NORMALIZE_SYSTEM
        messages = [
            {"role": "system", "content": QUERY_NORMALIZE_SYSTEM},
            {"role": "user", "content": user_content.strip()},
        ]
        out = agent_config_module.invoke_model(
            agent_id, "writing", "query_normalize", messages, temperature=0.3
        )
        if not out:
            return None
        if out.startswith('"') and out.endswith('"'):
            out = out[1:-1]
        return out.strip()

    def normalize_query(
        self,
        raw_input: str,
        venue_id: str = "nature",
        project_type_id: str = "paper",
        data_file_names: Optional[List[str]] = None,
        memory_md: Optional[str] = None,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        将用户粗糙输入规范化为一条符合 scientific-writer 案例语法的 query。
        优先使用 agent_config.invoke_model；失败时回退 writer.normalize_query。
        """
        aid = agent_id or self.memu.agent_id or "_default"
        _step_print("normalize_query", "开始", agent_id=aid, raw_len=len(raw_input or ""))
        if memory_md is None and self.memu.enabled:
            memory_md = self.memu.get_memory_context_for_writing(
                topic_hint=raw_input.strip() or "scientific writing",
                user_id=user_id,
                agent_id=aid,
            )
        else:
            memory_md = memory_md or ""

        data_files = data_file_names or []
        _step_print("normalize_query", "agent_config 规范化", memory_len=len(memory_md or ""))
        query = self._normalize_query_via_agent_config(
            raw_input, venue_id, project_type_id, data_files, memory_md, aid
        )
        if query:
            _step_print("normalize_query", "完成", source="agent_config", query_len=len(query))
            return {"query": query, "source": "agent_config", "error": None}
        _step_print("normalize_query", "回退 writer.normalize_query")
        return self.writer.normalize_query(
            raw_input=raw_input,
            venue_id=venue_id,
            project_type_id=project_type_id,
            data_file_names=data_files,
            memory_md=memory_md,
        )

    # ---------- 论文生成：异步流式（供后端/前端消费） ----------
    async def run_paper_generation(
        self,
        raw_input: str,
        venue_id: str = "nature",
        project_type_id: str = "paper",
        data_file_names: Optional[List[str]] = None,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        log_step: Optional[Any] = None,
        use_minimal_query: bool = False,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        场景二：论文写作。输入 raw_input + data 文件 → 记忆增强 → 规范化 query → generate_paper → 输出 PDF 供前端展示。
        use_minimal_query=True 时跳过复杂规范化，使用 claude-scientific-writer README 风格的简洁 query，提高成功率。
        """
        _step_print("run_paper_generation", "开始", raw_len=len(raw_input or ""), use_minimal_query=use_minimal_query)
        # 1) 记忆上下文（minimal 模式可跳过以加快速度）
        memory_md = ""
        if not use_minimal_query and self.memu.enabled:
            memory_md = self.memu.get_memory_context_for_writing(
                topic_hint=raw_input.strip() or "scientific writing",
                user_id=user_id,
                agent_id=agent_id,
            )
        _step_print("run_paper_generation", "记忆上下文", memory_len=len(memory_md))
        if log_step:
            log_step("memory", f"memory_context_len={len(memory_md)}")

        # 2) 规范化 query 或使用 minimal 模式（参考 claude-scientific-writer README 用例）
        if use_minimal_query:
            _step_print("run_paper_generation", "使用 minimal query")
            raw = (raw_input or "").strip()
            data_list = data_file_names or []
            # 若用户已输入完整 Create 风格 query，直接使用
            if raw and len(raw) > 80 and raw.lower().startswith("create "):
                query = raw
            else:
                venue = next((v for v in VENUE_FORMATS if v.get("id") == venue_id), {})
                prefix = venue.get("query_prefix", "Create a paper on")
                query = f"{prefix} {raw or 'quantum chaos in driven spin systems'}."
                if data_list:
                    query += f" Present key findings from the attached files ({', '.join(Path(f).name for f in data_list[:3])}). Keep the manuscript short (800-1000 words)."
            if log_step:
                log_step("query", f"minimal query_len={len(query)}")
        else:
            _step_print("run_paper_generation", "规范化 query")
            norm = self.normalize_query(
                raw_input=raw_input,
                venue_id=venue_id,
                project_type_id=project_type_id,
                data_file_names=data_file_names,
                memory_md=memory_md,
                user_id=user_id,
                agent_id=agent_id,
            )
            query = norm.get("query", "")
            if log_step:
                log_step("query", f"normalized query_len={len(query)} source={norm.get('source','')}")
        if not query:
            yield {"type": "result", "status": "failed", "errors": ["query 规范化失败"]}
            return

        # 3) 解析 data_files：绝对路径直接用；相对路径从 project_root/data_dir 下找
        _step_print("run_paper_generation", "解析 data_files", count=len(data_file_names or []))
        resolved = []
        for name in (data_file_names or []):
            p = Path(name)
            if p.is_absolute():
                pass  # 已是绝对路径，直接检查存在性
            else:
                p = self.project_root / name
                if not p.exists():
                    p = self.data_dir / name
            if p.exists():
                resolved.append(str(p))

        # 4) 调用 writer 生成
        _step_print("run_paper_generation", "调用 writer.generate_paper", resolved_count=len(resolved))
        async for update in self.writer.generate_paper(
            query=query,
            data_files=resolved if resolved else None,
            log_step=log_step,
        ):
            yield update
            # 5) 成功时保存写作输出到 memU（PDF、SUMMARY.md、PEER_REVIEW.md）
            if update.get("type") == "result" and update.get("status") == "success":
                out_dir = update.get("paper_directory") or update.get("output_directory") or ""
                files = update.get("files") or {}
                job_id = update.get("job_id") or ""
                if out_dir or files.get("pdf_final"):
                    try:
                        self.memu.register_writing_event(
                            job_id=job_id,
                            query=query,
                            data_files=data_file_names or [],
                            output_pdf=files.get("pdf_final", ""),
                            output_tex=files.get("tex_final", ""),
                            output_directory=out_dir,
                            user_id=user_id,
                            agent_id=agent_id,
                        )
                        _step_print("run_paper_generation", "写作输出已保存到 memU", output_directory=out_dir)
                    except Exception as e:
                        _step_print("run_paper_generation", "保存写作输出失败", error=str(e))

    # ---------- 任务状态（便于前端轮询与追溯） ----------
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        return self.writer.get_job_status(job_id)

    def list_jobs(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.writer.list_jobs(limit=limit)

    # ---------- 记忆接口（保留 user_id / agent_id） ----------
    def memu_retrieve(
        self,
        query: str,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """场景四：记忆检索。输入用户问题，返回 memU categories/items/resources。"""
        _step_print("memu_retrieve", "开始", query=query[:100] if query else "", agent_id=agent_id)
        out = self.memu.retrieve(query=query, user_id=user_id, agent_id=agent_id)
        _step_print("memu_retrieve", "完成", error=out.get("error"), items_count=len(out.get("items") or []))
        return out

    def memu_memorize(
        self,
        conversation: List[Dict[str, str]],
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        wait: bool = True,
    ) -> Dict[str, Any]:
        return self.memu.memorize(
            conversation=conversation,
            user_id=user_id,
            agent_id=agent_id,
            wait=wait,
        )

    def memu_upload_files(
        self,
        file_paths: List[str],
        scene: Optional[str] = None,
        user_input: str = "",
        simplified_path: Optional[str] = None,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        wait: bool = True,
    ) -> Dict[str, Any]:
        """多格式文件上传至 memU（对话式写入 + 本地记录索引），支持 paper/proposal/data/image 等场景。"""
        _step_print("memu_upload_files", "开始", scene=scene, file_count=len(file_paths or []), agent_id=agent_id)
        out = self.memu.upload_files(
            file_paths=file_paths,
            scene=scene,
            user_input=user_input,
            simplified_path=simplified_path,
            user_id=user_id,
            agent_id=agent_id,
            wait=wait,
        )
        _step_print("memu_upload_files", "完成", record_ids=out.get("record_ids"), error=out.get("error"))
        return out

    def memu_register_writing_event(
        self,
        job_id: str,
        query: str,
        data_files: List[str],
        output_pdf: str = "",
        output_tex: str = "",
        output_directory: str = "",
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        将一次写作任务打包为写作事件记录。
        提供 output_directory 时，会复制 PDF、SUMMARY.md、PEER_REVIEW.md 到 memU 存储。
        """
        return self.memu.register_writing_event(
            job_id=job_id,
            query=query,
            data_files=data_files,
            output_pdf=output_pdf,
            output_tex=output_tex,
            output_directory=output_directory,
            user_id=user_id,
            agent_id=agent_id,
        )

    def memu_search(
        self,
        query: str,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        scene: Optional[str] = None,
        limit: int = 20,
        use_openrouter_query_rewrite: bool = False,
    ) -> Dict[str, Any]:
        """检索记忆：云端 retrieve + 本地记录索引；可选 OpenRouter 改写 query 增强检索。"""
        return self.memu.search(
            query=query,
            user_id=user_id,
            agent_id=agent_id,
            scene=scene,
            limit=limit,
            use_openrouter_query_rewrite=use_openrouter_query_rewrite,
        )

    def memu_get_download_info(
        self,
        record_id: str,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """根据 record_id 返回该条记录的下载路径（资源存储路径、精简版、写作输出等）。"""
        return self.memu.get_download_info(
            record_id=record_id,
            user_id=user_id,
            agent_id=agent_id,
        )

    def memu_download_to_path(
        self,
        record_id: str,
        dest_dir: str,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """真实下载：从 DB 索引取资源存储路径，从存储目录复制到 dest_dir 并写下载日志。"""
        return self.memu.download_to_path(
            record_id=record_id,
            dest_dir=dest_dir,
            user_id=user_id,
            agent_id=agent_id,
        )

    def memu_match_and_resolve(
        self,
        query: str,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        limit: Optional[int] = None,
        use_openrouter_query_rewrite: bool = False,
    ) -> Dict[str, Any]:
        """场景四：记忆查询与源文件解析。用户问题 → memU 匹配 → DB 取路径 → 返回 matched_record_ids + records（含下载路径）。"""
        _step_print("memu_match_and_resolve", "开始", query=query[:80] if query else "", agent_id=agent_id)
        out = self.memu.match_and_resolve(
            query=query,
            user_id=user_id,
            agent_id=agent_id,
            limit=limit,
            use_openrouter_query_rewrite=use_openrouter_query_rewrite,
        )
        _step_print("memu_match_and_resolve", "完成", matched_count=len(out.get("matched_record_ids") or []), error=out.get("error"))
        return out

    def memu_list_records(
        self,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        scene: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """列出本地记录索引（按场景/用户过滤），供前端展示与下载入口。"""
        return self.memu.list_records(
            user_id=user_id,
            agent_id=agent_id,
            scene=scene,
            limit=limit,
        )

    def memu_delete_record(
        self,
        record_id: str,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        remove_from_storage: bool = False,
    ) -> Dict[str, Any]:
        """删除一条 memU 本地记录；remove_from_storage=True 时同时删除资源存储区文件。"""
        return self.memu.delete_record(
            record_id=record_id,
            user_id=user_id,
            agent_id=agent_id,
            remove_from_storage=remove_from_storage,
        )

    def memu_delete_records(
        self,
        record_ids: List[str],
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        remove_from_storage: bool = False,
    ) -> Dict[str, Any]:
        """批量删除 memU 本地记录；remove_from_storage=True 时同时删除资源存储区文件。"""
        return self.memu.delete_records(
            record_ids=record_ids,
            user_id=user_id,
            agent_id=agent_id,
            remove_from_storage=remove_from_storage,
        )

    def memu_log_download(
        self,
        record_id: str,
        source_path: str,
        saved_path: str = "",
        user_id: Optional[str] = None,
    ) -> None:
        """记录一次下载到 memu_download_log。"""
        self.memu.log_download(
            record_id=record_id,
            source_path=source_path,
            saved_path=saved_path,
            user_id=user_id,
        )

    # ---------- PDF 摘要提取（供意图识别，避免 read_text 乱码） ----------
    def get_pdf_abstract_snippet(
        self,
        file_path: str,
        max_chars: int = 1000,
    ) -> str:
        """
        从文件提取可用于意图识别的摘要片段。
        PDF 使用 PyMuPDF 提取，非 PDF 使用 read_text；避免 read_text 对 PDF 产生乱码。
        返回空字符串表示提取失败，调用方可用 file_name 作为兜底。
        """
        path = Path(file_path)
        if not path.exists():
            return ""
        if path.suffix.lower() == ".pdf":
            try:
                from . import pdf_extract as pdf_extract_module
                out = pdf_extract_module.extract_raw_with_pymupdf(str(path))
                if not out.get("error") and out.get("raw_text"):
                    return out["raw_text"][:max_chars]
            except Exception:
                pass
            return ""
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
            return "\n".join(text.splitlines()[:60])[:2000] if text else ""
        except Exception:
            return ""

    # ---------- 意图识别与 agent 配置（供前端入库/推荐前选择 agent） ----------
    def intent_to_agent_ids(
        self,
        input_text: str = "",
        file_path: Optional[str] = None,
        file_name: Optional[str] = None,
        auto_extract_pdf: bool = False,
    ) -> List[str]:
        """
        根据输入或文件名识别应使用的 agent_id 列表（如 physics_agent、cs_agent）。
        auto_extract_pdf=True 时，若 input_text 为空且 file_path 为 PDF，则自动用 get_pdf_abstract_snippet 提取摘要。
        """
        inp = (input_text or "").strip()
        fpath = file_path
        fname = file_name or (Path(fpath).name if fpath else "")
        if not inp and auto_extract_pdf and fpath and Path(fpath).suffix.lower() == ".pdf":
            inp = self.get_pdf_abstract_snippet(str(fpath), max_chars=1000)
        if not inp and fname:
            inp = fname
        _step_print("intent_to_agent_ids", "开始", file_name=fname, input_len=len(inp))
        result = agent_config_module.intent_to_agent_ids(
            input_text=inp,
            file_path=fpath,
            file_name=fname,
        )
        _step_print("intent_to_agent_ids", "完成", agent_ids=result)
        return result

    def get_agent_task_config(
        self,
        agent_id: str,
        task_name: str,
    ) -> Dict[str, Any]:
        """获取某 agent 某任务的配置（prompt 键等），供前端展示或调试。"""
        return agent_config_module.get_task_config(agent_id, task_name)

    def list_agent_ids(self) -> List[str]:
        """返回已配置的 agent_id 列表。"""
        ids = agent_config_module.list_agent_ids()
        _step_print("list_agent_ids", "返回", agent_ids=ids)
        return ids

    # ---------- 论文入库（PDF 结构化提取 + memU + 本地 DB） ----------
    def paper_ingest_pdf(
        self,
        file_path: str,
        user_id: Optional[str] = None,
        agent_ids: Optional[List[str]] = None,
        user_input: str = "",
        storage_dir: Optional[Path] = None,
        pre_extracted: Optional[Dict[str, Any]] = None,
        pre_extracted_for_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        论文 PDF 入库：意图识别（可选）→ 按 agent 模板提取 → 存储 → memU memorize → 本地 DB。
        paper_ingest 返回 results 后，app_backend 对每条执行 memorize + insert_record（含 memu_error）。
        若提供 pre_extracted、pre_extracted_for_agent，则对匹配的 agent 复用，避免重复提取。
        返回 agent_ids、results（每项含 agent_id, record_id, task_id, structured, error）。
        """
        uid = user_id or self.memu.user_id
        resolved_agent_ids = agent_ids
        if resolved_agent_ids is None:
            snippet = self.get_pdf_abstract_snippet(file_path, max_chars=1000)
            resolved_agent_ids = self.intent_to_agent_ids(
                input_text=snippet or Path(file_path).name,
                file_path=file_path,
                file_name=Path(file_path).name,
            )
            _step_print("paper_ingest_pdf", "意图解析(agent_ids=None)", agent_ids=resolved_agent_ids)
        _step_print("paper_ingest_pdf", "开始", file_path=file_path, agent_ids=resolved_agent_ids or [])
        out = paper_ingest_module.paper_ingest_pdf(
            file_path=file_path,
            user_id=uid,
            agent_ids=resolved_agent_ids,
            user_input=user_input,
            storage_dir=storage_dir,
            pre_extracted=pre_extracted,
            pre_extracted_for_agent=pre_extracted_for_agent,
        )
        if out.get("error"):
            _step_print("paper_ingest_pdf", "错误", error=out.get("error"))
            return out
        results = out.get("results", [])
        _step_print("paper_ingest_pdf", "提取完成", results_count=len(results))
        for r in results:
            record = r.get("record")
            if not record:
                continue
            conversation = r.get("conversation") or []
            memu_error = ""
            if conversation and self.memu.enabled:
                _step_print("paper_ingest_pdf", "memu_memorize", agent_id=r.get("agent_id"), record_id=record.get("record_id"))
                m_out = self.memu.memorize(
                    conversation=conversation,
                    user_id=record.get("user_id") or uid,
                    agent_id=record.get("agent_id") or r.get("agent_id"),
                    wait=True,
                )
                if m_out.get("error"):
                    memu_error = m_out.get("error", "memorize failed")
            record["memu_error"] = memu_error
            _step_print("paper_ingest_pdf", "insert_record", record_id=record.get("record_id"))
            self.memu.insert_record(record)
        _step_print("paper_ingest_pdf", "完成", total_records=len(results))
        return out

    # ---------- 参数推荐（多 agent 记忆 + 模板 + 大模型） ----------
    def _get_memory_context_for_agents(
        self,
        query: str,
        user_id: str,
        agent_ids: List[str],
        max_chars_per_agent: int = 3000,
    ) -> str:
        """多 agent 联合检索记忆，合并为一段文本。"""
        parts = []
        for aid in agent_ids:
            out = self.memu.retrieve(query=query, user_id=user_id, agent_id=aid)
            if out.get("error"):
                continue
            text = self.memu.format_retrieve_for_writing(out, max_chars=max_chars_per_agent)
            if text:
                parts.append(f"[{aid}]\n{text}")
        return "\n\n".join(parts) if parts else "（无相关记忆）"

    def parameter_recommendation(
        self,
        structured_paper: Dict[str, Any],
        user_params: Dict[str, Any],
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        agent_ids: Optional[List[str]] = None,
        relevant_forces: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        场景三：参数推荐（final_project DESIGN_ARCHITECTURE 对应）。
        输入：structured_paper + user_params（expected_phenomena 期望模拟现象；参数名 -> 含义/单位）。
        输出：parameter_recommendations（各参数的 range 如 [1,2]、reason 取值原因）、force_field_recommendation（力场与其他模拟参数）。
        """
        uid = user_id or self.memu.user_id
        _step_print("parameter_recommendation", "开始", agent_id=agent_id)
        if agent_ids is None and agent_id is None:
            ctx_parts = [
                (structured_paper.get("metadata") or {}).get("title", ""),
                structured_paper.get("observed_phenomena", ""),
                structured_paper.get("simulation_results_description", ""),
                structured_paper.get("methodology", ""),
                user_params.get("expected_phenomena", ""),
            ]
            memory_query = " ".join(str(x) for x in ctx_parts if x)[:500]
            _step_print("parameter_recommendation", "意图识别", memory_query_len=len(memory_query))
            agent_ids = agent_config_module.intent_to_agent_ids(input_text=memory_query)
        if agent_ids is None:
            agent_ids = [agent_id] if agent_id else ["_default"]
        if not agent_ids:
            agent_ids = ["_default"]
        aid = agent_ids[0]
        memory_context = ""
        if aid != "_default" and self.memu.enabled:
            query_parts = [
                structured_paper.get("observed_phenomena", ""),
                structured_paper.get("simulation_results_description", ""),
                structured_paper.get("methodology", ""),
                user_params.get("expected_phenomena", ""),
                str(user_params),
            ]
            memory_query = " ".join(str(x) for x in query_parts if x)[:500]
            _step_print("parameter_recommendation", "memU 检索", agent_ids=agent_ids)
            memory_context = self._get_memory_context_for_agents(
                memory_query, uid, agent_ids, max_chars_per_agent=3000
            )
        _step_print("parameter_recommendation", "run_parameter_recommendation", agent_ids=agent_ids)
        out = param_rec_module.run_parameter_recommendation(
            structured_paper=structured_paper,
            user_params=user_params,
            user_id=uid,
            agent_id=agent_id,
            agent_ids=agent_ids,
            memory_context=memory_context,
            relevant_forces=relevant_forces,
        )
        # 保存参数推荐结果到存储（summary.md + recommendations.json）
        if not out.get("error"):
            self._save_parameter_recommendation_to_storage(out, uid, aid)
        return out

    def _save_parameter_recommendation_to_storage(
        self, result: Dict[str, Any], user_id: str, agent_id: str
    ) -> Dict[str, Any]:
        """将参数推荐结果持久化到 memU 存储，并写入 DB 记录。路径规范：storage_dir/user_id/agent_id/parameter_recommendation/record_id/"""
        record_id = str(uuid.uuid4())[:12]
        relative_path = f"parameter_recommendation/{record_id}"
        folder = self.memu._build_storage_path(user_id, agent_id, "parameter_recommendation", record_id)
        folder.mkdir(parents=True, exist_ok=True)

        # 1) 写入 recommendations.json
        rec_data = {
            "parameter_recommendations": result.get("parameter_recommendations", {}),
            "force_field_recommendation": result.get("force_field_recommendation", {}),
            "agent_id_used": result.get("agent_id_used", ""),
        }
        (folder / "recommendations.json").write_text(
            json.dumps(rec_data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # 2) 构建并写入 summary.md
        summary_md = self._build_parameter_recommendation_summary_md(result)
        (folder / "summary.md").write_text(summary_md, encoding="utf-8")

        # 3) 构建 description 用于 memorize / 检索
        ref_line = f"[MEMU_REF record_id={record_id} scene=parameter_recommendation]"
        desc = f"{ref_line}\n\nParameter recommendation.\n\n{summary_md[:2000]}"

        task_id = ""
        if self.memu.enabled:
            conversation = [
                {"role": "user", "content": desc},
                {"role": "assistant", "content": "Parameter recommendation saved for retrieval and download."},
            ]
            mem_out = self.memu.memorize(conversation=conversation, user_id=user_id, agent_id=agent_id, wait=True)
            task_id = mem_out.get("task_id", "")
            if mem_out.get("error"):
                _step_print("parameter_recommendation", "memu_memorize 失败", error=mem_out.get("error"))

        record = {
            "record_id": record_id,
            "task_id": task_id,
            "scene": "parameter_recommendation",
            "original_path": relative_path,
            "file_name": "summary.md",
            "simplified_path": "",
            "description": desc[:4000],
            "user_input": "",
            "user_id": user_id,
            "agent_id": agent_id,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
        }
        self.memu.insert_record(record)
        _step_print("parameter_recommendation", "已保存到存储", record_id=record_id)
        return {"record_id": record_id, "task_id": task_id}

    def _build_parameter_recommendation_summary_md(self, result: Dict[str, Any]) -> str:
        """从参数推荐结果构建 Markdown 汇总（参考 writing_outputs SUMMARY 风格）。"""
        lines = ["# 参数推荐汇总\n", "## 参数推荐区间\n"]
        precs = result.get("parameter_recommendations", {})
        for name, v in precs.items():
            if isinstance(v, dict):
                lines.append(f"- **{name}**: {v.get('range', v)}\n")
                if v.get("reason"):
                    lines.append(f"  - 原因: {v['reason']}\n")
            else:
                lines.append(f"- **{name}**: {v}\n")
        lines.append("\n## 力场与模拟参数\n")
        ff = result.get("force_field_recommendation", {})
        for k, val in ff.items():
            lines.append(f"- **{k}**: {val}\n")
        return "".join(lines)

    # ---------- 项目提议（预留：多 agent 记忆 + 模板） ----------
    def project_proposal_optimize(
        self,
        user_idea: str,
        user_id: Optional[str] = None,
        agent_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """根据用户项目想法与多 agent 记忆，输出优化后的项目提议摘要。预留接口，可扩展。"""
        uid = user_id or self.memu.user_id
        if agent_ids is None:
            agent_ids = agent_config_module.intent_to_agent_ids(input_text=user_idea)
        if not agent_ids:
            agent_ids = ["_default"]
        memory_md = ""
        if self.memu.enabled and agent_ids:
            for aid in agent_ids[:3]:
                out = self.memu.retrieve(query=user_idea, user_id=uid, agent_id=aid)
                if not out.get("error"):
                    memory_md += self.memu.format_retrieve_for_writing(out, max_chars=2000) + "\n\n"
        hint = agent_config_module.get_prompt(
            agent_ids[0],
            "prompt",
            task_name="project_proposal",
        )
        if not hint:
            return {"summary": memory_md[:2000] or "（暂无记忆补充）", "status": "placeholder"}
        return {"summary": memory_md[:2000] or "（暂无记忆补充）", "status": "placeholder", "hint_loaded": True}

    # ---------- 修改论文（预留接口） ----------
    def revise_paper(
        self,
        existing_tex_path: str,
        instruction: str,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """根据用户指令修改已有 LaTeX 论文。预留接口，暂不实现具体逻辑。"""
        return {"status": "not_implemented", "existing_tex_path": existing_tex_path, "instruction": instruction}

    # ---------- 扩展接口：注册自定义格式/类型 ----------
    def register_venue_format(self, uid: str, label: str, query_prefix: str) -> None:
        from .config import add_venue_format
        add_venue_format(uid, label, query_prefix)

    def register_project_type(self, uid: str, label: str, hint: str, prompt_hint: str) -> None:
        from .config import add_project_type
        add_project_type(uid, label, hint, prompt_hint)

    # ---------- 写作场景：对比有/无 memU 记忆时的规范化 query ----------
    def compare_normalize_query_with_without_memory(
        self,
        raw_input: str,
        venue_id: str = "nature",
        project_type_id: str = "paper",
        data_file_names: Optional[List[str]] = None,
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        用于测试/调试：对比在不使用 memU 记忆 vs 使用 memU 记忆时，
        scientific-writer 规范化后的 query 有何差异。

        返回：
        - raw_input
        - base_query: memory_md 为空时的规范化 query
        - with_memory_query: 通过 AppBackend.normalize_query（内部拉取 memU 记忆）得到的规范化 query
        """
        _step_print("compare_normalize_query", "开始", raw_len=len(raw_input or ""))
        # 无记忆：直接调用 writer.normalize_query，显式传 memory_md=""
        _step_print("compare_normalize_query", "无记忆 base_query")
        base_norm = self.writer.normalize_query(
            raw_input=raw_input,
            venue_id=venue_id,
            project_type_id=project_type_id,
            data_file_names=data_file_names or [],
            memory_md="",
        )
        base_query = base_norm.get("query", "")

        # 有记忆：走 AppBackend.normalize_query（内部会从 memU 获取 memory_md）
        _step_print("compare_normalize_query", "有记忆 with_memory_query")
        with_mem_norm = self.normalize_query(
            raw_input=raw_input,
            venue_id=venue_id,
            project_type_id=project_type_id,
            data_file_names=data_file_names or [],
            user_id=user_id,
            agent_id=agent_id,
        )
        with_mem_query = with_mem_norm.get("query", "")
        _step_print("compare_normalize_query", "完成", base_len=len(base_query), with_mem_len=len(with_mem_query))

        return {
            "raw_input": raw_input,
            "base_query": base_query,
            "with_memory_query": with_mem_query,
        }

    # ---------- 场景一：论文上传分析（PDF + 用户疑问，三线程 + 文献扩展） ----------
    def paper_analysis_scenario(
        self,
        file_path: str,
        user_question: str,
        user_id: Optional[str] = None,
        agent_ids: Optional[List[str]] = None,
        log_step: Optional[Any] = None,
        skip_formula_verify: bool = False,
    ) -> Dict[str, Any]:
        """
        场景一：论文上传分析（final_project DESIGN_ARCHITECTURE 对应）。
        输入：PDF 路径 + 用户问题（对论文的理解/关注点）。
        输出：JSON（text_thread 结构化）+ Markdown（markdown_summary 供前端展示）；memU 记忆 + DB 落库。
        流程：PyMuPDF 提取 → 意图识别 → LLM 公式校验（可 skip_formula_verify 避免卡壳）→ 文本结构化 → 入库。
        """
        from .agent_config import intent_to_agent_ids  # type: ignore
        from . import pdf_extract as pdf_extract_module

        uid = user_id or self.memu.user_id
        path = Path(file_path)
        _step_print("paper_analysis_scenario", "开始", file_path=file_path)

        raw_text = ""
        corrected_text = ""
        use_pymupdf_flow = False

        # 0) PyMuPDF 原始提取（回退：失败时跳过，后续用 file-extract）
        _step_print("paper_analysis_scenario", "PyMuPDF 提取")
        pymupdf_out = pdf_extract_module.extract_raw_with_pymupdf(str(path))
        if not pymupdf_out.get("error") and pymupdf_out.get("raw_text"):
            raw_text = pymupdf_out["raw_text"]
            use_pymupdf_flow = True
            if log_step:
                log_step("pymupdf", "PyMuPDF 提取成功", data={"len": len(raw_text)})

        # 1) 意图识别：PyMuPDF 成功则用 raw_text[:1000]；否则用 file_name + user_question
        _step_print("paper_analysis_scenario", "意图识别", use_pymupdf=use_pymupdf_flow)
        if agent_ids is None:
            snippet = raw_text[:1000] if use_pymupdf_flow else (user_question or "")
            if log_step:
                log_step("intent_snippet", f"意图识别输入（{path.name}）", data=(snippet[:500] if snippet else "(file_name only)"))
            agent_ids = intent_to_agent_ids(input_text=snippet, file_path=str(path), file_name=path.name)

        if not agent_ids:
            agent_ids = ["_default"]
        main_agent = agent_ids[0]
        if log_step:
            log_step("agents", f"选定 agent_ids={agent_ids}", data={"main_agent": main_agent})

        # 2) LLM 公式校验（仅 PyMuPDF 成功时执行一次，main_agent；skip_formula_verify 可跳过避免卡壳）
        _step_print("paper_analysis_scenario", "公式校验", skip=skip_formula_verify or not (use_pymupdf_flow and bool(raw_text)))
        if use_pymupdf_flow and raw_text and not skip_formula_verify:
            verify_out = pdf_extract_module.verify_formulas_with_llm(raw_text, agent_id=main_agent, max_chars=15000)
            corrected_text = verify_out.get("corrected_text", raw_text)
            if log_step:
                log_step("formula_verify", "公式校验", data={"error": verify_out.get("error") or "ok"})

        # 3) 文本结构化：有 corrected_text 时用 raw_text_input；否则回退 file-extract
        _step_print("paper_analysis_scenario", "extract_paper_structure", main_agent=main_agent)
        raw_text_input = corrected_text if corrected_text else None
        text_thread: Dict[str, Any] = paper_ingest_module.extract_paper_structure(
            file_path=str(path),
            agent_id=main_agent,
            storage_dir=None,
            raw_text_input=raw_text_input,
        )
        if log_step:
            log_step("thread_text", "extract_paper_structure 输出", data=text_thread)

        # 4) 图像理解：由 paper_ingest_pdf 内 extract_figures 完成；此处先占位
        figure_thread: Dict[str, Any] = {}
        if isinstance(text_thread, dict) and text_thread.get("figures"):
            figure_thread = {"figures": text_thread["figures"]}
        if log_step:
            log_step("thread_figure", "图像信息（入库时补充）", data=figure_thread or "(待 paper_ingest_pdf 填充)")

        # 3) 线程 C：用户问题 + memU 记忆融合（不调用大模型，先用 memU 上下文 + 拼接）
        _step_print("paper_analysis_scenario", "memU 记忆融合")
        memory_context = ""
        if self.memu.enabled:
            query_for_memory = user_question or ""
            if not query_for_memory and isinstance(text_thread, dict):
                md = text_thread.get("metadata") or {}
                query_for_memory = md.get("title", "") or ""
            memory_context = self._get_memory_context_for_agents(
                query=query_for_memory or "",
                user_id=uid,
                agent_ids=agent_ids,
                max_chars_per_agent=1500,
            )
        fused_input = user_question
        if memory_context:
            fused_input = f"用户原始问题:\n{user_question}\n\nmemU 记忆上下文:\n{memory_context}"
        user_memory_thread = {
            "user_question": user_question,
            "memory_context": memory_context,
            "fused_input": fused_input,
        }
        if log_step:
            log_step("thread_user_memory", "用户问题 + memU 记忆融合", data=user_memory_thread)

        # 4) 文献/资料扩展：构造 scientific-writer 规范化 query（仅打印，不真正生成 PDF）
        _step_print("paper_analysis_scenario", "scientific-writer 资料扩展 query")
        expanded_query = self.normalize_query(
            raw_input=fused_input or user_question or "",
            venue_id="nature",
            project_type_id="paper",
            data_file_names=[path.name],
            user_id=uid,
            agent_id=main_agent,
        )
        scientific_writer_thread = {
            "raw_input": fused_input or user_question or "",
            "normalized": expanded_query,
        }
        if log_step:
            log_step("thread_research", "scientific-writer 资料扩展 query", data=scientific_writer_thread)

        # 5) 入库：调用 paper_ingest_pdf，将本次分析写入 memU 与本地 DB（scene=paper）
        # 传入已提取的 text_thread，避免 paper_ingest_pdf 内重复调用 extract_paper_structure
        # storage_dir 使用 memu._storage_dir，确保与 get_download_info 解析路径一致（测试时用 test_storage）
        _step_print("paper_analysis_scenario", "paper_ingest_pdf 入库")
        ingest_result = self.paper_ingest_pdf(
            file_path=str(path),
            user_id=uid,
            agent_ids=[main_agent],
            user_input=user_question,
            storage_dir=self.memu._storage_dir,
            pre_extracted=text_thread if (isinstance(text_thread, dict) and not text_thread.get("error")) else None,
            pre_extracted_for_agent=main_agent,
        )
        if log_step:
            log_step("paper_ingest", "paper_ingest_pdf 输出（含 record_id/task_id）", data=ingest_result)

        # 从入库结果补充 figures 到 text_thread/figure_thread（供 markdown 展示）
        for r in ingest_result.get("results", []):
            if r.get("structured", {}).get("figures"):
                text_thread["figures"] = r["structured"]["figures"]
                figure_thread = {"figures": r["structured"]["figures"]}
                break

        # 6) 生成 Markdown 汇总（供前端展示/调试；可被后续多模态大模型重写）
        _step_print("paper_analysis_scenario", "生成 Markdown 汇总")
        title = ""
        if isinstance(text_thread, dict):
            md_meta = text_thread.get("metadata") or {}
            title = md_meta.get("title", "") or path.name
        md_lines = [
            f"# 论文分析概要：{title}",
            "",
            "## Agent 与场景",
            f"- agent_ids: {', '.join(agent_ids)}",
            "",
            "## 线程 A：文本结构化（节选）",
        ]
        md_lines.append("```json")
        try:
            md_lines.append(json.dumps(text_thread, ensure_ascii=False, indent=2)[:2000])
        except Exception:
            md_lines.append(str(text_thread)[:2000])
        md_lines.append("```")
        md_lines += [
            "",
            "## 线程 B：图像/图注信息（占位，仅从 structured.figures 提取）",
            "```json",
        ]
        try:
            md_lines.append(json.dumps(figure_thread, ensure_ascii=False, indent=2)[:1000])
        except Exception:
            md_lines.append(str(figure_thread)[:1000])
        md_lines.append("```")
        md_lines += [
            "",
            "## 线程 C：用户问题 + memU 记忆融合",
            "```text",
            f"用户原始问题:\n{user_question}",
            "",
            f"memU 记忆上下文（截断）:\n{(memory_context or '')[:1000]}",
            "",
            "融合输入（fused_input，供后续模型使用）:",
            (fused_input or "")[:1500],
            "```",
            "",
            "## 文献与资料扩展（scientific-writer 规范化 query）",
            "```json",
        ]
        try:
            md_lines.append(json.dumps(expanded_query, ensure_ascii=False, indent=2)[:1500])
        except Exception:
            md_lines.append(str(expanded_query)[:1500])
        md_lines.append("```")
        md_lines += [
            "",
            "## 入库结果（paper_ingest_pdf）",
            "```json",
        ]
        try:
            md_lines.append(json.dumps(ingest_result, ensure_ascii=False, indent=2)[:1500])
        except Exception:
            md_lines.append(str(ingest_result)[:1500])
        md_lines.append("```")
        markdown_summary = "\n".join(md_lines)

        # 将 Markdown 与 JSON 同存于存储目录（paper/<record_id>/summary.md）
        for r in ingest_result.get("results", []):
            folder = r.get("resolved_storage_folder")
            if folder:
                md_path = Path(folder) / "summary.md"
                md_path.write_text(markdown_summary, encoding="utf-8")

        return {
            "agent_ids": agent_ids,
            "text_thread": text_thread,
            "figure_thread": figure_thread,
            "user_memory_thread": user_memory_thread,
            "scientific_writer_query": scientific_writer_thread,
            "ingest_result": ingest_result,
            "markdown_summary": markdown_summary,
        }
