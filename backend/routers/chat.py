"""聊天路由：基于 Mandol 的溯源问答 + 会话管理 + 真正流式输出。

接口：
- POST /api/chat/sessions        创建会话
- GET  /api/chat/sessions        列出会话
- GET  /api/chat/sessions/{id}   会话详情（含消息）
- PATCH /api/chat/sessions/{id}  更新配置
- DELETE /api/chat/sessions/{id} 删除
- POST /api/chat/stream          SSE 流式问答
- POST /api/chat/save-to-space   将问答存为指定空间的记忆单元
"""
from __future__ import annotations

import json
import uuid
from typing import Any, AsyncIterator, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from ..database import db
from ..models.schemas import (
    ChatRequest,
    ChatResponse,
    MemoryResult,
)
from ..services import llm_profiles as profiles_svc
from ..services.llm_stream import (
    estimate_tokens,
    messages_token_count,
    stream_or_fallback_chat,
    stream_with_thinking_fallback,
)
from ..services.mandol_service import mandol_service
from ..utils.logger import warn

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _hit_to_memory_result(hit: dict) -> MemoryResult:
    """将 Mandol 检索命中转换为 MemoryResult。"""
    metadata = hit.get("metadata", {}) or {}
    return MemoryResult(
        rel_path=metadata.get("source_path", "") or f"mandol:{hit.get('uid', '')}",
        title=metadata.get("entity_name") or metadata.get("event_name") or hit.get("uid", ""),
        snippet=(hit.get("text") or "")[:240],
        score=hit.get("score", 0.0),
        memory_type=metadata.get("type"),
        uid=hit.get("uid"),
        text=hit.get("text"),
        metadata=metadata,
        raw_data=hit.get("raw_data"),
        scores=hit.get("scores"),
        ranks=hit.get("ranks"),
    )


# =============== 会话 CRUD ===============

class SessionCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str = "新会话"
    profile_id: str = ""
    space_name: str = ""
    search_strategy: str = "auto"
    top_k: int = 5
    use_rerank: bool = True
    save_to_space: str = ""


class SessionUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: Optional[str] = None
    profile_id: Optional[str] = None
    space_name: Optional[str] = None
    search_strategy: Optional[str] = None
    top_k: Optional[int] = None
    use_rerank: Optional[bool] = None
    save_to_space: Optional[str] = None


class BatchDeleteRequest(BaseModel):
    """批量删除会话请求体"""
    model_config = ConfigDict(extra="ignore")
    session_ids: List[str] = Field(..., min_length=1, max_length=200)


@router.get("/sessions")
def list_sessions(limit: int = 50) -> List[Dict[str, Any]]:
    return db.list_sessions(limit=limit)


@router.post("/sessions")
def create_session(payload: SessionCreate) -> Dict[str, Any]:
    sid = uuid.uuid4().hex
    sess = db.create_session(
        {
            "id": sid,
            **payload.model_dump(),
        }
    )
    return sess


@router.get("/sessions/{sid}")
def get_session(sid: str, message_limit: int = 200) -> Dict[str, Any]:
    sess = db.get_session(sid)
    if not sess:
        raise HTTPException(status_code=404, detail=f"会话不存在: {sid}")
    sess["messages"] = db.load_session_messages(sid, limit=message_limit)
    return sess


@router.patch("/sessions/{sid}")
def patch_session(sid: str, payload: SessionUpdate) -> Dict[str, Any]:
    fields = {k: v for k, v in payload.model_dump().items() if v is not None}
    sess = db.update_session(sid, **fields)
    if not sess:
        raise HTTPException(status_code=404, detail=f"会话不存在: {sid}")
    return sess


@router.delete("/sessions/{sid}")
def delete_session(sid: str) -> Dict[str, Any]:
    ok = db.delete_session(sid)
    if not ok:
        raise HTTPException(status_code=404, detail=f"会话不存在: {sid}")
    return {"status": "ok", "deleted": sid}


