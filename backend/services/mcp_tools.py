"""
FR-18 MCP（Model Context Protocol）兼容工具接口
将工具接口标准化，便于接入其他 Agent 生态

MCP 协议规范：
- 每个工具包含 name, description, inputSchema, handler
- 通过标准接口注册和调用工具
- 支持工具发现（list_tools）和调用（call_tool）

参考：https://modelcontextprotocol.io/
"""
import json
import logging
from typing import Dict, Any, Callable, List, Optional, Awaitable
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class MCPToolSchema:
    """MCP 工具输入参数 Schema"""
    type: str = "object"
    properties: Dict[str, Any] = None
    required: List[str] = None


@dataclass
class MCPTool:
    """MCP 工具定义（标准化接口）"""
    name: str
    description: str
    inputSchema: MCPToolSchema
    handler: Callable[[Dict[str, Any]], Awaitable[str]]
    is_sensitive: bool = False  # 敏感工具需要人工确认

    def to_dict(self) -> Dict[str, Any]:
        """转换为可序列化的字典"""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": asdict(self.inputSchema) if self.inputSchema else None,
            "is_sensitive": self.is_sensitive,
        }


class MCPToolRegistry:
    """MCP 工具注册中心
    遵循 MCP 协议规范，支持工具发现和调用
    """

    def __init__(self):
        self._tools: Dict[str, MCPTool] = {}

    def register(self, tool: MCPTool):
        """注册工具"""
        if tool.name in self._tools:
            logger.warning(f"工具 {tool.name} 已存在，将被覆盖")
        self._tools[tool.name] = tool
        logger.info(f"MCP 工具已注册: {tool.name}")

    def unregister(self, name: str):
        """注销工具"""
        if name in self._tools:
            del self._tools[name]
            logger.info(f"MCP 工具已注销: {name}")

    def list_tools(self) -> List[Dict[str, Any]]:
        """列出所有工具（MCP 标准）"""
        return [tool.to_dict() for tool in self._tools.values()]

    def get_tool(self, name: str) -> Optional[MCPTool]:
        """获取工具定义"""
        return self._tools.get(name)

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        """调用工具（MCP 标准）"""
        tool = self._tools.get(name)
        if not tool:
            return f"错误：工具 {name} 不存在"

        try:
            result = await tool.handler(arguments) if _is_async(
                tool.handler
            ) else tool.handler(arguments)
            return result
        except Exception as e:
            logger.error(f"MCP 工具调用失败 {name}: {e}")
            return f"工具调用失败: {str(e)}"

    def is_sensitive(self, name: str) -> bool:
        """判断工具是否敏感（需要人工确认）"""
        tool = self._tools.get(name)
        return tool.is_sensitive if tool else False


def _is_async(func) -> bool:
    """判断函数是否是 async"""
    import inspect
    return inspect.iscoroutinefunction(func)


# ==================== 工具实现 ====================
# 将 LangChain @tool 包装为 MCP 标准工具

async def _mcp_search_web(args: Dict[str, Any]) -> str:
    """MCP 包装：网络搜索"""
    from services.agent_service import search_web
    query = args.get("query", "")
    return search_web.invoke({"query": query})


async def _mcp_search_documents(args: Dict[str, Any]) -> str:
    """MCP 包装：文档检索"""
    from services.agent_service import search_documents
    query = args.get("query", "")
    return search_documents.invoke({"query": query})


async def _mcp_summarize_document(args: Dict[str, Any]) -> str:
    """MCP 包装：文档摘要"""
    from services.agent_service import summarize_document
    doc_id = args.get("doc_id", "")
    return summarize_document.invoke({"doc_id": doc_id})


async def _mcp_execute_code(args: Dict[str, Any]) -> str:
    """MCP 包装：代码执行（敏感工具，需用户确认）"""
    from services.agent_service import execute_code
    code = args.get("code", "")
    return execute_code.invoke({"code": code})


# ==================== 注册工具 ====================

def create_mcp_registry() -> MCPToolRegistry:
    """创建并注册 MCP 工具集"""
    registry = MCPToolRegistry()

    # search_web
    registry.register(MCPTool(
        name="search_web",
        description="使用 Tavily 搜索引擎搜索互联网上的最新信息。当用户的问题涉及时事新闻、最新技术、外部知识时使用此工具。",
        inputSchema=MCPToolSchema(
            type="object",
            properties={
                "query": {
                    "type": "string",
                    "description": "搜索查询字符串",
                }
            },
            required=["query"],
        ),
        handler=_mcp_search_web,
        is_sensitive=False,
    ))

    # search_documents
    registry.register(MCPTool(
        name="search_documents",
        description="在用户上传的文档中搜索相关内容。当用户的问题涉及已上传的文档内容、代码分析、文档摘要时使用此工具。",
        inputSchema=MCPToolSchema(
            type="object",
            properties={
                "query": {
                    "type": "string",
                    "description": "文档检索查询字符串",
                }
            },
            required=["query"],
        ),
        handler=_mcp_search_documents,
        is_sensitive=False,
    ))

    # summarize_document
    registry.register(MCPTool(
        name="summarize_document",
        description="对指定文档进行摘要。返回文档的关键句摘要。",
        inputSchema=MCPToolSchema(
            type="object",
            properties={
                "doc_id": {
                    "type": "string",
                    "description": "文档的唯一标识符",
                }
            },
            required=["doc_id"],
        ),
        handler=_mcp_summarize_document,
        is_sensitive=False,
    ))

    # execute_code（敏感工具）
    registry.register(MCPTool(
        name="execute_code",
        description="执行用户提供的 Python 代码。此工具需要用户确认后才能执行。安全限制：禁止访问文件系统、网络、系统命令。",
        inputSchema=MCPToolSchema(
            type="object",
            properties={
                "code": {
                    "type": "string",
                    "description": "要执行的 Python 代码",
                }
            },
            required=["code"],
        ),
        handler=_mcp_execute_code,
        is_sensitive=True,
    ))

    return registry


# 全局 MCP 工具注册中心单例
mcp_registry = create_mcp_registry()
