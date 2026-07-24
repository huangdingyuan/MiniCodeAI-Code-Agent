import type { Session, Message } from '../types'

// 按 user_id 隔离的会话存储 key
const SESSIONS_KEY_PREFIX = 'chat_sessions_'
const CURRENT_SESSION_KEY_PREFIX = 'current_session_id_'
const OLD_MESSAGES_KEY_PREFIX = 'chat_messages_'

// 旧版本（不分用户）的 key，用于一次性清理
const LEGACY_KEYS = ['chat_sessions', 'current_session_id', 'chat_messages']

// 获取当前登录用户 ID（从 auth store 写入 localStorage）
const getUserId = (): string => {
  return localStorage.getItem('current_user_id') || 'anonymous'
}

const sessionsKey = (): string => `${SESSIONS_KEY_PREFIX}${getUserId()}`
const currentSessionKey = (): string => `${CURRENT_SESSION_KEY_PREFIX}${getUserId()}`
const oldMessagesKey = (): string => `${OLD_MESSAGES_KEY_PREFIX}${getUserId()}`

// 一次性清理旧版本（不分用户）的 localStorage 残留数据
const cleanupLegacyKeys = (): void => {
  LEGACY_KEYS.forEach((key) => {
    if (localStorage.getItem(key) !== null) {
      localStorage.removeItem(key)
    }
  })
}

export const sessionManager = {
  getAllSessions(): Session[] {
    try {
      const saved = localStorage.getItem(sessionsKey())
      if (saved) {
        return JSON.parse(saved)
      }
    } catch (e) {
      console.error('加载会话列表失败:', e)
    }
    return []
  },

  getSession(id: string): Session | null {
    const sessions = this.getAllSessions()
    return sessions.find(s => s.id === id) || null
  },

  saveSession(session: Session): void {
    const sessions = this.getAllSessions()
    const index = sessions.findIndex(s => s.id === session.id)
    if (index >= 0) {
      sessions[index] = session
    } else {
      sessions.unshift(session)
    }
    localStorage.setItem(sessionsKey(), JSON.stringify(sessions))
  },

  deleteSession(id: string): void {
    const sessions = this.getAllSessions().filter(s => s.id !== id)
    localStorage.setItem(sessionsKey(), JSON.stringify(sessions))
    if (this.getCurrentSessionId() === id) {
      this.setCurrentSessionId('')
    }
  },

  createNewSession(): Session {
    const now = Date.now()
    const session: Session = {
      id: `session_${now}`,
      title: '新对话',
      messages: [
        {
          id: '1',
          role: 'assistant',
          content: '你好！我是 MiniCodeAI 代码智能体。我可以帮助你理解代码、解答技术问题、分析文档。请上传相关文档后开始提问。',
          timestamp: now
        }
      ],
      createdAt: now,
      updatedAt: now
    }
    this.saveSession(session)
    this.setCurrentSessionId(session.id)
    return session
  },

  updateSessionMessages(id: string, messages: Message[]): void {
    const session = this.getSession(id)
    if (session) {
      session.messages = messages
      session.updatedAt = Date.now()
      if (!session.title || session.title === '新对话') {
        const firstUserMessage = messages.find(m => m.role === 'user')
        if (firstUserMessage) {
          session.title = firstUserMessage.content.substring(0, 30) + (firstUserMessage.content.length > 30 ? '...' : '')
        }
      }
      this.saveSession(session)
    }
  },

  getCurrentSessionId(): string {
    return localStorage.getItem(currentSessionKey()) || ''
  },

  setCurrentSessionId(id: string): void {
    localStorage.setItem(currentSessionKey(), id)
  },

  getCurrentSession(): Session | null {
    const id = this.getCurrentSessionId()
    return id ? this.getSession(id) : null
  },

  // 清空当前用户的会话状态（用于登出）
  clearCurrentUserSession(): void {
    localStorage.removeItem(currentSessionKey())
  },

  // 获取旧版 chat_messages（按用户隔离）
  getLegacyMessages(): Message[] | null {
    cleanupLegacyKeys()
    try {
      const saved = localStorage.getItem(oldMessagesKey())
      if (saved) {
        return JSON.parse(saved)
      }
    } catch (e) {
      console.error('加载旧消息失败:', e)
    }
    return null
  },

  // 清理旧版残留 key（启动时调用一次）
  cleanupLegacyKeys(): void {
    cleanupLegacyKeys()
  }
}