@router.post("/sessions/batch-delete")
def batch_delete_sessions(payload: BatchDeleteRequest) -> Dict[str, Any]:
    """批量删除会话（一次请求，删除多个 sid）"""
    deleted: List[str] = []
    missing: List[str] = []
    for sid in payload.session_ids:
        if db.delete_session(sid):
            deleted.append(sid)
        else:
            missing.append(sid)
    return {"status": "ok", "deleted": deleted, "missing": missing, "count": len(deleted)}


# =============== 检索策略 ===============

def _retrieve(query: str, *, strategy: str, top_k: int, use_rerank: bool,
              space_name: str = "") -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """根据 strategy 选择不同检索路径。

    综合三种检索来源：
    1. 向量检索（holistic/text_only）：基于 embedding 的语义相似度
    2. 图谱检索：从实体子图 + BFS 扩展获取关联文档
    3. RRF 融合：将两路结果去重融合后排序

    Returns:
        (hits, trace_steps) - 命中的单元字典列表 + 检索过程 trace 步骤
    """
    trace: List[Dict[str, Any]] = []
    if not mandol_service.is_enabled:
        return [], trace
    hits: List[Dict[str, Any]] = []
    s = (strategy or "auto").lower()
    try:
        if s == "auto" or s == "holistic" or not s:
            trace.append({"step": "strategy", "value": "holistic（向量+图谱+RRF+Rerank）"})
            hits = mandol_service.holistic_retrieve(
                query, top_k=top_k, use_rerank=use_rerank
            )
            # 图谱扩展：holistic rerank 通常把实体排到后面被截断，
            # 所以不依赖 hits 中的实体，而是主动执行实体子图检索获取种子
            try:
                subgraph = mandol_service.get_entity_subgraph(query, top_k=5)  # noqa: max_depth defaults to 2
                sg_nodes = subgraph.get("nodes", [])
                sg_edges = subgraph.get("edges", [])
                entity_seeds = [
                    str(n.get("uid", n.get("id", "")))
                    for n in sg_nodes
                    if str(n.get("uid", n.get("id", ""))).startswith("entity:")
                ][:3]
                trace.append({
                    "step": "graph_subgraph",
                    "value": f"实体子图检索：{len(sg_nodes)} 节点, {len(sg_edges)} 边, 提取种子 {len(entity_seeds)} 个",
                })
                if entity_seeds:
                    trace.append({
                        "step": "graph_expand",
                        "value": f"图谱 BFS 扩展：种子={entity_seeds}",
                    })
                    expanded = mandol_service.bfs_expand(
                        entity_seeds, per_seed=3, hops=2
                    )
                    existing_uids = {h.get("uid", "") for h in hits}
                    graph_hits = []
                    for ex in expanded:
                        ex_uid = str(ex.get("uid", ""))
                        if ex_uid and ex_uid not in existing_uids:
                            ex_dict = {
                                "uid": ex_uid,
                                "text": (ex.get("raw_data", {}).get("text_content", "") or ex.get("text", ""))[:600],
                                "score": float(ex.get("score", 0.3)),
                                "metadata": ex.get("metadata", {}),
                                "raw_data": ex.get("raw_data", {}),
                                "scores": {"graph_bfs": 0.3},
                                "ranks": {"graph_bfs": len(graph_hits) + 1},
                            }
                            graph_hits.append(ex_dict)
                            existing_uids.add(ex_uid)
                    if graph_hits:
                        trace.append({
                            "step": "graph_expand",
                            "value": f"图谱扩展新增 {len(graph_hits)} 条关联记忆",
                        })
                        hits.extend(graph_hits[:top_k])
                    else:
                        trace.append({
                            "step": "graph_expand",
                            "value": "图谱扩展无新增（所有关联节点已在向量结果中）",
                        })
            except Exception as exc:
                trace.append({"step": "graph_expand", "value": f"图谱扩展失败: {exc}"})
        elif s == "text_only" or s == "vector_only":
            trace.append({"step": "strategy", "value": "text_only（仅向量检索）"})
            hits = mandol_service.search_by_text(query, top_k=top_k)
        elif s == "graph_only":
            trace.append({"step": "strategy", "value": "graph_only（图谱遍历）"})
            # 先通过实体子图查找相关实体
            try:
                subgraph = mandol_service.get_entity_subgraph(query, top_k=top_k)
                trace.append({"step": "graph_subgraph", "value": f"实体子图：{len(subgraph.get('nodes', []))} 节点, {len(subgraph.get('edges', []))} 边"})
                for node in subgraph.get("nodes", []):
                    uid = node.get("uid", node.get("id", ""))
                    if uid and not str(uid).startswith("entity:"):
                        hits.append({
                            "uid": uid,
                            "text": (node.get("text") or node.get("raw_data", {}).get("text_content", ""))[:600],
                            "score": float(node.get("score", 0.5)),
                            "metadata": node.get("metadata", {}),
                            "raw_data": node.get("raw_data", {}),
                        })
            except Exception as exc:
                trace.append({"step": "graph_subgraph", "value": f"实体子图查询失败: {exc}"})
            # 再用 BFS 扩展
            raw = mandol_service.search_graph_relations(
                seed_nodes=[query], max_depth=2, limit=top_k
            )
            for r in raw:
                hits.append(
                    {
                        "uid": f"{r.get('source', '')}->{r.get('target', '')}",
                        "text": json.dumps(r, ensure_ascii=False),
                        "score": r.get("weight", 0.5),
                        "metadata": r,
                    }
                )
        else:
            trace.append({"step": "strategy", "value": f"未知策略 {s}，回退 holistic"})
            hits = mandol_service.holistic_retrieve(
                query, top_k=top_k, use_rerank=use_rerank
            )

        # 空间过滤：若指定了 space_name，只保留在 space 中的 unit
        if space_name and hits:
            try:
                pre = len(hits)
                in_units = mandol_service.list_units_in_space(space_name)
                allowed = {u.get("uid", "") for u in in_units}
                hits = [h for h in hits if h.get("uid", "") in allowed]
                trace.append({
                    "step": "space_filter",
                    "value": f"空间「{space_name}」过滤：{pre} -> {len(hits)}",
                })
            except Exception as exc:
                trace.append({"step": "space_filter", "value": f"空间过滤失败: {exc}"})
    except Exception as exc:
        warn(f"检索失败: {exc}")
        trace.append({"step": "error", "value": f"检索失败: {exc}"})

    return hits, trace


