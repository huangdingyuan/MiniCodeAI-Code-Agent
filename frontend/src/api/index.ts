import axios from 'axios'
import type { Document, UploadResponse, LoginRequest, RegisterRequest, LoginResponse, ApiResponse, ChatRequest, ChatResponse, SessionInfo, DocumentPreview } from '../types'

// 创建 axios 实例
const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器：自动携带 token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器：统一处理错误
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('auth_token')
      localStorage.removeItem('user_info')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// 认证 API
export const authApi = {
  // 用户注册
  async register(data: RegisterRequest): Promise<ApiResponse> {
    return await api.post<ApiResponse>('/auth/register', data)
  },

  // 用户登录
  async login(data: LoginRequest): Promise<LoginResponse> {
    return await api.post<LoginResponse>('/auth/login', data)
  },

  // 上传头像（持久化到后端数据库）
  async uploadAvatar(file: File): Promise<{ avatar: string; message: string }> {
    const formData = new FormData()
    formData.append('file', file)
    return await api.post('/auth/avatar', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  }
}

// 文档管理 API
export const documentApi = {
  // 上传文档
  async upload(file: File): Promise<UploadResponse> {
    const formData = new FormData()
    formData.append('file', file)
    return await api.post('/documents/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  },

  // 获取文档列表
  async list(): Promise<Document[]> {
    return await api.get('/documents')
  },

  // 删除文档
  async delete(docId: string): Promise<void> {
    await api.delete(`/documents/${docId}`)
  },

  // 获取文档状态
  async getStatus(docId: string): Promise<Document> {
    return await api.get(`/documents/${docId}/status`)
  },

  // FR-5 文档预览
  async preview(docId: string): Promise<DocumentPreview> {
    return await api.get(`/documents/${docId}/preview`)
  },
}

// 会话管理 API（FR-16）
export const sessionApi = {
  // 列出用户所有会话
  async list(): Promise<SessionInfo[]> {
    return await api.get('/sessions')
  },

  // 创建新会话
  async create(data?: { session_id?: string; title?: string }): Promise<SessionInfo> {
    return await api.post('/sessions', data || {})
  },

  // 获取会话历史
  async get(sessionId: string): Promise<{
    session_id: string
    title: string
    messages: Array<{ role: string; content: string; timestamp?: number }>
  }> {
    return await api.get(`/sessions/${sessionId}`)
  },

  // 更新会话标题
  async updateTitle(sessionId: string, title: string): Promise<void> {
    await api.put(`/sessions/${sessionId}/title`, { title })
  },

  // 删除会话
  async delete(sessionId: string): Promise<void> {
    await api.delete(`/sessions/${sessionId}`)
  },
}

// 对话 API
export const chatApi = {
  // 非流式对话
  async sendMessage(data: ChatRequest): Promise<ChatResponse> {
    return await api.post<ChatResponse>('/chat/message', data)
  },

  // 流式对话（SSE）
  async streamMessage(data: ChatRequest): Promise<Response> {
    const token = localStorage.getItem('auth_token')
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    }
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }

    const response = await fetch('/api/chat/stream', {
      method: 'POST',
      headers,
      body: JSON.stringify(data),
    })

    if (!response.ok) {
      throw new Error(`对话请求失败: ${response.status}`)
    }

    return response
  },
}

// 图片识别 API
export const imageApi = {
  async recognize(file: File): Promise<any> {
    const formData = new FormData()
    formData.append('file', file)
    return await api.post('/images/recognize', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  }
}

// 健康检查 API
export const healthApi = {
  async check(): Promise<any> {
    return await api.get('/health')
  }
}

export default api
