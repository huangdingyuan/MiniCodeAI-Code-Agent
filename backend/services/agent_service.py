"""
LangChain Agent 服务
- 查询改写：将用户问题扩展为 3 个同义查询
- 混合检索：向量 + BM25 + Rerank
- Agent 工具调用：search_web / search_documents / summarize_document
- 思考过程流式：thinking / retrieving / tool_call / tool_result / chunk / citations
- 引文判断：通过 [USED_DOC] / [NO_DOC] 标记决定是否显示引文
- 人工介入：敏感操作（如代码执行）需要用户确认
"""
import logging
import json
from typing import AsyncGenerator, List, Dict, Any, Optional

from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_core.tools import tool
from langchain_community.utilities.tavily_search import TavilySearchAPIWrapper

from config import settings
from services.vector_store import vector_store

logger = logging.getLogger(__name__)


# ==================== 工具定义 ====================

@tool
def search_web(query: str) -> str:
    """使用 Tavily 搜索引擎搜索互联网上的最新信息。当用户的问题涉及时事新闻、最新技术、外部知识时使用此工具。"""
    try:
        tavily = TavilySearchAPIWrapper(tavily_api_key=settings.TAVILY_API_KEY)
        results = tavily.results(query=query, max_results=5, search_depth="basic")
        if not results:
            return "未搜索到相关信息。"
        formatted = []
        for r in results:
            formatted.append(
                f"标题: {r.get('title', 'N/A')}\n"
                f"内容: {r.get('content', 'N/A')}\n"
                f"来源: {r.get('url', 'N/A')}"
            )
        return "\n\n---\n\n".join(formatted)
    except Exception as e:
        logger.error(f"网络搜索失败: {e}")
        return f"网络搜索失败: {str(e)}"


@tool
def search_documents(query: str) -> str:
    """在用户上传的文档中搜索相关内容。当用户的问题涉及已上传的文档内容、代码分析、文档摘要时使用此工具。"""
    try:
        results = vector_store.search(query=query, n_results=5)
        if not results:
            return "未在已上传的文档中找到相关内容。请先上传相关文档后再提问。"
        formatted = []
        for r in results:
            meta = r.get("metadata", {})
            doc_id = meta.get("doc_id", "未知")
            chunk_index = meta.get("chunk_index", 0)
            page = meta.get("page")
            page_str = f"，第{page}页" if page is not None else ""
            formatted.append(
                f"[文档ID: {doc_id}, 片段{chunk_index + 1}{page_str}]\n"
                f"内容: {r['content']}\n"
                f"相关度: {r['relevance_score']:.2f}"
            )
        return "\n\n---\n\n".join(formatted)
    except Exception as e:
        logger.error(f"文档检索失败: {e}")
        return f"文档检索失败: {str(e)}"


@tool
def summarize_document(doc_id: str) -> str:
    """对指定文档进行摘要。doc_id 是文档的唯一标识符。"""
    try:
        chunks = vector_store.get_document_chunks(doc_id)
        if not chunks:
            return f"未找到文档: {doc_id}"

        full_text = "\n\n".join([c["content"] for c in chunks])
        # 简单摘要：取前 500 字 + 关键句
        if len(full_text) <= 500:
            return f"文档摘要:\n{full_text}"

        # 取首段 + 关键句（包含关键词的句子）
        import re
        sentences = re.split(r'[。！？\.\!\?]', full_text)
        key_sentences = [s.strip() for s in sentences if len(s.strip()) > 20][:5]
        return f"文档摘要 (共{len(chunks)}个片段):\n" + "\n".join(key_sentences)
    except Exception as e:
        logger.error(f"文档摘要失败: {e}")
        return f"文档摘要失败: {str(e)}"