def _hit_to_dict(hit) -> Dict[str, Any]:
    """适配 HolisticHit/单元对象 → 字典（保留以备特殊场景使用）。"""
    if isinstance(hit, dict):
        return hit
    try:
        return {
            "uid": str(getattr(hit, "uid", "")),
            "text": getattr(hit, "text", ""),
            "score": float(getattr(hit, "score", 0.0)),
            "metadata": getattr(hit, "metadata", {}) or {},
        }
    except Exception:
        return {"uid": "", "text": str(hit), "score": 0.0, "metadata": {}}


def _unit_to_dict(unit) -> Dict[str, Any]:
    """适配 MemoryUnit → 字典（保留以备特殊场景使用）。"""
    md = getattr(unit, "metadata", {}) or {}
    raw = getattr(unit, "raw_data", {}) or {}
    return {
        "uid": str(getattr(unit, "uid", "")),
        "text": raw.get("text_content", "") or getattr(unit, "summary_text", ""),
        "score": 0.0,
        "metadata": md,
    }


# =============== SSE 流式问答 ===============

class StreamRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    session_id: str
    message: str
    profile_id: Optional[str] = None
    space_name: Optional[str] = ""
    search_strategy: Optional[str] = "auto"
    top_k: int = 5
    use_rerank: bool = True
    system_prompt: Optional[str] = None
    # 是否把本轮问答自动保存到 save_to_space
    save_to_space: Optional[str] = ""
    save_title: Optional[str] = None  # 可选标题
    # 上下文最大 token 预算
    context_token_budget: int = 3000


