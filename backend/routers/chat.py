from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
import json
import time
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models.user import User
from utils.auth import get_current_user
from services.agent_service import agent_service
from services.session_service import session_service
from utils.request_logger import request_logger

router = APIRouter()
logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    """对话请求"""
    message: str
    session_id: Optional[str] = None
    chat_history: Optional[List[dict]] = None


class ChatResponse(BaseModel):
    """对话响应"""
    message: str
    citations: List[dict] = []
    session_id: str


@router.post("/message", response_model=ChatResponse)
async def chat_message(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """发送对话消息（非流式）- 使用 LangChain Agent"""
    request_id = request_logger.start_request(
        user_id=current_user.id,
        endpoint="/api/chat/message",
        input_text=request.message,
    )
    start_time = time.time()

    try:
        session_id = request.session_id or f"session_{int(time.time() * 1000)}"

        # 优先从 Redis 加载历史，前端传入的 chat_history 作为备选
        history = []
        if session_id:
            redis_history = session_service.get_history(session_id, current_user.id)
            if redis_history:
                history = redis_history
            elif request.chat_history:
                history = request.chat_history

        # 追加用户消息
        session_service.append_message(session_id, current_user.id, "user", request.message)

        # 同步构建引文（查询到相关文档时显示 100%）
        citations = []
        try:
            from services.vector_store import vector_store
            retrieved_docs = vector_store.search(query=request.message, n_results=5)

            def _is_relevant(doc):
                rel_score = doc.get("relevance_score", 0.0)
                bm25_score = doc.get("bm25_score", 0.0)
                return rel_score > 0.4 and bm25_score > 0.3

            if any(_is_relevant(doc) for doc in retrieved_docs):
                seen_doc_ids = set()
                for doc in retrieved_docs:
                    if not _is_relevant(doc):
                        continue
                    meta = doc.get("metadata", {})
                    doc_id = meta.get("doc_id", "")
                    if doc_id in seen_doc_ids:
                        continue
                    seen_doc_ids.add(doc_id)
                    citations.append({
                        "doc_id": doc_id,
                        "filename": meta.get("filename", ""),
                        "chunk_id": doc.get("chunk_id", ""),
                        "page": meta.get("page"),
                        "relevance_score": 1.0,
                    })
        except Exception as e:
            logger.warning(f"构建引文失败: {e}")

        response = await agent_service.chat(
            message=request.message,
            chat_history=history,
        )

        # 保存 AI 回复到 Redis
        session_service.append_message(session_id, current_user.id, "assistant", response)

        # 首次对话自动生成标题
        if len(history) == 0:
            try:
                title = await agent_service.generate_title(request.message)
                if title:
                    session_service.update_session_title(session_id, current_user.id, title)
            except Exception:
                pass

        request_logger.end_request(
            request_id=request_id,
            output_text=response,
            citations=citations,
            duration=time.time() - start_time,
        )

        return ChatResponse(
            message=response,
            citations=citations,
            session_id=session_id,
        )
    except Exception as e:
        request_logger.end_request(
            request_id=request_id,
            output_text="",
            error=str(e),
            duration=time.time() - start_time,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"对话服务出错: {str(e)}",
        )


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """发送对话消息（流式 SSE）- 使用 LangChain Agent"""
    request_id = request_logger.start_request(
        user_id=current_user.id,
        endpoint="/api/chat/stream",
        input_text=request.message,
    )
    start_time = time.time()
    session_id = request.session_id or f"session_{int(time.time() * 1000)}"

    # 优先从 Redis 加载历史
    history = []
    if session_id:
        redis_history = session_service.get_history(session_id, current_user.id)
        if redis_history:
            history = redis_history
        elif request.chat_history:
            history = request.chat_history

    # 追加用户消息
    session_service.append_message(session_id, current_user.id, "user", request.message)

    full_response = {"content": ""}

    async def generate_stream():
        nonlocal full_response
        citations_sent = []
        try:
            async for item in agent_service.chat_stream(
                message=request.message,
                chat_history=history,
                session_id=session_id,
                user_id=current_user.id,
            ):
                item_type = item.get("type", "")
                if item_type == "thinking":
                    data = {
                        "type": "thinking",
                        "content": item.get("content", ""),
                    }
                    yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                elif item_type == "retrieving":
                    data = {
                        "type": "retrieving",
                        "queries": item.get("queries", []),
                        "doc_count": item.get("doc_count", 0),
                        "documents": item.get("documents", []),
                    }
                    yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                elif item_type == "tool_call":
                    data = {
                        "type": "tool_call",
                        "tool": item.get("tool", ""),
                        "input": item.get("input", ""),
                    }
                    yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                elif item_type == "tool_result":
                    data = {
                        "type": "tool_result",
                        "tool": item.get("tool", ""),
                        "content": item.get("content", ""),
                    }
                    yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                elif item_type == "chunk":
                    content = item.get("content", "")
                    full_response["content"] += content
                    data = {
                        "type": "generating",
                        "content": content,
                    }
                    yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                elif item_type == "citations":
                    citations_sent = item.get("citations", [])
                    data = {
                        "type": "citations",
                        "citations": citations_sent,
                    }
                    yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                elif item_type == "error":
                    data = {
                        "type": "error",
                        "content": item.get("content", ""),
                    }
                    yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

            # 保存 AI 回复到 Redis
            final_content = full_response["content"]
            if final_content:
                session_service.append_message(
                    session_id, current_user.id, "assistant", final_content
                )

            # 首次对话自动生成标题
            if len(history) == 0:
                try:
                    title = await agent_service.generate_title(request.message)
                    if title:
                        session_service.update_session_title(session_id, current_user.id, title)
                except Exception:
                    pass

            request_logger.end_request(
                request_id=request_id,
                output_text=final_content,
                citations=citations_sent,
                duration=time.time() - start_time,
            )

            # 发送完成事件
            done_data = {
                "type": "done",
                "content": "",
                "session_id": session_id,
            }
            yield f"data: {json.dumps(done_data, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"流式对话失败: {e}")
            request_logger.end_request(
                request_id=request_id,
                output_text="",
                error=str(e),
                duration=time.time() - start_time,
            )
            error_data = {
                "type": "error",
                "content": f"对话服务出错: {str(e)}",
            }
            yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        },
    )
