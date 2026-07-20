"""
会话管理路由
支持会话历史持久化到 Redis
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional

from models.user import User
from utils.auth import get_current_user
from services.session_service import session_service

router = APIRouter()


class SessionInfo(BaseModel):
    """会话信息"""
    session_id: str
    title: str
    message_count: int
    last_updated: Optional[int] = None


class SessionHistoryResponse(BaseModel):
    """会话历史响应"""
    session_id: str
    title: str
    messages: List[dict]


class CreateSessionRequest(BaseModel):
    """创建会话请求"""
    session_id: Optional[str] = None
    title: Optional[str] = None


class UpdateTitleRequest(BaseModel):
    """更新标题请求"""
    title: str


@router.get("", response_model=List[SessionInfo])
async def list_sessions(current_user: User = Depends(get_current_user)):
    """获取用户所有会话列表"""
    session_ids = session_service.list_user_sessions(current_user.id)
    result = []
    for sid in session_ids:
        messages = session_service.get_history(sid, current_user.id)
        title = session_service.get_session_title(sid, current_user.id) or "新对话"
        result.append(SessionInfo(
            session_id=sid,
            title=title,
            message_count=len(messages),
            last_updated=messages[-1].get("timestamp") if messages else None,
        ))
    # 按最近更新时间排序
    result.sort(key=lambda x: x.last_updated or 0, reverse=True)
    return result


@router.post("", response_model=SessionInfo)
async def create_session(
    request: CreateSessionRequest,
    current_user: User = Depends(get_current_user),
):
    """创建新会话"""
    import time
    session_id = request.session_id or f"session_{int(time.time() * 1000)}"
    title = request.title or "新对话"
    session_service.save_history(session_id, current_user.id, [])
    session_service.update_session_title(session_id, current_user.id, title)
    return SessionInfo(
        session_id=session_id,
        title=title,
        message_count=0,
        last_updated=int(time.time()),
    )


@router.get("/{session_id}", response_model=SessionHistoryResponse)
async def get_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
):
    """获取会话历史"""
    messages = session_service.get_history(session_id, current_user.id)
    title = session_service.get_session_title(session_id, current_user.id) or "新对话"
    return SessionHistoryResponse(
        session_id=session_id,
        title=title,
        messages=messages,
    )


@router.put("/{session_id}/title")
async def update_session_title(
    session_id: str,
    request: UpdateTitleRequest,
    current_user: User = Depends(get_current_user),
):
    """更新会话标题"""
    session_service.update_session_title(session_id, current_user.id, request.title)
    return {"message": "标题已更新", "title": request.title}


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
):
    """删除会话"""
    session_service.delete_session(session_id, current_user.id)
    return {"message": "会话已删除"}