def _format_context(hits: List[Dict[str, Any]], budget: int = 2400) -> str:
    """将命中拼成 LLM 上下文，标注检索来源。"""
    parts: List[str] = []
    used = 0
    for i, h in enumerate(hits, 1):
        text = (h.get("text") or "").strip()
        if not text:
            continue
        snippet = text[:600]
        # 标注检索来源
        scores = h.get("scores") or {}
        ranks = h.get("ranks") or {}
        source_tag = ""
        if "graph_bfs" in scores or "graph_bfs" in ranks:
            source_tag = " [图谱扩展]"
        elif "rerank" in scores or "rerank" in ranks:
            source_tag = " [向量+Rerank]"
        elif "dense" in ranks:
            source_tag = " [向量检索]"
        piece = f"[{i}]{source_tag} {snippet}"
        cost = estimate_tokens(piece)
        if used + cost > budget:
            break
        parts.append(piece)
        used += cost
    if not parts:
        return "（无相关记忆）"
    return "\n\n".join(parts)


def _build_history_messages(
    history: List[Dict[str, Any]],
    user_msg: str,
    hits: List[Dict[str, Any]],
    budget: int = 3000,
) -> List[Dict[str, str]]:
    """构造 LLM 消息：system(含记忆) + 历史（裁剪到预算） + user。"""
    sys_prompt = (
        "你是一个基于记忆的智能助手。请结合下方「记忆」回答用户问题。"
        "记忆来源包括 [向量检索]、[向量+Rerank] 和 [图谱扩展] 三种，"
        "请综合参考所有来源的信息给出准确回答。"
        "如果记忆中没有相关信息，请明确说明并基于通用知识回答。"
        "回答末尾列出引用的记忆编号（形如 [1][2]）。\n"
        "【输出格式要求】\n"
        "1) 若你是带推理能力的模型（reasoning/thinking），请先在内部完成推理，"
        "然后必须以正常文本给出最终答案。\n"
        "2) 最终答案必须以 '【回答】' 开头（用于与推理内容分离），"
        "禁止只输出思考过程而不给结论。\n"
        "3) 若记忆为空或不足，请基于通用知识直接回答并标注「未引用记忆」。"
    )
    context = _format_context(hits, budget=max(800, budget // 2))
    sys_block = f"{sys_prompt}\n\n记忆：\n{context}"

    msgs: List[Dict[str, str]] = [{"role": "system", "content": sys_block}]
    # 倒序遍历 history，预算内尽量多塞，从最新往最旧
    remaining = max(400, budget - estimate_tokens(sys_block) - estimate_tokens(user_msg))
    kept: List[Dict[str, str]] = []
    for m in reversed(history):
        c = (m.get("content") or "").strip()
        if not c:
            continue
        cost = estimate_tokens(c)
        if remaining - cost < 0:
            break
        kept.append({"role": m["role"], "content": c})
        remaining -= cost
    kept.reverse()
    msgs.extend(kept)
    msgs.append({"role": "user", "content": user_msg})
    return msgs


async def _event_stream(req: StreamRequest) -> AsyncIterator[bytes]:
    """SSE 生成器。事件类型：trace / hits / token / done / error。"""
    sess = db.get_session(req.session_id)
    if not sess:
        yield _sse("error", {"message": f"会话不存在: {req.session_id}"})
        return

    # 1) 解析 profile
    profile_id = req.profile_id or sess.get("profile_id") or ""
    profile = profiles_svc.get_profile(profile_id) if profile_id else None
    if profile is None:
        profile = profiles_svc.get_default_profile()
    if profile is None:
        # 没有可用 profile -> 用 mandol 系统的 LLM（不再支持流式）
        yield _sse("error", {"message": "未配置 LLM profile，请到「系统设置」添加"})
        return

    space_name = req.space_name or sess.get("space_name") or ""
    strategy = req.search_strategy or sess.get("search_strategy") or "auto"
    top_k = int(req.top_k or sess.get("top_k") or 5)
    use_rerank = bool(req.use_rerank if req.use_rerank is not None else sess.get("use_rerank", True))

    # 2) 检索
    trace: List[Dict[str, Any]] = []  # 完整 trace（持久化到 db，供回看）
    t = {"step": "start", "value": f"开始检索：strategy={strategy}, top_k={top_k}, space={space_name or '全局'}"}
    trace.append(t)
    yield _sse("trace", t)
    t = {"step": "profile", "value": f"使用模型：{profile.get('name','?')} ({profile.get('model','')})"}
    trace.append(t)
    yield _sse("trace", t)
    t = {"step": "query", "value": f"用户问题：{req.message[:200]}"}
    trace.append(t)
    yield _sse("trace", t)
    hits, retrieve_trace = _retrieve(
        req.message, strategy=strategy, top_k=top_k, use_rerank=use_rerank,
        space_name=space_name,
    )
    # 检索阶段返回的 trace 合并进来 + 同步推送给前端 SSE
    for t_step in retrieve_trace:
        trace.append(t_step)
        yield _sse("trace", t_step)
    t_hc = {"step": "hits_count", "value": f"命中 {len(hits)} 条"}
    trace.append(t_hc)
    yield _sse("trace", t_hc)
    # 把每个 hit 的关键信息也作为 trace 推送（snippet+score），便于前端展示
    for i, h in enumerate(hits, 1):
        meta = h.get("metadata") or {}
        title = meta.get("entity_name") or meta.get("event_name") or h.get("uid", "")
        snippet = (h.get("text") or "").strip()[:120].replace("\n", " ")
        score = h.get("score", 0.0)
        space = (meta.get("spaces") or ["?"])[0]
        t_hit = {
            "step": "hit",
            "value": f"  [{i}] {title}  · score={float(score):.3f}  · 空间={space}",
            "uid": h.get("uid", ""),
            "title": title,
            "snippet": snippet,
            "score": score,
        }
        trace.append(t_hit)
        yield _sse("trace", t_hit)

    # 把 hits 推给前端（注意去重：每个 uid 只发一次）
    seen: set = set()
    for h in hits:
        uid = str(h.get("uid", ""))
        if uid in seen:
            continue
        seen.add(uid)
        yield _sse("hit", _hit_to_memory_result(h).model_dump())

    # 3) 构造历史 + 消息
    history = db.load_session_messages(req.session_id, limit=200)
    msgs = _build_history_messages(
        history, req.message, hits, budget=int(req.context_token_budget or 3000)
    )
    t_ctx = {"step": "context", "value": f"构造消息 {len(msgs)} 条，约 {messages_token_count(msgs)} tokens（其中 system≈{messages_token_count([msgs[0]])} tokens，含 {len(hits)} 条记忆）"}
    trace.append(t_ctx)
    yield _sse("trace", t_ctx)
    t_gen = {"step": "generating", "value": f"开始流式生成（model={profile.get('model','')}）"}
    trace.append(t_gen)
    yield _sse("trace", t_gen)

    # 4) 保存 user 消息
    db.append_session_message(
        req.session_id, "user", req.message,
        memories=[_hit_to_memory_result(h).model_dump() for h in hits],
    )

    # 5) 流式生成（支持 reasoning 模型的 thinking 内容；带 <think>/</think> 兜底切分）
    full_text = ""
    full_thinking = ""
    answer_text = ""  # 兜底字段初始化（流式抛错时也要能取到）
    try:
        async for piece in stream_with_thinking_fallback(profile, msgs):
            kind = piece.get("kind")
            text = piece.get("text") or ""
            if kind == "thinking":
                full_thinking += text
                yield _sse("thinking", {"content": text})
            else:
                full_text += text
                yield _sse("token", {"content": text})
    except Exception as exc:
        warn(f"流式生成失败: {exc}")
        yield _sse("error", {"message": f"LLM 生成失败: {exc}"})

    # 6) 保存 assistant 消息（含溯源 + 思考）
    db.append_session_message(
        req.session_id, "assistant", answer_text or full_text,
        memories=[_hit_to_memory_result(h).model_dump() for h in hits],
        trace=trace,
        thinking=full_thinking or None,
    )

    # 7) 若用户要求把本轮问答存到指定空间
    save_to = req.save_to_space or sess.get("save_to_space") or ""
    saved_info: Dict[str, Any] = {}
    if save_to and full_text.strip():
        try:
            unit_uid = _save_qa_to_space(
                question=req.message,
                answer=full_text,
                hits=hits,
                space_name=save_to,
                title=req.save_title,
            )
            saved_info = {"saved": True, "space": save_to, "uid": unit_uid}
            t_sv = {"step": "saved", "value": f"已保存到空间「{save_to}」: {unit_uid}"}
            trace.append(t_sv)
            yield _sse("trace", t_sv)
        except Exception as exc:
            warn(f"保存到空间失败: {exc}")
            saved_info = {"saved": False, "error": str(exc)}
            t_se = {"step": "save_error", "value": f"保存到空间失败: {exc}"}
            trace.append(t_se)
            yield _sse("trace", t_se)

    # ⭐ 兜底：模型只输出 reasoning 不输出 content 时（qwen3.5:9b 等），
    # 把 thinking 末尾切出「最终答案」。优先级：先找 "【回答】" / "Final Answer:" 等标记；
    # 没有时取 thinking 末段。
    answer_text = full_text  # 默认就是模型原生输出
    if not answer_text.strip() and full_thinking.strip():
        # 1) 显式标记
        markers = ["【回答】", "【答案】", "Final Answer:", "最终回答：", "Answer:"]
        for m in markers:
            if m in full_thinking:
                answer_text = full_thinking.split(m, 1)[1].strip()
                break
        # 2) 兜底：取最后 800 字，截断在最近的换行/句号
        if not answer_text.strip():
            tail = full_thinking[-1200:].strip()
            for sep in ["\n\n", "。", ".\n", "?\n"]:
                idx = tail.rfind(sep)
                if idx > 100:
                    tail = tail[idx + len(sep):].strip()
                    break
            answer_text = tail
        # 3) 加引用编号提示
        if hits and "[" not in answer_text:
            answer_text = answer_text + "\n\n（参考记忆：" + "、".join(
                f"[{i+1}] {meta.get('entity_name') or h.get('uid','')}" for i, h in enumerate(hits[:3])
            ) + "）"

    yield _sse("done", {
        "answer": answer_text,
        "thinking": full_thinking,
        "memories": [_hit_to_memory_result(h).model_dump() for h in hits],
        "trace": trace,
        "session_id": req.session_id,
        "saved": saved_info,
    })
    t_done = {"step": "done", "value": f"生成完成：回答 {len(answer_text)} 字，思考 {len(full_thinking)} 字，引用 {len(hits)} 条记忆"}
    trace.append(t_done)
    yield _sse("trace", t_done)


def _sse(event: str, data: Any) -> bytes:
    """构造 SSE 事件行。"""
    if not isinstance(data, str):
        data = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {data}\n\n".encode("utf-8")


@router.post("/stream")
async def stream_chat(req: StreamRequest):
    """SSE 流式问答。"""
    return StreamingResponse(
        _event_stream(req),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# =============== 保存问答到空间 ===============

class SaveToSpaceRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    session_id: str
    message_id: int  # chat_session_messages.id
    space_name: str
    title: Optional[str] = None


@router.post("/save-to-space")
def save_to_space(req: SaveToSpaceRequest) -> Dict[str, Any]:
    """把指定 session 消息（user 或 assistant 配对）存为空间内的记忆单元。"""
    msgs = db.load_session_messages(req.session_id, limit=200)
    target = next((m for m in msgs if m.get("id") == req.message_id), None)
    if not target:
        raise HTTPException(status_code=404, detail=f"消息不存在: id={req.message_id}")
    # 找相邻的 user/assistant 配对
    if target["role"] == "assistant":
        question = ""
        for m in msgs:
            if m["id"] < target["id"] and m["role"] == "user":
                question = m["content"]
        answer = target["content"]
    else:
        # user 自己存
        question = target["content"]
        answer = ""
    uid = _save_qa_to_space(
        question=question, answer=answer, hits=target.get("memories") or [],
        space_name=req.space_name, title=req.title,
    )
    return {"status": "ok", "uid": uid, "space": req.space_name}


def _save_qa_to_space(*, question: str, answer: str, hits: List[Dict[str, Any]],
                      space_name: str, title: Optional[str] = None) -> str:
    """把问答对写入指定空间作为记忆单元。

    单元 metadata 携带 question/answer/source 标签，便于后续过滤。
    """
    from datetime import datetime as _dt

    if not mandol_service.is_enabled:
        raise RuntimeError("Mandol 未启用，无法写入空间")

    title = title or question[:30].replace("\n", " ").strip() or "问答"
    text = (
        f"问：{question}\n\n答：{answer}\n\n"
        f"来源记忆：{', '.join(str(h.get('uid', '')) for h in hits if h.get('uid'))}"
    )
    uid_str = f"qa:{space_name}:{int(_dt.utcnow().timestamp() * 1000)}"
    metadata = {
        "type": "qa",
        "question": question,
        "answer": answer,
        "source": "chat",
        "space": space_name,
        "title": title,
        "source_uids": [h.get("uid") for h in hits if h.get("uid")][:10],
    }
    # 用 add_text 高阶 API：自动创建空间、生成嵌入、加到空间
    mandol_service.add_text(
        uid=uid_str,
        text=text,
        metadata=metadata,
        space_name=space_name,
    )
    # 显式持久化
    try:
        mandol_service.save(wait=False)
    except Exception as exc:
        warn(f"持久化失败: {exc}")
    return uid_str


# =============== 兼容旧接口（mock 数据替代） ===============

@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    """旧版非流式问答，保留兼容。"""
    if mandol_service.is_enabled:
        try:
            data = mandol_service.ask(
                req.message,
                top_k=req.top_k,
                use_rerank=req.use_rerank,
                system_prompt=req.system_prompt,
                temperature=req.temperature,
                max_tokens=req.max_tokens,
            )
            memories = [_hit_to_memory_result(h) for h in data.get("hits", [])]
            db.save_message("mandol", "user", req.message)
            db.save_message("mandol", "assistant", data["answer"],
                            memories=[m.model_dump() for m in memories])
            return ChatResponse(
                response=data["answer"],
                memories_used=memories,
                status="ok",
            )
        except Exception as exc:
            warn(f"Mandol 问答失败: {exc}")
    # 回退
    from ..services.agent_service import agent_service
    try:
        context = [m.model_dump() for m in req.context]
        result = await agent_service.run_agent(req.agent, req.message, context=context)
        return ChatResponse(
            response=result["response"],
            memories_used=[MemoryResult(**m) for m in result.get("memories", [])],
            thinking=result.get("thinking"),
            status="ok",
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/history/{agent_id}")
def history(agent_id: str, limit: int = 50) -> List[dict]:
    return db.load_history(agent_id, limit=limit)