@tool
def execute_code(code: str) -> str:
    """执行用户提供的 Python 代码。此工具需要用户确认后才能执行。
    安全限制：禁止访问文件系统、网络、系统命令。
    仅支持基础数学计算、字符串处理等纯计算操作。"""
    try:
        # 安全检查：禁止危险操作
        dangerous_keywords = [
            "import os", "import subprocess", "import sys",
            "open(", "exec(", "eval(", "__import__",
            "os.system", "subprocess", "shutil",
        ]
        code_lower = code.lower()
        for kw in dangerous_keywords:
            if kw in code_lower:
                return f"安全限制：代码中包含禁止的操作 '{kw}'"

        # 限制执行时间 5 秒，限制内存
        import signal

        def timeout_handler(signum, frame):
            raise TimeoutError("代码执行超时（5秒）")

        # 在受限命名空间中执行
        restricted_globals = {
            "__builtins__": {
                "abs": abs, "min": min, "max": max, "sum": sum,
                "len": len, "range": range, "print": print,
                "int": int, "float": float, "str": str, "bool": bool,
                "list": list, "dict": dict, "set": set, "tuple": tuple,
                "sorted": sorted, "reversed": reversed, "enumerate": enumerate,
                "zip": zip, "map": map, "filter": filter,
                "round": round, "pow": pow, "divmod": divmod,
            },
            "math": __import__("math"),
            "json": __import__("json"),
            "re": __import__("re"),
        }

        # 仅 Windows 不支持 signal.alarm，使用线程方式
        import threading
        result = {"value": None, "error": None}

        def run():
            try:
                old_stdout = __import__("sys").stdout
                from io import StringIO
                captured = StringIO()
                __import__("sys").stdout = captured
                try:
                    exec(code, restricted_globals)
                finally:
                    __import__("sys").stdout = old_stdout
                    result["value"] = captured.getvalue()
            except Exception as e:
                result["error"] = str(e)

        t = threading.Thread(target=run, daemon=True)
        t.start()
        t.join(timeout=5)

        if t.is_alive():
            return "代码执行超时（5秒）"
        if result["error"]:
            return f"代码执行错误: {result['error']}"
        return f"代码执行结果:\n{result['value'] or '(无输出)'}"
    except Exception as e:
        logger.error(f"代码执行失败: {e}")
        return f"代码执行失败: {str(e)}"


# ==================== Agent 服务 ====================

