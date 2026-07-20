import type { Session, Message } from '../types'

const SESSIONS_KEY = 'chat_sessions'
const CURRENT_SESSION_KEY = 'current_session_id'

export const sessionManager = {
  getAllSessions(): Session[] {
    try {
      const saved = localStorage.getItem(SESSIONS_KEY)
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
    localStorage.setItem(SESSIONS_KEY, JSON.stringify(sessions))
  },

  deleteSession(id: string): void {
    const sessions = this.getAllSessions().filter(s => s.id !== id)
    localStorage.setItem(SESSIONS_KEY, JSON.stringify(sessions))
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
    return localStorage.getItem(CURRENT_SESSION_KEY) || ''
  },

  setCurrentSessionId(id: string): void {
    localStorage.setItem(CURRENT_SESSION_KEY, id)
  },

  getCurrentSession(): Session | null {
    const id = this.getCurrentSessionId()
    return id ? this.getSession(id) : null
  }
}
