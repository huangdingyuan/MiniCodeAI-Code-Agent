"""
FR-18 MCP 路由
提供工具发现（list_tools）和调用（call_tool）的 HTTP 接口
遵循 MCP 协议规范
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Dict, Any, List

from models.user import User
from utils.auth import get_current_user
from services.mcp_tools import mcp_registry

router = APIRouter()


class ToolCallRequest(BaseModel):
    """工具调用请求"""
    name: str
    arguments: Dict[str, Any] = {}


class ToolCallResponse(BaseModel):
    """工具调用响应"""
    name: str
    result: str
    is_sensitive: bool = False


class ConfirmToolCallRequest(BaseModel):
    """敏感工具确认调用请求"""
    name: str
    arguments: Dict[str, Any] = {}
    confirmed: bool = False


@router.get("/tools")
async def list_tools(current_user: User = Depends(get_current_user)):
    """FR-18 列出所有可用工具（MCP 标准）"""
    tools = mcp_registry.list_tools()
    return {
        "tools": tools,
        "count": len(tools),
    }


@router.get("/tools/{name}")
async def get_tool(
    name: str,
    current_user: User = Depends(get_current_user),
):
    """获取指定工具的定义"""
    tool = mcp_registry.get_tool(name)
    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"工具 {name} 不存在",
        )
    return tool.to_dict()


@router.post("/call", response_model=ToolCallResponse)
async def call_tool(
    request: ToolCallRequest,
    current_user: User = Depends(get_current_user),
):
    """FR-18 调用工具（非敏感工具直接调用）
    敏感工具需要通过 /confirm 调用
    """
    tool = mcp_registry.get_tool(request.name)
    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"工具 {request.name} 不存在",
        )

    if tool.is_sensitive:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"工具 {request.name} 是敏感工具，请使用 /api/mcp/confirm 端点调用并确认",
        )

    result = await mcp_registry.call_tool(request.name, request.arguments)
    return ToolCallResponse(
        name=request.name,
        result=result,
        is_sensitive=False,
    )


@router.post("/confirm", response_model=ToolCallResponse)
async def confirm_and_call_tool(
    request: ConfirmToolCallRequest,
    current_user: User = Depends(get_current_user),
):
    """FR-17 + FR-18 敏感工具确认后调用
    要求 confirmed=true 才会执行
    """
    if not request.confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="敏感工具调用需要用户确认（confirmed=true）",
        )

    tool = mcp_registry.get_tool(request.name)
    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"工具 {request.name} 不存在",
        )

    if not tool.is_sensitive:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"工具 {request.name} 不是敏感工具，请使用 /api/mcp/call 直接调用",
        )

    result = await mcp_registry.call_tool(request.name, request.arguments)
    return ToolCallResponse(
        name=request.name,
        result=result,
        is_sensitive=True,
    )