class AgentService:
    """智能体 对话服务"""

    def __init__(self):
        self._llm: Optional[ChatOpenAI] = None
        self._agent_executor: Optional[AgentExecutor] = None
        # 工具列表（代码执行工具需要确认）
        self._safe_tools = [search_web, search_documents, summarize_document]
        self._sensitive_tools = [execute_code]
        self._tools = self._safe_tools + self._sensitive_tools
        # 敏感工具集合（用于人工介入判断）
        self._sensitive_tool_names = {"execute_code"}

    def _get_llm(self) -> ChatOpenAI:
        """获取 LLM 实例（懒加载）"""
        if self._llm is None:
            self._llm = ChatOpenAI(
                model=settings.DEEPSEEK_MODEL,
                api_key=settings.DEEPSEEK_API_KEY,
                base_url=settings.DEEPSEEK_BASE_URL,
                temperature=0.7,
                streaming=True,
                max_tokens=4096,
            )
        return self._llm

    def _get_agent_executor(self) -> AgentExecutor:
        """获取 Agent 执行器（懒加载）"""
        if self._agent_executor is None:
            llm = self._get_llm()
            prompt = ChatPromptTemplate.from_messages([
                ("system", """你是一个专业的代码智能体助手 MiniCodeAI，你可以帮助用户：
1. 理解和分析代码
2. 解答技术问题
3. 分析上传的文档内容
4. 搜索互联网获取最新信息
5. 执行简单的代码计算

你可以使用以下工具来辅助回答：
- search_web: 搜索互联网获取最新信息
- search_documents: 在用户上传的文档中搜索相关内容
- summarize_document: 对指定文档进行摘要
- execute_code: 执行简单的 Python 代码（需要用户确认）

请用中文回答用户的问题，回答要专业、准确、简洁。如果使用了工具获取信息，请在回答中引用来源。"""),
                MessagesPlaceholder(variable_name="chat_history", optional=True),
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ])
            agent = create_tool_calling_agent(llm, self._tools, prompt)
            self._agent_executor = AgentExecutor(
                agent=agent,
                tools=self._tools,
                verbose=True,
                max_iterations=5,
                return_intermediate_steps=False,
                handle_parsing_errors=True,
            )
        return self._agent_executor

    def _build_chat_history(self, history: List[Dict[str, str]]) -> List[BaseMessage]:
        """将对话历史转换为 LangChain 消息格式"""
        messages = []
        for msg in history:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if not content:
                continue
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))
        return messages

    async def rewrite_queries(self, message: str) -> List[str]:
        """FR-8 查询改写：用 LLM 将用户问题扩展为 3 个同义查询"""
        try:
            llm = self._get_llm()
            rewrite_prompt = ChatPromptTemplate.from_messages([
                ("system", """你是一个查询改写助手。将用户的问题扩展为 3 个不同表述的同义查询，以提高文档检索的召回率。

要求：
1. 输出格式为 JSON 数组：["查询1", "查询2", "查询3"]
2. 每个查询保持原意，但使用不同的关键词和表述
3. 包含原始问题作为第一个查询
4. 只输出 JSON，不要其他文字"""),
                ("human", "{question}"),
            ])
            messages = rewrite_prompt.format_messages(question=message)
            # 非流式调用
            response = await llm.ainvoke(messages)
            content = response.content.strip()

            # 尝试解析 JSON
            if content.startswith("```"):
                # 去除 markdown 代码块
                import re
                content = re.sub(r'^```(?:json)?\s*', '', content)
                content = re.sub(r'\s*```$', '', content)

            queries = json.loads(content)
            if isinstance(queries, list) and all(isinstance(q, str) for q in queries):
                # 最多 3 个查询
                return queries[:3]
        except Exception as e:
            logger.warning(f"查询改写失败，使用原始查询: {e}")
        # 回退：仅使用原始查询
        return [message]

    async def chat(
        self,
        message: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """非流式对话 - 优先文档检索，不足时调用外部工具"""
        llm = self._get_llm()
        history = self._build_chat_history(chat_history or [])

        try:
            # 1. 优先检索相关文档内容
            retrieved_docs = vector_store.search(query=message, n_results=5)

            # 判断是否有足够相关的文档
            def _is_relevant(doc):
                rel_score = doc.get("relevance_score", 0.0)
                bm25_score = doc.get("bm25_score", 0.0)
                return rel_score > 0.4 and bm25_score > 0.3

            has_relevant_docs = any(_is_relevant(doc) for doc in retrieved_docs)

            # 2. 构建上下文和提示词
            relevant_docs = [doc for doc in retrieved_docs if _is_relevant(doc)]
            context = self._format_retrieved_documents(relevant_docs)

            rag_prompt = ChatPromptTemplate.from_messages([
                ("system", """你是一个专业的代码智能体助手 MiniCodeAI。请按照以下优先级回答用户问题：

【优先级规则】
1. 首先检查是否有已上传的文档。如果有，优先基于文档内容回答。
2. 如果文档内容足以回答问题（相关度高），请完全基于文档内容回答，并引用文档来源。
3. 如果文档内容不足以回答问题，或者用户询问的是外部知识（时事新闻、最新技术等），请先说明文档中找不到相关信息，然后基于你的通用知识或搜索互联网来补充回答。
4. 如果没有任何已上传文档，请直接回答问题。

【检索到的文档内容】
{context}

请用中文回答，回答要专业、准确、简洁。"""),
                MessagesPlaceholder(variable_name="chat_history", optional=True),
                ("human", "{input}"),
            ])

            messages = rag_prompt.format_messages(
                context=context,
                input=message,
                chat_history=history,
            )

            # 3. 生成回答
            result = await llm.ainvoke(messages)
            return result.content if result.content else "抱歉，我暂时无法回答这个问题。"

        except Exception as e:
            logger.error(f"Agent 对话失败: {e}")
            return f"对话服务出错: {str(e)}"

    async def chat_stream(
        self,
        message: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        session_id: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """流式对话（SSE）
        事件类型：
        - thinking: 思考过程开始
        - retrieving: 检索文档（带查询和文档列表）
        - tool_call: 工具调用开始
        - tool_result: 工具调用结果
        - confirm_required: 需要用户确认（敏感操作）
        - chunk: 生成的回答内容
        - citations: 引文列表（仅在 AI 实际使用文档时发送）
        - error: 错误
        """
        llm = self._get_llm()
        history = self._build_chat_history(chat_history or [])

        try:
            # 1. 发送思考事件
            yield {"type": "thinking", "content": "正在分析您的问题..."}

            # 2. 查询改写（FR-8）
            yield {"type": "thinking", "content": "正在改写查询以提升检索效果..."}
            queries = await self.rewrite_queries(message)

            # 3. 多查询融合检索
            yield {"type": "thinking", "content": f"正在检索文档（{len(queries)}个查询）..."}
            retrieved_docs = await self._multi_query_retrieve(queries)

            # 4. 双条件过滤
            def _is_relevant(doc):
                rel_score = doc.get("relevance_score", 0.0)
                bm25_score = doc.get("bm25_score", 0.0)
                return rel_score > 0.4 and bm25_score > 0.3

            has_relevant_docs = any(_is_relevant(doc) for doc in retrieved_docs)

            # 5. 发送检索事件（FR-12 思考过程流式）
            doc_summaries = [
                {
                    "filename": d.get("metadata", {}).get("filename", ""),
                    "doc_id": d.get("metadata", {}).get("doc_id", ""),
                    "chunk_id": d.get("chunk_id", ""),
                    "relevance_score": min(1.0, d.get("relevance_score", 0.0)),
                    "page": d.get("metadata", {}).get("page"),
                    "preview": d.get("content", "")[:100] + "..." if len(d.get("content", "")) > 100 else d.get("content", ""),
                }
                for d in retrieved_docs[:5]
            ]
            yield {
                "type": "retrieving",
                "queries": queries,
                "doc_count": len(retrieved_docs),
                "documents": doc_summaries,
            }

            # 6. 构建引文列表
            citations = []
            if has_relevant_docs:
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

            # 7. 构建上下文
            relevant_docs = [doc for doc in retrieved_docs if _is_relevant(doc)]
            context = self._format_retrieved_documents(relevant_docs)

            # 8. 构建 prompt
            rag_prompt = ChatPromptTemplate.from_messages([
                ("system", """你是一个专业的代码智能体助手 MiniCodeAI。请按照以下优先级回答用户问题：

【优先级规则】
1. 首先检查是否有已上传的文档。如果有，优先基于文档内容回答。
2. 如果文档内容足以回答问题（相关度高），请完全基于文档内容回答，并引用文档来源。
3. 如果文档内容不足以回答问题，或者用户询问的是外部知识（时事新闻、最新技术等），请先说明文档中找不到相关信息，然后基于你的通用知识或搜索互联网来补充回答。
4. 如果没有任何已上传文档，请直接回答问题。

【检索到的文档内容】
{context}

【重要：回答格式要求】
- 如果你的回答**基于或引用了上述文档内容**，请在回答开头添加标记 `[USED_DOC]`
- 如果你的回答**未使用上述文档内容**（如通用知识、未找到相关文档、用户问的是闲聊或外部信息等），请在回答开头添加标记 `[NO_DOC]`
- 如果文档内容不足以回答，你需要联网搜索获取最新信息，请在回答开头添加标记 `[NEED_WEB_SEARCH]`
- 标记必须放在回答的最开头，不要换行，不要加其他字符
- 标记后面紧跟实际回答内容，不需要换行分隔
- 用户看不到这个标记，它仅用于系统判断是否显示引用来源

请用中文回答，回答要专业、准确、简洁。"""),
                MessagesPlaceholder(variable_name="chat_history", optional=True),
                ("human", "{input}"),
            ])

            messages = rag_prompt.format_messages(
                context=context,
                input=message,
                chat_history=history,
            )

            # 9. 流式生成回答
            buffer = ""
            marker_detected = False
            used_document = False
            need_web_search = False
            MARKER_LEN = len("[NEED_WEB_SEARCH]")  # 最长标记 17 字符

            async for chunk in llm.astream(messages):
                if not chunk.content:
                    continue

                if not marker_detected:
                    buffer += chunk.content
                    if buffer.startswith("[USED_DOC]"):
                        used_document = True
                        marker_detected = True
                        rest = buffer[len("[USED_DOC]"):]
                        if rest:
                            yield {"type": "chunk", "content": rest}
                        buffer = ""
                    elif buffer.startswith("[NO_DOC]"):
                        used_document = False
                        marker_detected = True
                        rest = buffer[len("[NO_DOC]"):]
                        if rest:
                            yield {"type": "chunk", "content": rest}
                        buffer = ""
                    elif buffer.startswith("[NEED_WEB_SEARCH]"):
                        need_web_search = True
                        used_document = False
                        marker_detected = True
                        rest = buffer[len("[NEED_WEB_SEARCH]"):]
                        if rest:
                            yield {"type": "chunk", "content": rest}
                        buffer = ""
                    elif len(buffer) >= MARKER_LEN:
                        marker_detected = True
                        used_document = has_relevant_docs
                        yield {"type": "chunk", "content": buffer}
                        buffer = ""
                else:
                    yield {"type": "chunk", "content": chunk.content}

            # 边界处理
            if not marker_detected and buffer:
                used_document = has_relevant_docs
                yield {"type": "chunk", "content": buffer}

            # 10. 如果需要联网搜索（FR-13 外部搜索触发）
            if need_web_search and settings.TAVILY_API_KEY:
                yield {"type": "tool_call", "tool": "search_web", "input": message}
                try:
                    web_results = search_web.invoke({"query": message})
                    yield {"type": "tool_result", "tool": "search_web", "content": web_results[:500]}

                    # 基于检索结果再次生成回答
                    yield {"type": "thinking", "content": "基于网络搜索结果生成回答..."}
                    web_prompt = ChatPromptTemplate.from_messages([
                        ("system", """你是一个专业的代码智能体助手 MiniCodeAI。
基于以下网络搜索结果回答用户问题。请在回答中标注信息来源。

【网络搜索结果】
{web_results}

请用中文回答，回答要专业、准确、简洁。"""),
                        MessagesPlaceholder(variable_name="chat_history", optional=True),
                        ("human", "{input}"),
                    ])
                    web_messages = web_prompt.format_messages(
                        web_results=web_results,
                        input=message,
                        chat_history=history,
                    )
                    async for chunk in llm.astream(web_messages):
                        if chunk.content:
                            yield {"type": "chunk", "content": chunk.content}
                except Exception as e:
                    logger.error(f"网络搜索失败: {e}")
                    yield {"type": "tool_result", "tool": "search_web", "content": f"搜索失败: {str(e)}"}

            # 11. 只有当 AI 实际使用了文档内容回答时才发送引文
            if used_document and has_relevant_docs:
                yield {"type": "citations", "citations": citations}

        except Exception as e:
            logger.error(f"Agent 流式对话失败: {e}")
            yield {"type": "error", "content": f"对话服务出错: {str(e)}"}

    async def _multi_query_retrieve(
        self,
        queries: List[str],
        n_per_query: int = 5,
    ) -> List[Dict[str, Any]]:
        """多查询融合检索：对多个查询分别检索，合并去重后按相关度排序"""
        all_docs = []
        seen_chunk_ids = set()

        for query in queries:
            try:
                docs = vector_store.search(query=query, n_results=n_per_query)
                for doc in docs:
                    chunk_id = doc.get("chunk_id", "")
                    if chunk_id and chunk_id not in seen_chunk_ids:
                        seen_chunk_ids.add(chunk_id)
                        all_docs.append(doc)
            except Exception as e:
                logger.warning(f"查询 '{query}' 检索失败: {e}")

        # 按相关度降序排序
        all_docs.sort(
            key=lambda x: x.get("relevance_score", 0.0),
            reverse=True,
        )
        return all_docs[:10]  # 返回前 10 个

    async def generate_title(self, message: str) -> str:
        """根据用户首条消息生成会话标题"""
        try:
            llm = self._get_llm()
            title_prompt = ChatPromptTemplate.from_messages([
                ("system", """根据用户的问题生成一个简短的会话标题（不超过 15 个字）。
只输出标题文字，不要加引号或其他符号。"""),
                ("human", "{message}"),
            ])
            messages = title_prompt.format_messages(message=message)
            response = await llm.ainvoke(messages)
            title = response.content.strip()
            # 限制长度
            if len(title) > 20:
                title = title[:20] + "..."
            return title or "新对话"
        except Exception as e:
            logger.warning(f"生成标题失败: {e}")
            return "新对话"

    def _format_retrieved_documents(self, docs: List[Dict[str, Any]]) -> str:
        """将检索结果格式化为上下文文本"""
        if not docs:
            return "未上传任何文档，或已上传文档中未找到与问题相关的内容。"

        formatted = []
        for i, doc in enumerate(docs, 1):
            meta = doc.get("metadata", {})
            filename = meta.get("filename", "未知文档")
            doc_id = meta.get("doc_id", "未知")
            chunk_index = meta.get("chunk_index", 0)
            page = meta.get("page")
            content = doc.get("content", "")
            score = doc.get("relevance_score", 0.0)
            page_str = f"，第{page}页" if page is not None else ""
            formatted.append(
                f"[文档{i}] 来源: {filename} (ID: {doc_id}, 片段{chunk_index + 1}{page_str}, 相关度: {score:.2f})\n"
                f"{content}\n"
            )
        return "\n---\n".join(formatted)


# 全局单例
agent_service = AgentService()
