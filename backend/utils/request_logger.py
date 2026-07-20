"""
结构化请求日志
记录每次请求的输入、检索块、输出、耗时，便于调试
日志文件按天滚动，保留 7 天
"""
import json
import logging
import os
import time
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from config import settings


class RequestLogger:
    """请求级结构化日志记录器"""

    def __init__(self):
        self._logger: Optional[logging.Logger] = None
        self._log_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "logs",
        )
        os.makedirs(self._log_dir, exist_ok=True)
        self._setup_logger()

    def _setup_logger(self):
        """配置日志器"""
        self._logger = logging.getLogger("request_logger")
        self._logger.setLevel(logging.INFO)

        # 避免重复添加 handler
        if self._logger.handlers:
            return

        # 按天滚动日志文件，保留 7 天
        from logging.handlers import TimedRotatingFileHandler
        log_file = os.path.join(self._log_dir, "requests.log")
        handler = TimedRotatingFileHandler(
            log_file,
            when='midnight',
            interval=1,
            backupCount=7,
            encoding='utf-8',
        )
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
        )
        handler.setFormatter(formatter)
        self._logger.addHandler(handler)

    def start_request(
        self,
        user_id: int,
        endpoint: str,
        input_text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """开始记录请求，返回 request_id"""
        request_id = str(uuid.uuid4())[:8]
        log_entry = {
            "request_id": request_id,
            "user_id": user_id,
            "endpoint": endpoint,
            "input": input_text[:500],  # 限制长度
            "start_time": datetime.now().isoformat(),
            "metadata": metadata or {},
        }
        self._logger.info(f"REQUEST_START | {json.dumps(log_entry, ensure_ascii=False)}")
        return request_id

    def log_retrieval(
        self,
        request_id: str,
        queries: List[str],
        retrieved_docs: List[Dict[str, Any]],
    ):
        """记录检索过程"""
        log_entry = {
            "request_id": request_id,
            "queries": queries,
            "doc_count": len(retrieved_docs),
            "docs": [
                {
                    "chunk_id": d.get("chunk_id", ""),
                    "doc_id": d.get("metadata", {}).get("doc_id", ""),
                    "filename": d.get("metadata", {}).get("filename", ""),
                    "relevance_score": d.get("relevance_score", 0.0),
                    "bm25_score": d.get("bm25_score", 0.0),
                }
                for d in retrieved_docs[:5]
            ],
        }
        self._logger.info(f"RETRIEVAL | {json.dumps(log_entry, ensure_ascii=False)}")

    def log_tool_call(
        self,
        request_id: str,
        tool: str,
        tool_input: str,
        tool_output: str,
    ):
        """记录工具调用"""
        log_entry = {
            "request_id": request_id,
            "tool": tool,
            "input": tool_input[:200],
            "output": tool_output[:500],
        }
        self._logger.info(f"TOOL_CALL | {json.dumps(log_entry, ensure_ascii=False)}")

    def end_request(
        self,
        request_id: str,
        output_text: str,
        citations: Optional[List[Dict]] = None,
        error: Optional[str] = None,
        duration: float = 0.0,
    ):
        """结束记录请求"""
        log_entry = {
            "request_id": request_id,
            "output": output_text[:500] if output_text else "",
            "citations_count": len(citations) if citations else 0,
            "citations": [
                {"filename": c.get("filename", ""), "relevance_score": c.get("relevance_score", 0)}
                for c in (citations or [])
            ],
            "error": error,
            "duration_ms": int(duration * 1000),
            "end_time": datetime.now().isoformat(),
        }
        level = "ERROR" if error else "INFO"
        self._logger.log(
            logging.getLevelName(level),
            f"REQUEST_END | {json.dumps(log_entry, ensure_ascii=False)}",
        )


# 全局单例
request_logger = RequestLogger()
