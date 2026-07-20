// 消息类型
export interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: number
  citations?: Citation[]
  isStreaming?: boolean
  imageUrl?: string
  // FR-12 思考过程
  thinkingSteps?: string[]
  // FR-12 检索结果（在思考过程中展示）
  retrievedDocuments?: RetrievedDocument[]
  // FR-13 工具调用记录
  toolCalls?: ToolCallRecord[]
}

// 引用来源
export interface Citation {
  doc_id: string
  filename: string
  page?: number
  chunk_id?: string
  content?: string
  relevance_score?: number
}

// FR-12 检索到的文档摘要
export interface RetrievedDocument {
  filename: string
  doc_id: string
  chunk_id: string
  relevance_score: number
  page?: number
  preview: string
}

// FR-13 工具调用记录
export interface ToolCallRecord {
  tool: string
  input: string
  output?: string
  status: 'calling' | 'done' | 'error'
}

// 文档类型
export interface Document {
  doc_id: string
  filename: string
  file_type: string
  file_size: number
  upload_time: string
  status: 'parsing' | 'ready' | 'error'
  chunk_count?: number
}

// 对话请求
export interface ChatRequest {
  message: string
  session_id: string
  chat_history?: Array<{ role: string; content: string }>
}

// 对话响应
export interface ChatResponse {
  message: string
  citations: Citation[]
  session_id: string
}

// 会话类型
export interface Session {
  id: string
  title: string
  messages: Message[]
  createdAt: number
  updatedAt: number
}

// 会话信息（后端返回的精简格式）
export interface SessionInfo {
  session_id: string
  title: string
  message_count: number
  last_updated?: number
}

// SSE 事件
export interface SSEEvent {
  type: 'thinking' | 'retrieving' | 'tool_call' | 'tool_result' | 'generating' | 'citations' | 'done' | 'error'
  data: any
}

// 上传响应
export interface UploadResponse {
  task_id: string
  doc_id: string
  filename: string
  status: string
}

// 文档预览响应
export interface DocumentPreview {
  doc_id: string
  filename: string
  file_type: string
  preview: string
  chunk_count: number
  source: string
}

// 认证相关类型
export interface User {
  id: number
  username: string
  email: string
  avatar?: string
}

export interface LoginRequest {
  username: string
  password: string
}

export interface RegisterRequest {
  username: string
  email: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  user: User
}

export interface ApiResponse {
  message: string
  success: boolean
}

export interface ApiError {
  detail: string
}
