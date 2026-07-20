"""
会话管理服务
使用 Redis 持久化对话历史，支持跨设备同步
如果 Redis 不可用，自动降级到内存存储
"""
import json
import logging
import time
from typing import List, Dict, Optional

import redis
from redis.exceptions import RedisError

from config import settings

logger = logging.getLogger(__name__)


class SessionService:
    """Redis 会话管理（带内存降级）"""

    def __init__(self):
        self._redis: Optional[redis.Redis] = None
        self._fallback_store: Dict[str, str] = {}  # 内存降级存储
        self._session_ttl = 7 * 24 * 3600  # 7 天过期
        self._connect()

    def _connect(self):
        """连接 Redis（失败则降级到内存）"""
        try:
            self._redis = redis.Redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_timeout=3,
                socket_connect_timeout=3,
            )
            self._redis.ping()
            logger.info("Redis 会话服务已连接")
        except RedisError as e:
            logger.warning(f"Redis 不可用，降级到内存存储: {e}")
            self._redis = None

    def _session_key(self, session_id: str, user_id: int) -> str:
        """生成 Redis key（按用户隔离）"""
        return f"chat:session:{user_id}:{session_id}"

    def _user_sessions_key(self, user_id: int) -> str:
        """用户所有 session 的索引集合"""
        return f"chat:user_sessions:{user_id}"

    def get_history(
        self,
        session_id: str,
        user_id: int,
        max_messages: int = 20,
    ) -> List[Dict[str, str]]:
        """获取会话历史"""
        try:
            key = self._session_key(session_id, user_id)
            raw = (
                self._redis.get(key)
                if self._redis
                else self._fallback_store.get(key)
            )
            if not raw:
                return []
            messages = json.loads(raw)
            # 只取最近 max_messages 条作为上下文
            return messages[-max_messages:]
        except Exception as e:
            logger.error(f"获取会话历史失败: {e}")
            return []

    def save_history(
        self,
        session_id: str,
        user_id: int,
        messages: List[Dict[str, str]],
    ) -> bool:
        """保存会话历史"""
        try:
            key = self._session_key(session_id, user_id)
            raw = json.dumps(messages, ensure_ascii=False)

            if self._redis:
                self._redis.setex(key, self._session_ttl, raw)
                # 加入用户 session 索引
                self._redis.sadd(self._user_sessions_key(user_id), session_id)
            else:
                self._fallback_store[key] = raw
            return True
        except Exception as e:
            logger.error(f"保存会话历史失败: {e}")
            return False

    def append_message(
        self,
        session_id: str,
        user_id: int,
        role: str,
        content: str,
    ) -> List[Dict[str, str]]:
        """追加一条消息到会话历史，返回最新历史"""
        history = self.get_history(session_id, user_id)
        history.append({
            "role": role,
            "content": content,
            "timestamp": int(time.time()),
        })
        # 限制单个 session 消息总数
        if len(history) > 100:
            history = history[-100:]
        self.save_history(session_id, user_id, history)
        return history

    def list_user_sessions(self, user_id: int) -> List[str]:
        """获取用户所有 session_id"""
        try:
            if self._redis:
                return list(self._redis.smembers(self._user_sessions_key(user_id)))
            return []
        except Exception as e:
            logger.error(f"获取用户会话列表失败: {e}")
            return []

    def delete_session(self, session_id: str, user_id: int) -> bool:
        """删除会话"""
        try:
            key = self._session_key(session_id, user_id)
            if self._redis:
                self._redis.delete(key)
                self._redis.srem(self._user_sessions_key(user_id), session_id)
            else:
                self._fallback_store.pop(key, None)
            return True
        except Exception as e:
            logger.error(f"删除会话失败: {e}")
            return False

    def update_session_title(
        self,
        session_id: str,
        user_id: int,
        title: str,
    ) -> bool:
        """更新会话标题（独立存储）"""
        try:
            key = f"chat:session_title:{user_id}:{session_id}"
            if self._redis:
                self._redis.setex(key, self._session_ttl, title)
            else:
                self._fallback_store[key] = title
            return True
        except Exception as e:
            logger.error(f"更新会话标题失败: {e}")
            return False

    def get_session_title(self, session_id: str, user_id: int) -> str:
        """获取会话标题"""
        try:
            key = f"chat:session_title:{user_id}:{session_id}"
            if self._redis:
                return self._redis.get(key) or ""
            return self._fallback_store.get(key, "")
        except Exception as e:
            logger.error(f"获取会话标题失败: {e}")
            return ""


# 全局单例
session_service = SessionService()
